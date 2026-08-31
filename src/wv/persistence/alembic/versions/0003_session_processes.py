"""Add session process tracking.

Revision ID: 0003_session_processes
Revises: 0002_session_inventory
Create Date: 2026-07-31 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_session_processes"
down_revision: str | None = "0002_session_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_processes",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("process_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("files_discovered", sa.Integer(), nullable=False),
        sa.Column("files_processed", sa.Integer(), nullable=False),
        sa.Column("files_selected", sa.Integer(), nullable=False),
        sa.Column("files_moved", sa.Integer(), nullable=False),
        sa.Column("files_ignored", sa.Integer(), nullable=False),
        sa.Column("files_failed", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "process_name IN ('clean_corrupted', 'clean_overexposed_ir', 'clean_bursts', 'detect_content')",
            name="ck_session_processes_process_name",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'completed_with_failures', 'failed')",
            name="ck_session_processes_status",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("session_id", "process_name"),
    )


def downgrade() -> None:
    op.drop_table("session_processes")
