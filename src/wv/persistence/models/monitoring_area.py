from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class MonitoringAreaModel(Base):
    __tablename__ = "monitoring_areas"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None]
    notes: Mapped[str | None]
