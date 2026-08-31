"""Add immutable session process image plans.

Revision ID: 0004_session_process_image_plans
Revises: 0003_session_processes
Create Date: 2026-08-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_session_process_image_plans"
down_revision: str | None = "0003_session_processes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_process_image_plans",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("process_name", sa.Text(), nullable=False),
        sa.Column("image_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("target_relative_path", sa.Text(), nullable=True),
        sa.Column("planned_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('keep', 'move')",
            name="ck_session_process_image_plans_decision",
        ),
        sa.CheckConstraint(
            "(decision = 'keep' AND target_relative_path IS NULL) OR "
            "(decision = 'move' AND target_relative_path IS NOT NULL)",
            name="ck_session_process_image_plans_target",
        ),
        sa.ForeignKeyConstraint(["image_id"], ["session_images.id"]),
        sa.ForeignKeyConstraint(
            ["session_id", "process_name"],
            ["session_processes.session_id", "session_processes.process_name"],
        ),
        sa.PrimaryKeyConstraint("session_id", "process_name", "image_id"),
    )
    op.create_index(
        "ix_session_process_image_plans_image_id",
        "session_process_image_plans",
        ["image_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_process_image_plans_image_id",
        table_name="session_process_image_plans",
    )
    op.drop_table("session_process_image_plans")
