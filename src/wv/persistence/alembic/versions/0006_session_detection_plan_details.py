"""Add detection plan details.

Revision ID: 0006_session_detection_plan_details
Revises: 0005_session_process_burst_count
Create Date: 2026-08-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_session_detection_plan_details"
down_revision: str | None = "0005_session_process_burst_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "session_processes",
        sa.Column("execution_details_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "session_process_image_plans",
        sa.Column("decision_details_json", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_session_process_image_plans_target",
        "session_process_image_plans",
        ["session_id", "process_name", "target_relative_path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_session_process_image_plans_target",
        table_name="session_process_image_plans",
    )
    op.drop_column("session_process_image_plans", "decision_details_json")
    op.drop_column("session_processes", "execution_details_json")
