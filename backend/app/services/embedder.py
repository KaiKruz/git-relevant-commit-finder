"""
Embedding service for commit summary documents.
"""

from __future__ import annotations

import logging

from app.db.vector_store import get_collection

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def _build_document(commit: dict) -> str:
    """Return text to embed for a commit."""
    return commit.get("summary_text") or commit.get("message", "")


def _build_metadata(commit: dict) -> dict:
    """Return vector metadata fields used for filtering and rendering."""
    return {
        "author_name": commit["author_name"],
        "author_email": commit["author_email"],
        "date": commit["date"],
        "message": commit["message"],
        "short_sha": commit["short_sha"],
        "files": ",".join(commit["files"][:60]),
        "additions": int(commit.get("additions", 0)),
        "deletions": int(commit.get("deletions", 0)),
        "diff_preview": commit.get("diff_preview", ""),
    }


def upsert_commits(
    repo_id: str,
    commits: list[dict],
    existing_shas: set[str] | None = None,
) -> int:
    """
    Embed and upsert commit documents, skipping already-indexed SHAs.
    Returns number of newly embedded commits.
    """
    collection = get_collection(repo_id)
    existing_shas = existing_shas or set()

    new_commits = [c for c in commits if c["sha"] not in existing_shas]
    if not new_commits:
        logger.info("No new commits to embed for repo %s", repo_id)
        return 0

    logger.info("Embedding %d commits for repo %s", len(new_commits), repo_id)

    for i in range(0, len(new_commits), BATCH_SIZE):
        batch = new_commits[i : i + BATCH_SIZE]
        collection.upsert(
            ids=[c["sha"] for c in batch],
            documents=[_build_document(c) for c in batch],
            metadatas=[_build_metadata(c) for c in batch],
        )

    return len(new_commits)
