from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SqlSession

from wv.domain.session import IngestSession
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.models.session import SessionModel


class SessionRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def create(self, session: IngestSession) -> IngestSession:
        model = SessionModel(
            id=session.id,
            device_id=session.device_id,
            monitoring_site_id=session.monitoring_site_id,
            source_path=session.source_path,
            mode=session.mode,
            recursive=session.recursive,
            started_at=session.started_at,
            completed_at=session.completed_at,
            ingest_status=session.ingest_status,
            failure_message=session.failure_message,
            files_discovered=session.files_discovered,
            files_copied=session.files_copied,
            files_deleted=session.files_deleted,
            files_ignored=session.files_ignored,
            files_failed=session.files_failed,
            files_replaced=session.files_replaced,
        )
        self.sql_session.add(model)

        try:
            self.sql_session.flush()
        except IntegrityError as exc:
            self.sql_session.rollback()
            raise RecordAlreadyExistsError(f"Session already exists: {session.id}") from exc

        return _model_to_session(model)

    def get(self, session_id: str) -> IngestSession:
        model = self.sql_session.get(SessionModel, session_id)
        if model is None:
            raise RecordNotFoundError(f"Session not found: {session_id}")
        return _model_to_session(model)

    def list(self) -> list[IngestSession]:
        models = self.sql_session.scalars(
            select(SessionModel).order_by(SessionModel.started_at, SessionModel.id)
        ).all()
        return [_model_to_session(model) for model in models]

    def update(
        self, session_id: str, updates: dict[str, str | int | bool | None]
    ) -> IngestSession:
        model = self.sql_session.get(SessionModel, session_id)
        if model is None:
            raise RecordNotFoundError(f"Session not found: {session_id}")

        for column, value in updates.items():
            setattr(model, column, value)

        self.sql_session.flush()
        return _model_to_session(model)


def _model_to_session(model: SessionModel) -> IngestSession:
    return IngestSession(
        id=model.id,
        device_id=model.device_id,
        monitoring_site_id=model.monitoring_site_id,
        source_path=model.source_path,
        mode=model.mode,
        recursive=model.recursive,
        started_at=model.started_at,
        completed_at=model.completed_at,
        ingest_status=model.ingest_status,
        failure_message=model.failure_message,
        files_discovered=model.files_discovered,
        files_copied=model.files_copied,
        files_deleted=model.files_deleted,
        files_ignored=model.files_ignored,
        files_failed=model.files_failed,
        files_replaced=model.files_replaced,
    )
