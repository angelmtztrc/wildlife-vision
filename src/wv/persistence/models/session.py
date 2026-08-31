from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_monitoring_site_id", "monitoring_site_id"),
        Index("ix_sessions_ingest_status", "ingest_status"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    monitoring_site_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_sites.id"), nullable=False
    )
    source_path: Mapped[str]
    mode: Mapped[str]
    recursive: Mapped[bool]
    started_at: Mapped[str]
    completed_at: Mapped[str | None]
    ingest_status: Mapped[str]
    failure_message: Mapped[str | None]
    files_discovered: Mapped[int]
    files_copied: Mapped[int]
    files_deleted: Mapped[int]
    files_ignored: Mapped[int]
    files_failed: Mapped[int]
    files_replaced: Mapped[int]
