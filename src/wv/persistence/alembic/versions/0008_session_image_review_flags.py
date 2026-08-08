"""Add session image review and favorite flags.

Revision ID: 0008_session_image_review_flags
Revises: 0007_geography_first_reset
Create Date: 2026-08-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_session_image_review_flags"
down_revision: str | None = "0007_geography_first_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "session_images",
        sa.Column("detection_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "session_images",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "session_images",
        sa.Column("favorite_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("session_images", "favorite_reviewed")
    op.drop_column("session_images", "is_favorite")
    op.drop_column("session_images", "detection_reviewed")
