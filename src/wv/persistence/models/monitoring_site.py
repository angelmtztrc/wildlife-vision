from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class MonitoringSiteModel(Base):
    __tablename__ = "monitoring_sites"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_sites_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_sites_longitude"),
        Index("ix_monitoring_sites_area_id", "monitoring_area_id"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    monitoring_area_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_areas.id"), nullable=False
    )
    name: Mapped[str]
    description: Mapped[str | None]
    latitude: Mapped[float]
    longitude: Mapped[float]
    elevation: Mapped[float | None]
    notes: Mapped[str | None]
