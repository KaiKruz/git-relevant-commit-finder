"""
SQLite metadata store for repositories and commits.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from app.core.config import settings


def _utc_now() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    """Create a SQLite connection with row factory enabled."""
    db_path = settings.sqlite_db_path
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create required SQLite tables if they do not exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repos (
                repo_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                local_path TEXT NOT NULL,
                branch TEXT,
                github_url TEXT,
                status TEXT NOT NULL DEFAULT 'connected',
                commit_count INTEGER NOT NULL DEFAULT 0,
                last_indexed_sha TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commits (
                repo_id TEXT NOT NULL,
                sha TEXT NOT NULL,
                short_sha TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_email TEXT NOT NULL,
                date TEXT NOT NULL,
                message TEXT NOT NULL,
                files_json TEXT NOT NULL,
                additions INTEGER NOT NULL DEFAULT 0,
                deletions INTEGER NOT NULL DEFAULT 0,
                diff_preview TEXT NOT NULL DEFAULT '',
                summary_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (repo_id, sha),
                FOREIGN KEY (repo_id) REFERENCES repos(repo_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commits_repo_date ON commits(repo_id, date)"
        )
        conn.commit()


def upsert_repo(repo: dict) -> None:
    """Insert or update a repository row."""
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO repos (
                repo_id, source_type, source, repo_name, local_path, branch,
                github_url, status, commit_count, last_indexed_sha, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_id) DO UPDATE SET
                source_type=excluded.source_type,
                source=excluded.source,
                repo_name=excluded.repo_name,
                local_path=excluded.local_path,
                branch=excluded.branch,
                github_url=excluded.github_url,
                status=excluded.status,
                commit_count=excluded.commit_count,
                last_indexed_sha=excluded.last_indexed_sha,
                updated_at=excluded.updated_at
            """,
            (
                repo["repo_id"],
                repo["source_type"],
                repo["source"],
                repo["repo_name"],
                repo["local_path"],
                repo.get("branch"),
                repo.get("github_url", ""),
                repo.get("status", "connected"),
                int(repo.get("commit_count", 0)),
                repo.get("last_indexed_sha"),
                repo.get("created_at", now),
                now,
            ),
        )
        conn.commit()


def update_repo_index_state(
    repo_id: str, *, commit_count: int, last_indexed_sha: str | None, status: str
) -> None:
    """Update repo status and indexing metadata."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE repos
            SET commit_count = ?, last_indexed_sha = ?, status = ?, updated_at = ?
            WHERE repo_id = ?
            """,
            (commit_count, last_indexed_sha, status, _utc_now(), repo_id),
        )
        conn.commit()


def get_repo(repo_id: str) -> dict | None:
    """Get repository metadata by ID."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM repos WHERE repo_id = ?", (repo_id,)).fetchone()
    return dict(row) if row else None


def list_repos() -> list[dict]:
    """List all repositories ordered by most recently updated."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM repos ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


def get_commit(repo_id: str, sha: str) -> dict | None:
    """Get one commit row for a repo."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM commits WHERE repo_id = ? AND sha = ?",
            (repo_id, sha),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["files"] = json.loads(data.pop("files_json", "[]"))
    return data


def get_commit_shas(repo_id: str) -> set[str]:
    """Return all indexed SHAs for a repository."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sha FROM commits WHERE repo_id = ?",
            (repo_id,),
        ).fetchall()
    return {row["sha"] for row in rows}


def upsert_commits(repo_id: str, commits: list[dict]) -> int:
    """Insert commit metadata rows. Returns number of newly inserted SHAs."""
    if not commits:
        return 0

    existing = get_commit_shas(repo_id)
    inserted = 0
    now = _utc_now()

    with _connect() as conn:
        for commit in commits:
            if commit["sha"] not in existing:
                inserted += 1
            conn.execute(
                """
                INSERT INTO commits (
                    repo_id, sha, short_sha, author_name, author_email, date,
                    message, files_json, additions, deletions, diff_preview, summary_text,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id, sha) DO UPDATE SET
                    short_sha=excluded.short_sha,
                    author_name=excluded.author_name,
                    author_email=excluded.author_email,
                    date=excluded.date,
                    message=excluded.message,
                    files_json=excluded.files_json,
                    additions=excluded.additions,
                    deletions=excluded.deletions,
                    diff_preview=excluded.diff_preview,
                    summary_text=excluded.summary_text,
                    updated_at=excluded.updated_at
                """,
                (
                    repo_id,
                    commit["sha"],
                    commit["short_sha"],
                    commit["author_name"],
                    commit["author_email"],
                    commit["date"],
                    commit["message"],
                    json.dumps(commit["files"]),
                    int(commit.get("additions", 0)),
                    int(commit.get("deletions", 0)),
                    commit.get("diff_preview", ""),
                    commit.get("summary_text", ""),
                    now,
                    now,
                ),
            )
        conn.commit()

    return inserted
