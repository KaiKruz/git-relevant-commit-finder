"""
Semantic search with lightweight heuristic reranking.
"""

from __future__ import annotations

import logging
import re

from app.db.vector_store import get_collection

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-z0-9_./-]+")


def _tokenize(text: str) -> set[str]:
    """Tokenize text for overlap scoring."""
    return {t for t in TOKEN_RE.findall((text or "").lower()) if len(t) >= 2}


def semantic_search(
    repo_id: str,
    query: str,
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    Search commits by embedding similarity and rerank with overlap boosts.
    Ranking rule:
    1) vector score primary
    2) filename overlap boost
    3) message overlap boost
    """
    collection = get_collection(repo_id)
    total_docs = collection.count()
    if total_docs == 0:
        return []

    where = None
    if filters and filters.get("author"):
        where = {"author_email": {"$eq": filters["author"]}}

    fetch_n = min(max(top_k * 5, top_k), total_docs)

    try:
        raw = collection.query(
            query_texts=[query],
            n_results=fetch_n,
            where=where,
        )
    except Exception as exc:  # pragma: no cover - chroma runtime error fallback
        logger.error("Search failed for repo %s: %s", repo_id, exc)
        return []

    ids = raw.get("ids", [[]])[0]
    if not ids:
        return []

    query_tokens = _tokenize(query)
    ranked: list[dict] = []

    for i, sha in enumerate(ids):
        meta = raw["metadatas"][0][i] or {}
        distance = float(raw["distances"][0][i] or 0.0)
        vector_score = max(0.0, 1.0 - distance)

        files = [f for f in (meta.get("files", "") or "").split(",") if f]
        commit_date = meta.get("date", "")

        if filters:
            from_date = filters.get("from_date")
            to_date = filters.get("to_date")
            path_contains = (filters.get("path_contains") or "").lower()

            if from_date and commit_date < from_date:
                continue
            if to_date and commit_date > to_date:
                continue
            if path_contains and not any(path_contains in f.lower() for f in files):
                continue

        files_blob = " ".join(files).lower()
        message = meta.get("message", "")
        message_tokens = _tokenize(message)

        filename_overlap = sum(1 for token in query_tokens if token in files_blob)
        message_overlap = len(query_tokens.intersection(message_tokens))

        filename_boost = min(0.18, filename_overlap * 0.03)
        message_boost = min(0.12, message_overlap * 0.02)
        rerank_score = vector_score + filename_boost + message_boost

        ranked.append(
            {
                "sha": sha,
                "short_sha": meta.get("short_sha", ""),
                "vector_score": round(vector_score, 4),
                "rerank_score": round(rerank_score, 4),
                "message": message,
                "author_name": meta.get("author_name", ""),
                "author_email": meta.get("author_email", ""),
                "date": commit_date,
                "files": files,
                "additions": int(meta.get("additions", 0)),
                "deletions": int(meta.get("deletions", 0)),
                "diff_preview": meta.get("diff_preview", ""),
            }
        )

    ranked.sort(key=lambda item: (item["rerank_score"], item["vector_score"]), reverse=True)
    final = ranked[:top_k]
    for idx, item in enumerate(final, start=1):
        item["rank"] = idx
    return final
