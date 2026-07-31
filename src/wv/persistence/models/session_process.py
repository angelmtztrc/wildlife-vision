from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class SessionProcessModel(Base):
    __tablename__ = "session_processes"
    __table_args__ = (
        CheckConstraint(
            "process_name IN ('clean_corrupted', 'clean_overexposed_ir', 'clean_bursts', 'detect_content')",
            name="ck_session_processes_process_name",
        ),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'completed_with_failures', 'failed')",
            name="ck_session_processes_status",
        ),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id"), primary_key=True
    )
    process_name: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]
    attempt_count: Mapped[int]
    started_at: Mapped[str]
    completed_at: Mapped[str | None]
    failure_message: Mapped[str | None]
    parameters_json: Mapped[str | None]
    files_discovered: Mapped[int]
    files_processed: Mapped[int]
    files_selected: Mapped[int]
    files_moved: Mapped[int]
    files_ignored: Mapped[int]
    files_failed: Mapped[int]
