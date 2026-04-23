"""
Search and commit detail endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import CommitDetailResponse, SearchRequest, SearchResponse
from app.services import ingestor, searcher

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def semantic_search(body: SearchRequest) -> SearchResponse:
    """Run semantic commit search with lightweight reranking."""
    repo = ingestor.get_repo_meta(body.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repo '{body.repo_id}' not found.")

    if repo.get("status") not in {"ready", "connected"}:
        raise HTTPException(status_code=409, detail="Repository is not ready for search.")

    filters = body.filters.model_dump(exclude_none=True) if body.filters else {}
    if filters.get("branch") and repo.get("branch") and filters["branch"] != repo["branch"]:
        return SearchResponse(repo_id=body.repo_id, query=body.query, total=0, results=[])

    results = searcher.semantic_search(
        repo_id=body.repo_id,
        query=body.query,
        top_k=body.top_k,
        filters=filters,
    )

    github_url = repo.get("github_url", "")
    for item in results:
        item["github_url"] = ingestor.github_commit_url(github_url, item["sha"])

    return SearchResponse(
        repo_id=body.repo_id,
        query=body.query,
        total=len(results),
        results=results,
    )


@router.get("/commit/{sha}", response_model=CommitDetailResponse)
async def commit_detail(sha: str, repo_id: str) -> CommitDetailResponse:
    """Return detailed information for one commit."""
    repo = ingestor.get_repo_meta(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repo '{repo_id}' not found.")

    detail = ingestor.get_commit_from_store(repo_id, sha)
    if detail is None:
        detail = ingestor.get_commit_detail(repo["local_path"], sha)
        if detail:
            ingestor.save_commits(repo_id, [detail])

    if detail is None:
        raise HTTPException(status_code=404, detail=f"Commit '{sha}' not found.")

    payload = {
        "repo_id": repo_id,
        "sha": detail["sha"],
        "short_sha": detail["short_sha"],
        "author_name": detail["author_name"],
        "author_email": detail["author_email"],
        "date": detail["date"],
        "message": detail["message"],
        "files": detail["files"],
        "additions": int(detail.get("additions", 0)),
        "deletions": int(detail.get("deletions", 0)),
        "diff_preview": detail.get("diff_preview", ""),
        "summary_text": detail.get("summary_text", ""),
        "github_url": ingestor.github_commit_url(repo.get("github_url", ""), detail["sha"]),
    }
    return CommitDetailResponse(**payload)
