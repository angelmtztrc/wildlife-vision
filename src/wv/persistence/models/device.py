from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class DeviceModel(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    manufacturer: Mapped[str | None]
    serial_number: Mapped[str | None]
    notes: Mapped[str | None]
    monitoring_site_id: Mapped[str | None]
