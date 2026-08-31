"""Add session inventory.

Revision ID: 0002_session_inventory
Revises: 0001_initial_schema
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_session_inventory"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("monitoring_site_id", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("recursive", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("ingest_status", sa.Text(), nullable=False),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("files_discovered", sa.Integer(), nullable=False),
        sa.Column("files_copied", sa.Integer(), nullable=False),
        sa.Column("files_deleted", sa.Integer(), nullable=False),
        sa.Column("files_ignored", sa.Integer(), nullable=False),
        sa.Column("files_failed", sa.Integer(), nullable=False),
        sa.Column("files_replaced", sa.Integer(), nullable=False),
    )
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"])
    op.create_index("ix_sessions_monitoring_site_id", "sessions", ["monitoring_site_id"])
    op.create_index("ix_sessions_ingest_status", "sessions", ["ingest_status"])

    op.create_table(
        "session_images",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("source_relative_path", sa.Text(), nullable=False),
        sa.Column("initial_relative_path", sa.Text(), nullable=False),
        sa.Column("current_relative_path", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.Text(), nullable=False),
        sa.Column("content_size_bytes", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.UniqueConstraint(
            "session_id",
            "initial_relative_path",
            name="uq_session_images_session_initial_path",
        ),
    )
    op.create_index("ix_session_images_session_id", "session_images", ["session_id"])
    op.create_index(
        "ix_session_images_session_state",
        "session_images",
        ["session_id", "state"],
    )
    op.create_index(
        "ix_session_images_session_current_path",
        "session_images",
        ["session_id", "current_relative_path"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_images_session_current_path", table_name="session_images")
    op.drop_index("ix_session_images_session_state", table_name="session_images")
    op.drop_index("ix_session_images_session_id", table_name="session_images")
    op.drop_table("session_images")
    op.drop_index("ix_sessions_ingest_status", table_name="sessions")
    op.drop_index("ix_sessions_monitoring_site_id", table_name="sessions")
    op.drop_index("ix_sessions_device_id", table_name="sessions")
    op.drop_table("sessions")
