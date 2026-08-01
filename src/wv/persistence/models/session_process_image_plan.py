from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class SessionProcessImagePlanModel(Base):
    __tablename__ = "session_process_image_plans"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('keep', 'move')",
            name="ck_session_process_image_plans_decision",
        ),
        CheckConstraint(
            "(decision = 'keep' AND target_relative_path IS NULL) OR "
            "(decision = 'move' AND target_relative_path IS NOT NULL)",
            name="ck_session_process_image_plans_target",
        ),
        ForeignKeyConstraint(
            ["session_id", "process_name"],
            ["session_processes.session_id", "session_processes.process_name"],
        ),
        ForeignKeyConstraint(
            ["session_id", "image_id"],
            ["session_images.session_id", "session_images.id"],
        ),
        Index("ix_session_process_image_plans_image_id", "image_id"),
    )

    session_id: Mapped[str] = mapped_column(primary_key=True)
    process_name: Mapped[str] = mapped_column(primary_key=True)
    image_id: Mapped[str] = mapped_column(primary_key=True)
    decision: Mapped[str]
    target_relative_path: Mapped[str | None]
    planned_at: Mapped[str]
