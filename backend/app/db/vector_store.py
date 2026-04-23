"""
Vector store adapter.

Uses ChromaDB when available, with an in-process fallback for environments
where Chroma dependencies are not installed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.core.config import settings

try:  # pragma: no cover - exercised only when chromadb is installed
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:  # pragma: no cover - fallback path is primary in lightweight envs
    chromadb = None
    embedding_functions = None


TOKEN_RE = re.compile(r"[a-z0-9_./-]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text for fallback similarity."""
    return TOKEN_RE.findall((text or "").lower())


def _tf(text: str) -> Counter:
    """Term-frequency vector."""
    return Counter(_tokenize(text))


def _norm(vec: Counter) -> float:
    """L2 norm for sparse vector."""
    return math.sqrt(sum(v * v for v in vec.values()))


def _cosine(a: Counter, b: Counter, b_norm: float) -> float:
    """Cosine similarity for sparse vectors."""
    if not a or not b or b_norm == 0.0:
        return 0.0
    a_norm = _norm(a)
    if a_norm == 0.0:
        return 0.0
    dot = 0.0
    for key, value in a.items():
        dot += value * b.get(key, 0)
    return dot / (a_norm * b_norm)


def _where_match(metadata: dict, where: dict | None) -> bool:
    """Support simple Chroma-style $eq where filters used by this MVP."""
    if not where:
        return True
    if "$and" in where:
        return all(_where_match(metadata, clause) for clause in where["$and"])
    for field, condition in where.items():
        if isinstance(condition, dict) and "$eq" in condition:
            if metadata.get(field) != condition["$eq"]:
                return False
    return True


class _FallbackCollection:
    """Minimal in-memory collection compatible with required Chroma methods."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}

    def count(self) -> int:
        """Return total number of indexed documents."""
        return len(self._rows)

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        """Insert or update rows."""
        for idx, doc_id in enumerate(ids):
            doc = documents[idx] if idx < len(documents) else ""
            meta = metadatas[idx] if idx < len(metadatas) else {}
            tf = _tf(doc)
            self._rows[doc_id] = {
                "id": doc_id,
                "document": doc,
                "metadata": meta,
                "tf": tf,
                "norm": _norm(tf),
            }

    def get(self) -> dict[str, list]:
        """Return all rows."""
        ids = list(self._rows.keys())
        docs = [self._rows[i]["document"] for i in ids]
        metas = [self._rows[i]["metadata"] for i in ids]
        return {"ids": ids, "documents": docs, "metadatas": metas}

    def query(
        self,
        *,
        query_texts: list[str],
        n_results: int,
        where: dict | None = None,
    ) -> dict[str, list[list]]:
        """Query with cosine similarity over sparse token vectors."""
        query = query_texts[0] if query_texts else ""
        q_tf = _tf(query)

        scored: list[tuple[float, str]] = []
        for doc_id, row in self._rows.items():
            if not _where_match(row["metadata"], where):
                continue
            sim = _cosine(q_tf, row["tf"], row["norm"])
            scored.append((sim, doc_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[: max(1, n_results)]

        ids = [doc_id for _, doc_id in top]
        metas = [self._rows[i]["metadata"] for i in ids]
        docs = [self._rows[i]["document"] for i in ids]
        distances = [max(0.0, 1.0 - score) for score, _ in top]

        return {
            "ids": [ids],
            "metadatas": [metas],
            "documents": [docs],
            "distances": [distances],
        }


_fallback_collections: dict[str, _FallbackCollection] = {}
_client = None
_ef = None


def _get_fallback_collection(repo_id: str) -> _FallbackCollection:
    """Get or create fallback collection by repo."""
    name = f"repo_{repo_id}"
    if name not in _fallback_collections:
        _fallback_collections[name] = _FallbackCollection()
    return _fallback_collections[name]


def get_chroma_client():
    """Return persistent Chroma client when available."""
    global _client
    if chromadb is None:
        return None
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.vector_store_path)
    return _client


def get_embedding_function():
    """Return Chroma embedding function when available."""
    global _ef
    if embedding_functions is None:
        return None
    if _ef is None:
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
    return _ef


def get_collection(repo_id: str):
    """Get vector collection for a repository."""
    client = get_chroma_client()
    ef = get_embedding_function()
    if client is None or ef is None:
        return _get_fallback_collection(repo_id)
    return client.get_or_create_collection(
        name=f"repo_{repo_id}",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
