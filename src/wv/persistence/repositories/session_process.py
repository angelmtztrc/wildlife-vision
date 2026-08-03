from sqlalchemy.orm import Session as SqlSession

from wv.domain.session import SessionProcess
from wv.persistence.common import RecordNotFoundError
from wv.persistence.models.session_process import SessionProcessModel


class SessionProcessRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def get(self, session_id: str, process_name: str) -> SessionProcess:
        model = self.sql_session.get(SessionProcessModel, (session_id, process_name))
        if model is None:
            raise RecordNotFoundError(
                f"Session process not found: {session_id}/{process_name}"
            )
        return _model_to_session_process(model)

    def get_optional(self, session_id: str, process_name: str) -> SessionProcess | None:
        model = self.sql_session.get(SessionProcessModel, (session_id, process_name))
        return _model_to_session_process(model) if model is not None else None

    def start(
        self,
        session_id: str,
        process_name: str,
        started_at: str,
        parameters_json: str | None,
    ) -> SessionProcess:
        model = self.sql_session.get(SessionProcessModel, (session_id, process_name))
        if model is None:
            model = SessionProcessModel(
                session_id=session_id,
                process_name=process_name,
                status="in_progress",
                attempt_count=1,
                started_at=started_at,
                completed_at=None,
                failure_message=None,
                parameters_json=parameters_json,
                files_discovered=0,
                files_processed=0,
                files_selected=0,
                files_moved=0,
                files_ignored=0,
                files_failed=0,
                bursts_count=0,
                execution_details_json=None,
            )
            self.sql_session.add(model)
        else:
            model.status = "in_progress"
            model.attempt_count += 1
            model.started_at = started_at
            model.completed_at = None
            model.failure_message = None
            model.parameters_json = parameters_json
            model.files_discovered = 0
            model.files_processed = 0
            model.files_selected = 0
            model.files_moved = 0
            model.files_ignored = 0
            model.files_failed = 0
            model.bursts_count = 0

        self.sql_session.flush()
        return _model_to_session_process(model)

    def complete(
        self,
        session_id: str,
        process_name: str,
        *,
        status: str,
        completed_at: str,
        files_discovered: int,
        files_processed: int,
        files_selected: int,
        files_moved: int,
        files_ignored: int,
        files_failed: int,
        bursts_count: int = 0,
    ) -> SessionProcess:
        model = self._get_model(session_id, process_name)
        model.status = status
        model.completed_at = completed_at
        model.failure_message = None
        model.files_discovered = files_discovered
        model.files_processed = files_processed
        model.files_selected = files_selected
        model.files_moved = files_moved
        model.files_ignored = files_ignored
        model.files_failed = files_failed
        model.bursts_count = bursts_count
        self.sql_session.flush()
        return _model_to_session_process(model)

    def fail(
        self,
        session_id: str,
        process_name: str,
        *,
        completed_at: str,
        failure_message: str,
        files_discovered: int | None = None,
        files_processed: int | None = None,
        files_selected: int | None = None,
        files_moved: int | None = None,
        files_ignored: int | None = None,
        files_failed: int | None = None,
        bursts_count: int | None = None,
    ) -> SessionProcess:
        model = self._get_model(session_id, process_name)
        model.status = "failed"
        model.completed_at = completed_at
        model.failure_message = failure_message
        if files_discovered is not None:
            model.files_discovered = files_discovered
        if files_processed is not None:
            model.files_processed = files_processed
        if files_selected is not None:
            model.files_selected = files_selected
        if files_moved is not None:
            model.files_moved = files_moved
        if files_ignored is not None:
            model.files_ignored = files_ignored
        if files_failed is not None:
            model.files_failed = files_failed
        if bursts_count is not None:
            model.bursts_count = bursts_count
        self.sql_session.flush()
        return _model_to_session_process(model)

    def set_bursts_count(
        self, session_id: str, process_name: str, bursts_count: int
    ) -> SessionProcess:
        model = self._get_model(session_id, process_name)
        model.bursts_count = bursts_count
        self.sql_session.flush()
        return _model_to_session_process(model)

    def set_execution_details(
        self, session_id: str, process_name: str, execution_details_json: str
    ) -> SessionProcess:
        model = self._get_model(session_id, process_name)
        model.execution_details_json = execution_details_json
        self.sql_session.flush()
        return _model_to_session_process(model)

    def _get_model(self, session_id: str, process_name: str) -> SessionProcessModel:
        model = self.sql_session.get(SessionProcessModel, (session_id, process_name))
        if model is None:
            raise RecordNotFoundError(
                f"Session process not found: {session_id}/{process_name}"
            )
        return model


def _model_to_session_process(model: SessionProcessModel) -> SessionProcess:
    return SessionProcess(
        session_id=model.session_id,
        process_name=model.process_name,
        status=model.status,
        attempt_count=model.attempt_count,
        started_at=model.started_at,
        completed_at=model.completed_at,
        failure_message=model.failure_message,
        parameters_json=model.parameters_json,
        files_discovered=model.files_discovered,
        files_processed=model.files_processed,
        files_selected=model.files_selected,
        files_moved=model.files_moved,
        files_ignored=model.files_ignored,
        files_failed=model.files_failed,
        bursts_count=model.bursts_count,
        execution_details_json=model.execution_details_json,
    )
