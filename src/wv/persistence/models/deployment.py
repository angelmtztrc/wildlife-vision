from sqlalchemy.orm import Mapped, mapped_column

from wv.persistence.base import Base


class DeploymentModel(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(primary_key=True)
    device_id: Mapped[str]
    monitoring_site_id: Mapped[str]
    sd_card_path: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]
