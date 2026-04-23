"""FastAPI application entrypoint."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, init_db
from .models import CommitRecord, IndexJob, Repository
from .schemas import (
    CommitDetailResponse,
    JobStatusResponse,
    RepoConnectRequest,
    RepoConnectResponse,
    RepoIndexRequest,
    RepoIndexResponse,
    SearchRequest,
    SearchResponse,
)
from .vector_store import get_commit_collection

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    """Initialize local storage dependencies."""
    init_db()
    get_commit_collection()


def _guess_repo_name(source_type: str, source: str) -> str:
    """Infer repository name from GitHub URL or local path."""
    if source_type == "github":
        path = urlparse(source).path.rstrip("/")
        name = path.split("/")[-1] if path else "repo"
        return name[:-4] if name.endswith(".git") else name
    return Path(source).name or "repo"


@app.get("/api/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/api/repo/connect", response_model=RepoConnectResponse)
def connect_repo(payload: RepoConnectRequest, db: Session = Depends(get_db)) -> RepoConnectResponse:
    """Create or update tracked repository metadata."""
    repo_name = _guess_repo_name(payload.source_type, payload.source)
    if payload.source_type == "github":
        local_path = str((settings.absolute_repo_clone_dir / repo_name).resolve())
        github_url = payload.source
    else:
        local_path = str(Path(payload.source).resolve())
        github_url = None

    repo = (
        db.query(Repository)
        .filter(Repository.source == payload.source, Repository.branch == payload.branch)
        .first()
    )
    if repo is None:
        repo = Repository(
            source_type=payload.source_type,
            source=payload.source,
            repo_name=repo_name,
            local_path=local_path,
            branch=payload.branch,
            github_url=github_url,
        )
        db.add(repo)
    else:
        repo.source_type = payload.source_type
        repo.repo_name = repo_name
        repo.local_path = local_path
        repo.branch = payload.branch
        repo.github_url = github_url
        repo.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(repo)
    return RepoConnectResponse(
        repo_id=repo.id,
        repo_name=repo.repo_name,
        local_path=repo.local_path,
        branch=repo.branch,
    )


def _create_job(db: Session, repo_id: int, job_type: str) -> RepoIndexResponse:
    """Create a queued indexing job row."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    job = IndexJob(
        job_id=job_id,
        repo_id=repo_id,
        job_type=job_type,
        status="queued",
        progress=0,
        message="Job queued",
    )
    db.add(job)
    db.commit()
    return RepoIndexResponse(job_id=job_id, status="queued")


@app.post("/api/repo/index", response_model=RepoIndexResponse)
def start_index(payload: RepoIndexRequest, db: Session = Depends(get_db)) -> RepoIndexResponse:
    """Queue a new index job."""
    return _create_job(db=db, repo_id=payload.repo_id, job_type="index")


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    """Return status details for a queued/running/completed job."""
    job = db.query(IndexJob).filter(IndexJob.job_id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(status=job.status, progress=job.progress, message=job.message)


@app.post("/api/search", response_model=SearchResponse)
def search_commits(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    """Stub semantic search endpoint returning empty ranked results for now."""
    repo = db.query(Repository).filter(Repository.id == payload.repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return SearchResponse(results=[])


@app.get("/api/commit/{sha}", response_model=CommitDetailResponse)
def get_commit_detail(
    sha: str, repo_id: int = Query(..., ge=1), db: Session = Depends(get_db)
) -> CommitDetailResponse:
    """Return full commit details for one commit SHA within a repository."""
    commit = (
        db.query(CommitRecord)
        .filter(CommitRecord.repo_id == repo_id, CommitRecord.sha == sha)
        .first()
    )
    if commit is None:
        raise HTTPException(status_code=404, detail="Commit not found")

    try:
        files_changed = json.loads(commit.files_changed or "[]")
    except json.JSONDecodeError:
        files_changed = []

    return CommitDetailResponse(
        sha=commit.sha,
        author=commit.author,
        date=commit.date,
        message=commit.message,
        files_changed=files_changed,
        diff_preview=commit.diff_preview,
        github_commit_url=commit.github_commit_url,
    )


@app.post("/api/repo/refresh", response_model=RepoIndexResponse)
def refresh_repo(payload: RepoIndexRequest, db: Session = Depends(get_db)) -> RepoIndexResponse:
    """Queue a refresh job for incremental indexing."""
    return _create_job(db=db, repo_id=payload.repo_id, job_type="refresh")
