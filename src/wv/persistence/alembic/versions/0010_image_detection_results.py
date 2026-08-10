"""Store structured image detection results.

Revision ID: 0010_image_detection_results
Revises: 0009_rename_pct_high_parameter
Create Date: 2026-08-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_image_detection_results"
down_revision: str | None = "0009_rename_pct_high_parameter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_detection_results",
        sa.Column("image_id", sa.String(), sa.ForeignKey("session_images.id"), primary_key=True),
        sa.Column("predicted_label", sa.String(), nullable=False),
        sa.Column("predicted_confidence", sa.Float(), nullable=False),
        sa.Column("decision_source", sa.String(), nullable=False),
        sa.Column("megadetector_model", sa.String(), nullable=False),
        sa.Column("speciesnet_model", sa.String(), nullable=False),
        sa.Column("speciesnet_model_version", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("failure_message", sa.String(), nullable=True),
    )
    op.create_table(
        "image_object_detections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("image_id", sa.String(), sa.ForeignKey("image_detection_results.image_id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_width", sa.Float(), nullable=False),
        sa.Column("bbox_height", sa.Float(), nullable=False),
        sa.Column("final_taxon_id", sa.String(), nullable=True),
        sa.Column("final_taxon_rank", sa.String(), nullable=True),
        sa.Column("final_taxon_confidence", sa.Float(), nullable=True),
    )
    op.create_index("ix_image_object_detections_image_id", "image_object_detections", ["image_id"])
    op.create_index("ix_image_object_detections_category", "image_object_detections", ["category"])
    op.create_index("ix_image_object_detections_final_taxon_id", "image_object_detections", ["final_taxon_id"])
    op.create_table(
        "image_taxon_predictions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("object_detection_id", sa.String(), sa.ForeignKey("image_object_detections.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("taxon_id", sa.String(), nullable=False),
        sa.Column("taxon_class", sa.String(), nullable=True),
        sa.Column("taxon_order", sa.String(), nullable=True),
        sa.Column("taxon_family", sa.String(), nullable=True),
        sa.Column("taxon_genus", sa.String(), nullable=True),
        sa.Column("taxon_species", sa.String(), nullable=True),
        sa.Column("common_name", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.UniqueConstraint("object_detection_id", "rank", name="uq_image_taxon_predictions_detection_rank"),
    )
    op.create_index("ix_image_taxon_predictions_taxon_id", "image_taxon_predictions", ["taxon_id"])


def downgrade() -> None:
    op.drop_index("ix_image_taxon_predictions_taxon_id", table_name="image_taxon_predictions")
    op.drop_table("image_taxon_predictions")
    op.drop_index("ix_image_object_detections_final_taxon_id", table_name="image_object_detections")
    op.drop_index("ix_image_object_detections_category", table_name="image_object_detections")
    op.drop_index("ix_image_object_detections_image_id", table_name="image_object_detections")
    op.drop_table("image_object_detections")
    op.drop_table("image_detection_results")
