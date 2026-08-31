from sqlalchemy import Boolean, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class SessionImageModel(Base):
    __tablename__ = "session_images"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "initial_relative_path",
            name="uq_session_images_session_initial_path",
        ),
        Index("ix_session_images_session_id", "session_id"),
        Index("ix_session_images_session_state", "session_id", "state"),
        Index(
            "ix_session_images_session_current_path",
            "session_id",
            "current_relative_path",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    source_relative_path: Mapped[str]
    initial_relative_path: Mapped[str]
    current_relative_path: Mapped[str]
    state: Mapped[str]
    content_digest: Mapped[str]
    content_size_bytes: Mapped[int]
    captured_at: Mapped[str]
    ingested_at: Mapped[str]
    detection_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    favorite_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ImageDetectionResultModel(Base):
    __tablename__ = "image_detection_results"

    image_id: Mapped[str] = mapped_column(ForeignKey("session_images.id"), primary_key=True)
    predicted_label: Mapped[str]
    predicted_confidence: Mapped[float] = mapped_column(Float)
    decision_source: Mapped[str]
    megadetector_model: Mapped[str]
    speciesnet_model: Mapped[str]
    speciesnet_model_version: Mapped[str | None]
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    failure_message: Mapped[str | None]


class ImageObjectDetectionModel(Base):
    __tablename__ = "image_object_detections"
    __table_args__ = (
        Index("ix_image_object_detections_image_id", "image_id"),
        Index("ix_image_object_detections_category", "category"),
        Index("ix_image_object_detections_final_taxon_id", "final_taxon_id"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    image_id: Mapped[str] = mapped_column(ForeignKey("image_detection_results.image_id"), nullable=False)
    category: Mapped[str]
    confidence: Mapped[float] = mapped_column(Float)
    bbox_x: Mapped[float] = mapped_column(Float)
    bbox_y: Mapped[float] = mapped_column(Float)
    bbox_width: Mapped[float] = mapped_column(Float)
    bbox_height: Mapped[float] = mapped_column(Float)
    final_taxon_id: Mapped[str | None]
    final_taxon_rank: Mapped[str | None]
    final_taxon_confidence: Mapped[float | None] = mapped_column(Float)


class ImageTaxonPredictionModel(Base):
    __tablename__ = "image_taxon_predictions"
    __table_args__ = (
        UniqueConstraint("object_detection_id", "rank", name="uq_image_taxon_predictions_detection_rank"),
        Index("ix_image_taxon_predictions_taxon_id", "taxon_id"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    object_detection_id: Mapped[str] = mapped_column(ForeignKey("image_object_detections.id"), nullable=False)
    rank: Mapped[int]
    taxon_id: Mapped[str]
    taxon_class: Mapped[str | None]
    taxon_order: Mapped[str | None]
    taxon_family: Mapped[str | None]
    taxon_genus: Mapped[str | None]
    taxon_species: Mapped[str | None]
    common_name: Mapped[str | None]
    confidence: Mapped[float] = mapped_column(Float)
