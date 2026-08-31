"""Reset workspace catalog for geography-first ingestion.

Revision ID: 0007_geography_first_reset
Revises: 0006_session_detection_plan_details
Create Date: 2026-08-08 00:00:00.000000

This intentionally destructive clean-break migration removes existing workspace
catalog, session, and deployment data. Existing workspaces must be recreated.
"""

from collections.abc import Sequence

from alembic import op
from alembic.util import CommandError
import sqlalchemy as sa

revision: str = "0007_geography_first_reset"
down_revision: str | None = "0006_session_detection_plan_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    populated_tables = [
        table
        for table in ("sessions", "devices", "monitoring_sites")
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    ]
    if populated_tables:
        raise CommandError(
            "0007 is a destructive clean-break migration and cannot upgrade a populated "
            "workspace. Back up and recreate the workspace before migrating. "
            f"Populated tables: {', '.join(populated_tables)}."
        )

    op.execute("DELETE FROM session_process_image_plans")
    op.execute("DELETE FROM session_processes")
    op.execute("DELETE FROM session_images")
    op.execute("DELETE FROM sessions")
    op.execute("DELETE FROM deployments")
    op.execute("DELETE FROM devices")
    op.execute("DELETE FROM monitoring_sites")

    op.create_table(
        "monitoring_areas",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.drop_table("deployments")

    with op.batch_alter_table("devices") as batch:
        batch.drop_column("monitoring_site_id")

    with op.batch_alter_table("monitoring_sites") as batch:
        batch.add_column(sa.Column("monitoring_area_id", sa.Text(), nullable=True))
        batch.alter_column("latitude", existing_type=sa.Float(), nullable=False)
        batch.alter_column("longitude", existing_type=sa.Float(), nullable=False)
        batch.create_foreign_key(
            "fk_monitoring_sites_area", "monitoring_areas", ["monitoring_area_id"], ["id"]
        )
        batch.create_check_constraint("ck_sites_latitude", "latitude >= -90 AND latitude <= 90")
        batch.create_check_constraint("ck_sites_longitude", "longitude >= -180 AND longitude <= 180")
        batch.create_index("ix_monitoring_sites_area_id", ["monitoring_area_id"])
        batch.alter_column("monitoring_area_id", nullable=False)

    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_device_id")
        batch.drop_column("device_id")
        batch.create_foreign_key(
            "fk_sessions_monitoring_site", "monitoring_sites", ["monitoring_site_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint("fk_sessions_monitoring_site", type_="foreignkey")
        batch.add_column(sa.Column("device_id", sa.Text(), nullable=False, server_default=""))
        batch.create_index("ix_sessions_device_id", ["device_id"])

    with op.batch_alter_table("monitoring_sites") as batch:
        batch.drop_constraint("fk_monitoring_sites_area", type_="foreignkey")
        batch.drop_constraint("ck_sites_latitude", type_="check")
        batch.drop_constraint("ck_sites_longitude", type_="check")
        batch.drop_index("ix_monitoring_sites_area_id")
        batch.drop_column("monitoring_area_id")
        batch.alter_column("latitude", existing_type=sa.Float(), nullable=True)
        batch.alter_column("longitude", existing_type=sa.Float(), nullable=True)

    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("monitoring_site_id", sa.Text(), nullable=True))

    op.create_table(
        "deployments",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("monitoring_site_id", sa.Text(), nullable=False),
        sa.Column("sd_card_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.drop_table("monitoring_areas")
