"""
Shared API request/response schemas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConnectRepoRequest(BaseModel):
    source_type: Literal["github", "local"]
    source: str = Field(..., min_length=1)
    branch: str | None = None


class ConnectRepoResponse(BaseModel):
    repo_id: str
    repo_name: str
    local_path: str
    branch: str
    github_url: str = ""
    status: str


class RepoJobRequest(BaseModel):
    repo_id: str = Field(..., min_length=1)


class JobQueuedResponse(BaseModel):
    job_id: str
    status: str


class JobStats(BaseModel):
    indexed_commits: int = 0
    new_embeddings: int = 0
    total_commits: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    stats: JobStats
    error: str | None = None


class SearchFilters(BaseModel):
    author: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    path_contains: str | None = None
    branch: str | None = None


class SearchRequest(BaseModel):
    repo_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=50)
    filters: SearchFilters | None = None


class SearchResult(BaseModel):
    rank: int
    sha: str
    short_sha: str
    vector_score: float
    rerank_score: float
    message: str
    author_name: str
    author_email: str
    date: str
    files: list[str]
    additions: int
    deletions: int
    diff_preview: str
    github_url: str = ""


class SearchResponse(BaseModel):
    repo_id: str
    query: str
    total: int
    results: list[SearchResult]


class CommitDetailResponse(BaseModel):
    repo_id: str
    sha: str
    short_sha: str
    author_name: str
    author_email: str
    date: str
    message: str
    files: list[str]
    additions: int
    deletions: int
    diff_preview: str
    summary_text: str
    github_url: str = ""
