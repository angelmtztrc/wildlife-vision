from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class SessionImageModel(Base):
    __tablename__ = "session_images"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "initial_relative_path",
            name="uq_session_images_session_initial_path",
        ),
        Index("ix_session_images_session_id", "session_id"),
        Index("ix_session_images_session_state", "session_id", "state"),
        Index(
            "ix_session_images_session_current_path",
            "session_id",
            "current_relative_path",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    source_relative_path: Mapped[str]
    initial_relative_path: Mapped[str]
    current_relative_path: Mapped[str]
    state: Mapped[str]
    content_digest: Mapped[str]
    content_size_bytes: Mapped[int]
    captured_at: Mapped[str]
    ingested_at: Mapped[str]
    detection_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    favorite_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
