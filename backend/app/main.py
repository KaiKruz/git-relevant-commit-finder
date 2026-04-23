"""
FastAPI entrypoint for Git Relevant Commit Finder.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import repos, search
from app.core.config import settings
from app.db.sqlite_store import init_db

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Git Relevant Commit Finder",
    description="Semantic search over git commit history.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos.router, prefix="/api", tags=["repo"])
app.include_router(search.router, prefix="/api", tags=["search"])


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize local SQLite metadata database."""
    init_db()


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
