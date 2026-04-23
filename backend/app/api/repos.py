"""
Repository connection, indexing jobs, refresh jobs, and status API.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.schemas import (
    ConnectRepoRequest,
    ConnectRepoResponse,
    JobQueuedResponse,
    JobStatusResponse,
    RepoJobRequest,
)
from app.services import embedder, ingestor, jobs

logger = logging.getLogger(__name__)
router = APIRouter()


def _run_index_job(job_id: str, repo_id: str, refresh: bool) -> None:
    """Run indexing job and update in-memory status."""
    job_type = "refresh" if refresh else "index"
    jobs.update_job(job_id, status="running", progress=10, message=f"{job_type.title()} started")

    try:
        repo = ingestor.get_repo_meta(repo_id)
        if repo is None:
            jobs.update_job(
                job_id,
                status="failed",
                progress=100,
                message="Repository not found",
                error=f"Repo '{repo_id}' not found",
            )
            return

        synced_repo = ingestor.connect_repo(
            source_type=repo["source_type"],
            source=repo["source"],
            branch=repo.get("branch"),
        )
        ingestor.save_repo_meta({**synced_repo, "repo_id": repo_id})
        jobs.update_job(job_id, progress=35, message="Repository synced")

        if refresh:
            ingestor.fetch_latest(synced_repo["local_path"])
            jobs.update_job(job_id, progress=45, message="Fetched latest refs")

        commits = ingestor.extract_commits(
            repo_path=synced_repo["local_path"],
            branch=synced_repo.get("branch"),
        )
        total_commits = len(commits)
        jobs.update_job(
            job_id,
            progress=65,
            message="Commits extracted",
            stats={
                "indexed_commits": total_commits,
                "new_embeddings": 0,
                "total_commits": total_commits,
            },
        )

        existing_shas = ingestor.get_existing_shas(repo_id)
        new_embeddings = embedder.upsert_commits(repo_id, commits, existing_shas)
        ingestor.save_commits(repo_id, commits)

        last_sha = commits[0]["sha"] if commits else None
        ingestor.save_repo_meta(
            {
                **synced_repo,
                "repo_id": repo_id,
                "status": "ready",
                "commit_count": total_commits,
                "last_indexed_sha": last_sha,
            }
        )

        jobs.update_job(
            job_id,
            status="completed",
            progress=100,
            message=f"{job_type.title()} completed",
            stats={
                "indexed_commits": total_commits,
                "new_embeddings": new_embeddings,
                "total_commits": total_commits,
            },
            error=None,
        )
    except Exception as exc:
        logger.exception("Job failed (%s, repo=%s): %s", job_id, repo_id, exc)
        jobs.update_job(
            job_id,
            status="failed",
            progress=100,
            message="Job failed",
            error=str(exc),
        )


@router.post("/repo/connect", response_model=ConnectRepoResponse)
async def connect_repo(body: ConnectRepoRequest) -> ConnectRepoResponse:
    """Connect a repo source by cloning/opening and checking out selected branch."""
    try:
        repo = ingestor.connect_repo(body.source_type, body.source, body.branch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    ingestor.save_repo_meta(repo)
    return ConnectRepoResponse(
        repo_id=repo["repo_id"],
        repo_name=repo["repo_name"],
        local_path=repo["local_path"],
        branch=repo["branch"],
        github_url=repo.get("github_url", ""),
        status="connected",
    )


@router.post("/repo/index", response_model=JobQueuedResponse)
async def index_repo(body: RepoJobRequest, background_tasks: BackgroundTasks) -> JobQueuedResponse:
    """Queue a repository indexing job."""
    if ingestor.get_repo_meta(body.repo_id) is None:
        raise HTTPException(status_code=404, detail=f"Repo '{body.repo_id}' not found.")

    job = jobs.create_job(body.repo_id, "index")
    background_tasks.add_task(_run_index_job, job["job_id"], body.repo_id, False)
    return JobQueuedResponse(job_id=job["job_id"], status="queued")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Return current status for an indexing/refresh job."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobStatusResponse(**job)


@router.post("/repo/refresh", response_model=JobQueuedResponse)
async def refresh_repo(body: RepoJobRequest, background_tasks: BackgroundTasks) -> JobQueuedResponse:
    """Queue a safe reindex refresh job (duplicates are skipped by SHA)."""
    if ingestor.get_repo_meta(body.repo_id) is None:
        raise HTTPException(status_code=404, detail=f"Repo '{body.repo_id}' not found.")

    job = jobs.create_job(body.repo_id, "refresh")
    background_tasks.add_task(_run_index_job, job["job_id"], body.repo_id, True)
    return JobQueuedResponse(job_id=job["job_id"], status="queued")
