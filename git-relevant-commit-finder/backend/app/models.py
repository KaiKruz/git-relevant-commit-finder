"""SQLAlchemy models for repository indexing and search."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Repository(Base):
    """Tracked git repository metadata."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    github_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_indexed_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    commits: Mapped[list["CommitRecord"]] = relationship("CommitRecord", back_populates="repository")
    index_jobs: Mapped[list["IndexJob"]] = relationship("IndexJob", back_populates="repository")


class CommitRecord(Base):
    """Indexed commit metadata used for search and details."""

    __tablename__ = "commit_records"
    __table_args__ = (UniqueConstraint("repo_id", "sha", name="uq_commit_repo_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), index=True, nullable=False)
    sha: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    author: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    files_changed: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    compact_diff_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diff_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    branch: Mapped[str] = mapped_column(String(255), index=True, nullable=False, default="main")
    github_commit_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="commits")


class IndexJob(Base):
    """Background-like indexing job state for UI polling."""

    __tablename__ = "index_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False, default="index")
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="index_jobs")
