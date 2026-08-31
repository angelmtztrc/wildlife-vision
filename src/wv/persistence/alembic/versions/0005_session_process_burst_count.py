"""Add burst summary count to session processes.

Revision ID: 0005_session_process_burst_count
Revises: 0004_session_process_image_plans
Create Date: 2026-08-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_session_process_burst_count"
down_revision: str | None = "0004_session_process_image_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "session_processes",
        sa.Column("bursts_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("session_processes", "bursts_count")
