from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SqlSession

from wv.models import MonitoringSite
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.models.monitoring_site import MonitoringSiteModel


class MonitoringSiteRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

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
        self.sql_session.add(model)

        try:
            self.sql_session.flush()
        except IntegrityError as exc:
            self.sql_session.rollback()
            raise RecordAlreadyExistsError(
                f"Monitoring site already exists: {monitoring_site.id}"
            ) from exc

        return _model_to_monitoring_site(model)

    def list(self) -> list[MonitoringSite]:
        models = self.sql_session.scalars(
            select(MonitoringSiteModel).order_by(MonitoringSiteModel.id)
        ).all()
        return [_model_to_monitoring_site(model) for model in models]

    def get(self, site_id: str) -> MonitoringSite:
        model = self.sql_session.get(MonitoringSiteModel, site_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring site not found: {site_id}")
        return _model_to_monitoring_site(model)

    def update(
        self, site_id: str, updates: dict[str, str | float | None]
    ) -> MonitoringSite:
        model = self.sql_session.get(MonitoringSiteModel, site_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring site not found: {site_id}")

        for column, value in updates.items():
            setattr(model, column, value)

        self.sql_session.flush()
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
