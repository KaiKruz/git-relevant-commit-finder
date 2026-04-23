"""
Repository ingest service: connect repos, checkout branches, and extract commit data.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from datetime import datetime, timezone

from app.core.config import settings
from app.db import sqlite_store

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _run(
    cmd: list[str], *, timeout: int = 60, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command and optionally validate return code."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or "unknown git error"
        raise RuntimeError(stderr)
    return result


def _normalize_source(source: str) -> str:
    """Normalize source string for deterministic IDs."""
    return source.strip().replace("\\", "/").rstrip("/")


def make_repo_id(source_type: str, source: str) -> str:
    """Generate deterministic repository ID from source type + source."""
    normalized = _normalize_source(source)
    if "github.com" in normalized:
        normalized = _github_web_url(normalized) or normalized
    key = f"{source_type}:{normalized}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def _github_web_url(source: str) -> str:
    """Convert a GitHub git URL to web URL if possible."""
    if "github.com" not in source:
        return ""
    url = source.strip().rstrip("/")
    if url.startswith("git@github.com:"):
        url = url.replace("git@github.com:", "https://github.com/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def _get_origin_url(repo_path: str) -> str:
    """Return origin remote URL, empty string on failure."""
    result = _run(
        ["git", "-C", repo_path, "remote", "get-url", "origin"],
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _ensure_branch(repo_path: str, branch: str | None) -> str:
    """Checkout selected branch or keep current branch when omitted."""
    _run(["git", "-C", repo_path, "fetch", "--all", "--prune"], check=False)

    if branch:
        checkout = _run(
            ["git", "-C", repo_path, "checkout", branch],
            timeout=30,
            check=False,
        )
        if checkout.returncode != 0:
            tracking = _run(
                ["git", "-C", repo_path, "checkout", "-B", branch, f"origin/{branch}"],
                timeout=30,
                check=False,
            )
            if tracking.returncode != 0:
                msg = checkout.stderr.strip() or tracking.stderr.strip()
                raise ValueError(f"Unable to checkout branch '{branch}': {msg}")
        return branch

    result = _run(
        ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
        timeout=10,
    )
    return result.stdout.strip()


def connect_repo(source_type: str, source: str, branch: str | None) -> dict:
    """
    Connect a repository source (GitHub URL or local path) and checkout branch.
    Returns repository metadata for API response and persistence.
    """
    if source_type not in {"github", "local"}:
        raise ValueError("source_type must be 'github' or 'local'")

    source = source.strip()
    if not source:
        raise ValueError("source cannot be empty")

    if source_type == "github":
        if "github.com" not in source:
            raise ValueError("For source_type='github', provide a public GitHub URL")

        repo_id = make_repo_id(source_type, source)
        local_path = os.path.abspath(os.path.join(settings.repos_clone_dir, repo_id))
        os.makedirs(settings.repos_clone_dir, exist_ok=True)

        if os.path.isdir(os.path.join(local_path, ".git")):
            _run(["git", "-C", local_path, "fetch", "--all", "--prune"], check=False)
        else:
            result = _run(
                ["git", "clone", source, local_path],
                timeout=300,
                check=False,
            )
            if result.returncode != 0:
                raise ValueError(f"git clone failed: {result.stderr.strip()}")

        github_url = _github_web_url(source)
    else:
        local_path = os.path.abspath(source)
        if not os.path.isdir(local_path):
            raise ValueError(f"Local path does not exist: {local_path}")
        if not os.path.isdir(os.path.join(local_path, ".git")):
            raise ValueError(f"Not a git repository: {local_path}")
        repo_id = make_repo_id(source_type, local_path)
        origin = _get_origin_url(local_path)
        github_url = _github_web_url(origin)

    selected_branch = _ensure_branch(local_path, branch)
    repo_name = os.path.basename(local_path.rstrip("/\\"))

    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "local_path": local_path,
        "branch": selected_branch,
        "github_url": github_url,
        "source_type": source_type,
        "source": source if source_type == "github" else local_path,
        "status": "connected",
        "commit_count": 0,
        "last_indexed_sha": None,
        "created_at": _utc_now(),
    }


def fetch_latest(repo_path: str) -> None:
    """Fetch latest refs for repository if remotes are configured."""
    _run(["git", "-C", repo_path, "fetch", "--all", "--prune"], check=False)


def _compact_diff_preview(diff_text: str) -> str:
    """Build a compact one-line-ish diff preview for summary text."""
    compact = " ".join(diff_text.split())
    if len(compact) > settings.max_summary_diff_chars:
        return f"{compact[:settings.max_summary_diff_chars]}..."
    return compact


def _extract_commit(repo_path: str, sha: str) -> dict | None:
    """Extract all required fields for one commit."""
    header = _run(
        [
            "git",
            "-C",
            repo_path,
            "show",
            "-s",
            "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s",
            sha,
        ],
        timeout=20,
        check=False,
    )
    if header.returncode != 0:
        return None

    parts = header.stdout.strip().split("\x1f")
    if len(parts) != 6:
        return None

    sha_full, short_sha, author_name, author_email, date_str, message = parts

    patch_result = _run(
        [
            "git",
            "-C",
            repo_path,
            "show",
            "--format=",
            "--numstat",
            "--patch",
            "--no-color",
            "--unified=1",
            sha_full,
        ],
        timeout=60,
        check=False,
    )
    if patch_result.returncode != 0:
        return None

    raw = patch_result.stdout
    files: list[str] = []
    additions = 0
    deletions = 0
    seen_files: set[str] = set()

    for line in raw.splitlines():
        cols = line.split("\t")
        if len(cols) != 3:
            continue
        add_raw, del_raw, file_path = cols
        if (add_raw.isdigit() or add_raw == "-") and (del_raw.isdigit() or del_raw == "-"):
            file_path = file_path.strip()
            if file_path and file_path not in seen_files:
                files.append(file_path)
                seen_files.add(file_path)
            if add_raw.isdigit():
                additions += int(add_raw)
            if del_raw.isdigit():
                deletions += int(del_raw)

    start = raw.find("diff --git")
    diff_source = raw[start:] if start != -1 else raw
    diff_preview = diff_source[: settings.max_diff_chars].strip()

    files_text = ", ".join(files[:25])
    summary_text = (
        f"{message}\nChanged files: {files_text}\nDiff preview: {_compact_diff_preview(diff_preview)}"
    ).strip()

    return {
        "sha": sha_full,
        "short_sha": short_sha,
        "author_name": author_name,
        "author_email": author_email,
        "date": date_str,
        "message": message,
        "files": files,
        "additions": additions,
        "deletions": deletions,
        "diff_preview": diff_preview,
        "summary_text": summary_text,
    }


def extract_commits(
    repo_path: str,
    branch: str | None = None,
    max_commits: int | None = None,
) -> list[dict]:
    """Extract commits with metadata, stats, and diff preview."""
    if max_commits is None:
        max_commits = settings.max_commits

    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        "--format=%H",
        f"-{max_commits}",
    ]
    if branch:
        cmd.append(branch)

    result = _run(cmd, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")

    commits: list[dict] = []
    for sha in [line.strip() for line in result.stdout.splitlines() if line.strip()]:
        commit = _extract_commit(repo_path, sha)
        if commit:
            commits.append(commit)

    return commits


def get_commit_detail(repo_path: str, sha: str) -> dict | None:
    """Get one commit detail directly from git."""
    return _extract_commit(repo_path, sha)


def get_existing_shas(repo_id: str) -> set[str]:
    """Return already-indexed SHAs from vector store."""
    from app.db.vector_store import get_collection

    collection = get_collection(repo_id)
    if collection.count() == 0:
        return set()
    result = collection.get()
    return set(result["ids"])


def save_repo_meta(repo_data: dict) -> None:
    """Persist repository metadata to SQLite."""
    sqlite_store.upsert_repo(repo_data)


def update_repo_after_index(
    repo_id: str, *, commit_count: int, last_indexed_sha: str | None, status: str
) -> None:
    """Update repository indexing state in SQLite."""
    sqlite_store.update_repo_index_state(
        repo_id,
        commit_count=commit_count,
        last_indexed_sha=last_indexed_sha,
        status=status,
    )


def list_repos() -> list[dict]:
    """List all repositories from SQLite."""
    return sqlite_store.list_repos()


def get_repo_meta(repo_id: str) -> dict | None:
    """Get one repository metadata row from SQLite."""
    return sqlite_store.get_repo(repo_id)


def save_commits(repo_id: str, commits: list[dict]) -> int:
    """Persist commit metadata rows to SQLite."""
    return sqlite_store.upsert_commits(repo_id, commits)


def get_commit_from_store(repo_id: str, sha: str) -> dict | None:
    """Get commit metadata from SQLite."""
    return sqlite_store.get_commit(repo_id, sha)


def github_commit_url(github_url: str, sha: str) -> str:
    """Build a GitHub commit URL when repo has a GitHub remote."""
    if not github_url:
        return ""
    return f"{github_url.rstrip('/')}/commit/{sha}"
