"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Git Relevant Commit Finder"
    api_prefix: str = "/api"
    db_path: str = "data/app.db"
    repo_clone_dir: str = "repos"
    vector_db_path: str = "data/chroma_db"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def backend_root(self) -> Path:
        """Return the backend directory as an absolute path."""
        return Path(__file__).resolve().parents[1]

    @property
    def absolute_db_path(self) -> Path:
        """Return the SQLite file location."""
        return (self.backend_root / self.db_path).resolve()

    @property
    def absolute_repo_clone_dir(self) -> Path:
        """Return the local clone directory location."""
        return (self.backend_root / self.repo_clone_dir).resolve()

    @property
    def absolute_vector_db_path(self) -> Path:
        """Return the Chroma persistence directory."""
        return (self.backend_root / self.vector_db_path).resolve()

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy SQLite URL from file path."""
        sqlite_path = self.absolute_db_path.as_posix()
        return f"sqlite:///{sqlite_path}"

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        self.absolute_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.absolute_repo_clone_dir.mkdir(parents=True, exist_ok=True)
        self.absolute_vector_db_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
