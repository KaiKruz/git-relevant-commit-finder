# API Contract - Git Relevant Commit Finder

Status: LOCKED
Locked on: 2026-04-23
Base path: `/api`
Content type: `application/json`

This contract is intentionally minimal and frozen for current MVP implementation.

## 1. Connect Repository

`POST /api/repo/connect`

Accepts:

```json
{
  "source_type": "github",
  "source": "https://github.com/org/repo.git",
  "branch": "main"
}
```

`source_type` must be `github` or `local`.

Returns:

```json
{
  "repo_id": "f31a9082",
  "repo_name": "repo",
  "local_path": "C:/path/to/local/clone",
  "branch": "main",
  "github_url": "https://github.com/org/repo",
  "status": "connected"
}
```

## 2. Start Indexing

`POST /api/repo/index`

Accepts:

```json
{
  "repo_id": "f31a9082"
}
```

Returns:

```json
{
  "job_id": "job_123",
  "status": "queued"
}
```

## 3. Job Status

`GET /api/status/{job_id}`

Returns:

```json
{
  "job_id": "job_123",
  "status": "running",
  "progress": 42,
  "message": "Indexing commits",
  "stats": {
    "indexed_commits": 210,
    "new_embeddings": 35,
    "total_commits": 210
  },
  "error": null
}
```

## 4. Search

`POST /api/search`

Accepts:

```json
{
  "repo_id": "f31a9082",
  "query": "when was auth refactored?",
  "top_k": 10,
  "filters": {
    "author": "dev@example.com",
    "from_date": "2025-01-01",
    "to_date": "2025-12-31",
    "path_contains": "backend/app",
    "branch": "main"
  }
}
```

Returns:

```json
{
  "repo_id": "f31a9082",
  "query": "when was auth refactored?",
  "total": 1,
  "results": [
    {
      "rank": 1,
      "sha": "2b4e61bf91fca4",
      "short_sha": "2b4e61b",
      "vector_score": 0.89,
      "rerank_score": 0.97,
      "message": "refactor(auth): split token validation service",
      "author_name": "Dev User",
      "author_email": "dev@example.com",
      "date": "2025-05-18T11:42:03+00:00",
      "files": ["backend/app/services/auth.py", "backend/app/api/login.py"],
      "additions": 124,
      "deletions": 52,
      "diff_preview": "diff --git a/backend/app/services/auth.py b/backend/app/services/auth.py ...",
      "github_url": "https://github.com/org/repo/commit/2b4e61bf91fca4"
    }
  ]
}
```

## 5. Commit Details

`GET /api/commit/{sha}?repo_id=f31a9082`

Returns:

```json
{
  "repo_id": "f31a9082",
  "sha": "2b4e61bf91fca4",
  "short_sha": "2b4e61b",
  "author_name": "Dev User",
  "author_email": "dev@example.com",
  "date": "2025-05-18T11:42:03+00:00",
  "message": "refactor(auth): split token validation service",
  "files": ["backend/app/services/auth.py", "backend/app/api/login.py"],
  "additions": 124,
  "deletions": 52,
  "diff_preview": "diff --git a/backend/app/services/auth.py b/backend/app/services/auth.py ...",
  "summary_text": "refactor(auth): split token validation service ...",
  "github_url": "https://github.com/org/repo/commit/2b4e61bf91fca4"
}
```

## 6. Refresh Repository

`POST /api/repo/refresh`

Accepts:

```json
{
  "repo_id": "f31a9082"
}
```

Returns:

```json
{
  "job_id": "job_124",
  "status": "queued"
}
```
