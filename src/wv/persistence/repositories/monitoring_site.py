from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wv.models import MonitoringSite
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.models.monitoring_site import MonitoringSiteModel


class MonitoringSiteRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, monitoring_site: MonitoringSite) -> MonitoringSite:
        model = MonitoringSiteModel(
            id=monitoring_site.id,
            name=monitoring_site.name,
            description=monitoring_site.description,
            latitude=monitoring_site.latitude,
            longitude=monitoring_site.longitude,
            elevation=monitoring_site.elevation,
            notes=monitoring_site.notes,
        )
        self.session.add(model)

        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise RecordAlreadyExistsError(
                f"Monitoring site already exists: {monitoring_site.id}"
            ) from exc

        return _model_to_monitoring_site(model)

    def list(self) -> list[MonitoringSite]:
        models = self.session.scalars(
            select(MonitoringSiteModel).order_by(MonitoringSiteModel.id)
        ).all()
        return [_model_to_monitoring_site(model) for model in models]

    def get(self, site_id: str) -> MonitoringSite:
        model = self.session.get(MonitoringSiteModel, site_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring site not found: {site_id}")
        return _model_to_monitoring_site(model)

    def update(
        self, site_id: str, updates: dict[str, str | float | None]
    ) -> MonitoringSite:
        model = self.session.get(MonitoringSiteModel, site_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring site not found: {site_id}")

        for column, value in updates.items():
            setattr(model, column, value)

        self.session.flush()
        return _model_to_monitoring_site(model)


def _model_to_monitoring_site(model: MonitoringSiteModel) -> MonitoringSite:
    return MonitoringSite(
        id=model.id,
        name=model.name,
        description=model.description,
        latitude=model.latitude,
        longitude=model.longitude,
        elevation=model.elevation,
        notes=model.notes,
    )
