from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SqlSession

from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.models.monitoring_area import MonitoringAreaModel


class MonitoringAreaRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def create(self, area: MonitoringArea) -> MonitoringArea:
        model = MonitoringAreaModel(
            id=area.id,
            name=area.name,
            description=area.description,
            notes=area.notes,
        )
        self.sql_session.add(model)
        try:
            self.sql_session.flush()
        except IntegrityError as exc:
            self.sql_session.rollback()
            raise RecordAlreadyExistsError(f"Monitoring area already exists: {area.id}") from exc
        return _model_to_area(model)

    def list(self) -> list[MonitoringArea]:
        models = self.sql_session.scalars(
            select(MonitoringAreaModel).order_by(MonitoringAreaModel.id)
        ).all()
        return [_model_to_area(model) for model in models]

    def get(self, area_id: str) -> MonitoringArea:
        model = self.sql_session.get(MonitoringAreaModel, area_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring area not found: {area_id}")
        return _model_to_area(model)

    def update(self, area_id: str, updates: dict[str, str | None]) -> MonitoringArea:
        model = self.sql_session.get(MonitoringAreaModel, area_id)
        if model is None:
            raise RecordNotFoundError(f"Monitoring area not found: {area_id}")
        for column, value in updates.items():
            setattr(model, column, value)
        self.sql_session.flush()
        return _model_to_area(model)


def _model_to_area(model: MonitoringAreaModel) -> MonitoringArea:
    return MonitoringArea(
        id=model.id,
        name=model.name,
        description=model.description,
        notes=model.notes,
    )
