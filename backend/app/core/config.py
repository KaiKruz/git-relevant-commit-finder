"""
Application settings — loaded from environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Vector store
    vector_store_path: str = "./chroma_db"
    sqlite_db_path: str = "./app_meta.db"

    # Git repos
    repos_clone_dir: str = "./cloned_repos"
    repos_meta_file: str = "./repos_meta.json"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Ingestion limits
    max_diff_chars: int = 4000
    max_summary_diff_chars: int = 800
    max_commits: int = 500

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Logging
    log_level: str = "INFO"


settings = Settings()
