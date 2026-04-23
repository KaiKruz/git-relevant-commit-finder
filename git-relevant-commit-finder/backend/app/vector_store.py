"""ChromaDB initialization helpers."""

from chromadb import PersistentClient

from .config import get_settings

_client: PersistentClient | None = None


def get_chroma_client() -> PersistentClient:
    """Return a singleton persistent Chroma client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = PersistentClient(path=str(settings.absolute_vector_db_path))
    return _client


def get_commit_collection():
    """Return the default collection used to store commit embeddings."""
    client = get_chroma_client()
    return client.get_or_create_collection(name="commit_embeddings")
