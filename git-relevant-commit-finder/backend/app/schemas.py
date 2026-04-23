"""Pydantic schemas for API contract."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepoConnectRequest(BaseModel):
    """Request payload for connecting a repository."""

    source_type: Literal["github", "local"]
    source: str = Field(min_length=1)
    branch: str = Field(default="main", min_length=1)


class RepoConnectResponse(BaseModel):
    """Response payload after repository connect."""

    repo_id: int
    repo_name: str
    local_path: str
    branch: str


class RepoIndexRequest(BaseModel):
    """Request payload to start indexing."""

    repo_id: int


class RepoIndexResponse(BaseModel):
    """Response payload for index/refresh job creation."""

    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Response payload for job status polling."""

    status: str
    progress: int
    message: str


class SearchFilters(BaseModel):
    """Optional filters for semantic search."""

    author: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    path_contains: str | None = None
    branch: str | None = None


class SearchRequest(BaseModel):
    """Request payload for semantic search."""

    repo_id: int
    query: str = Field(min_length=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResultItem(BaseModel):
    """Single ranked search result."""

    sha: str
    author: str
    date: datetime
    summary: str
    score: float


class SearchResponse(BaseModel):
    """Semantic search response payload."""

    results: list[SearchResultItem]


class CommitDetailResponse(BaseModel):
    """Commit detail view payload."""

    sha: str
    author: str
    date: datetime
    message: str
    files_changed: list[str]
    diff_preview: str
    github_commit_url: str | None = None


class RepositoryOut(BaseModel):
    """Serialized repository row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source: str
    repo_name: str
    local_path: str
    branch: str


class IndexJobOut(BaseModel):
    """Serialized index job row."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    repo_id: int
    job_type: str
    status: str
    progress: int
    message: str
