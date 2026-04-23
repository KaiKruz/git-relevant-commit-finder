"""Embedding helpers using sentence-transformers."""

from sentence_transformers import SentenceTransformer

from .config import get_settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return a singleton embedding model instance."""
    global _model
    if _model is None:
        settings = get_settings()
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def embed_text(text: str) -> list[float]:
    """Generate an embedding for one text input."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple text inputs."""
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
