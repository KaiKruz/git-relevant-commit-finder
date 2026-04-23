"""
In-memory job tracking for indexing and refresh operations.
"""

from __future__ import annotations

import threading
import uuid

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}


def create_job(repo_id: str, job_type: str) -> dict:
    """Create and store a queued job."""
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job = {
        "job_id": job_id,
        "repo_id": repo_id,
        "job_type": job_type,
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "stats": {
            "indexed_commits": 0,
            "new_embeddings": 0,
            "total_commits": 0,
        },
        "error": None,
    }
    with _LOCK:
        _JOBS[job_id] = job
    return job


def get_job(job_id: str) -> dict | None:
    """Return job state by id."""
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def update_job(job_id: str, **fields) -> dict | None:
    """Update job fields and return updated job."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        job.update(fields)
        return dict(job)
