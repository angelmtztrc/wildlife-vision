from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class MonitoringSiteModel(Base):
    __tablename__ = "monitoring_sites"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None]
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    elevation: Mapped[float | None]
    notes: Mapped[str | None]
