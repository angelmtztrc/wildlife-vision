from sqlalchemy import select
from sqlalchemy.orm import Session as SqlSession

from wv.models import SessionProcessImagePlan
from wv.persistence.common import RecordAlreadyExistsError
from wv.persistence.models.session_process_image_plan import SessionProcessImagePlanModel


class SessionProcessImagePlanRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def create_many(
        self, plans: list[SessionProcessImagePlan]
    ) -> list[SessionProcessImagePlan]:
        if not plans:
            return []

        session_id = plans[0].session_id
        process_name = plans[0].process_name
        if any(
            plan.session_id != session_id or plan.process_name != process_name
            for plan in plans
        ):
            raise ValueError("Session process image plans must share a process.")

        if self.list_for_process(session_id, process_name):
            raise RecordAlreadyExistsError(
                f"Session process image plan already exists: {session_id}/{process_name}"
            )

        models = [
            SessionProcessImagePlanModel(
                session_id=plan.session_id,
                process_name=plan.process_name,
                image_id=plan.image_id,
                decision=plan.decision,
                target_relative_path=plan.target_relative_path,
                planned_at=plan.planned_at,
            )
            for plan in plans
        ]
        self.sql_session.add_all(models)
        self.sql_session.flush()
        return [_model_to_session_process_image_plan(model) for model in models]

    def list_for_process(
        self, session_id: str, process_name: str
    ) -> list[SessionProcessImagePlan]:
        models = self.sql_session.scalars(
            select(SessionProcessImagePlanModel)
            .where(
                SessionProcessImagePlanModel.session_id == session_id,
                SessionProcessImagePlanModel.process_name == process_name,
            )
            .order_by(SessionProcessImagePlanModel.image_id)
        ).all()
        return [_model_to_session_process_image_plan(model) for model in models]


def _model_to_session_process_image_plan(
    model: SessionProcessImagePlanModel,
) -> SessionProcessImagePlan:
    return SessionProcessImagePlan(
        session_id=model.session_id,
        process_name=model.process_name,
        image_id=model.image_id,
        decision=model.decision,
        target_relative_path=model.target_relative_path,
        planned_at=model.planned_at,
    )
