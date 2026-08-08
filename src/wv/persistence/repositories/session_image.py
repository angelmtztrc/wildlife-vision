from sqlalchemy import func, select
from sqlalchemy.orm import Session as SqlSession

from wv.domain.session import SessionImage, SessionImageStateCount
from wv.persistence.common import RecordNotFoundError
from wv.persistence.models.session_image import SessionImageModel


class SessionImageRepository:
    def __init__(self, sql_session: SqlSession):
        self.sql_session = sql_session

    def create_or_replace_by_initial_path(self, image: SessionImage) -> SessionImage:
        model = self.sql_session.scalar(
            select(SessionImageModel).where(
                SessionImageModel.session_id == image.session_id,
                SessionImageModel.initial_relative_path == image.initial_relative_path,
            )
        )

        if model is None:
            model = SessionImageModel(id=image.id, session_id=image.session_id)
            self.sql_session.add(model)

        model.source_relative_path = image.source_relative_path
        model.initial_relative_path = image.initial_relative_path
        model.current_relative_path = image.current_relative_path
        model.state = image.state
        model.content_digest = image.content_digest
        model.content_size_bytes = image.content_size_bytes
        model.captured_at = image.captured_at
        model.ingested_at = image.ingested_at

        self.sql_session.flush()
        return _model_to_session_image(model)

    def list_for_session(self, session_id: str) -> list[SessionImage]:
        models = self.sql_session.scalars(
            select(SessionImageModel)
            .where(SessionImageModel.session_id == session_id)
            .order_by(SessionImageModel.current_relative_path, SessionImageModel.id)
        ).all()
        return [_model_to_session_image(model) for model in models]

    def list_for_session_state(
        self,
        session_id: str,
        state: str,
        *,
        detection_reviewed: bool | None = None,
        favorite_reviewed: bool | None = None,
        favorites_only: bool = False,
    ) -> list[SessionImage]:
        statement = select(SessionImageModel).where(
            SessionImageModel.session_id == session_id,
            SessionImageModel.state == state,
        )
        if detection_reviewed is not None:
            statement = statement.where(
                SessionImageModel.detection_reviewed == detection_reviewed
            )
        if favorite_reviewed is not None:
            statement = statement.where(
                SessionImageModel.favorite_reviewed == favorite_reviewed
            )
        if favorites_only:
            statement = statement.where(SessionImageModel.is_favorite.is_(True))

        models = self.sql_session.scalars(
            statement.order_by(SessionImageModel.current_relative_path, SessionImageModel.id)
        ).all()
        return [_model_to_session_image(model) for model in models]

    def count_by_state_for_session(
        self, session_id: str
    ) -> list[SessionImageStateCount]:
        rows = self.sql_session.execute(
            select(SessionImageModel.state, func.count(SessionImageModel.id))
            .where(SessionImageModel.session_id == session_id)
            .group_by(SessionImageModel.state)
            .order_by(SessionImageModel.state)
        ).all()
        return [
            SessionImageStateCount(state=state, count=count) for state, count in rows
        ]

    def get(self, image_id: str) -> SessionImage:
        model = self.sql_session.get(SessionImageModel, image_id)
        if model is None:
            raise RecordNotFoundError(f"Session image not found: {image_id}")
        return _model_to_session_image(model)

    def relocate(
        self, image_id: str, current_relative_path: str, state: str
    ) -> SessionImage:
        model = self.sql_session.get(SessionImageModel, image_id)
        if model is None:
            raise RecordNotFoundError(f"Session image not found: {image_id}")

        model.current_relative_path = current_relative_path
        model.state = state
        self.sql_session.flush()
        return _model_to_session_image(model)

    def relocate_with_content(
        self,
        image_id: str,
        current_relative_path: str,
        state: str,
        content_digest: str,
        content_size_bytes: int,
    ) -> SessionImage:
        model = self.sql_session.get(SessionImageModel, image_id)
        if model is None:
            raise RecordNotFoundError(f"Session image not found: {image_id}")

        model.current_relative_path = current_relative_path
        model.state = state
        model.content_digest = content_digest
        model.content_size_bytes = content_size_bytes
        self.sql_session.flush()
        return _model_to_session_image(model)

    def mark_detection_reviewed(self, image_id: str) -> SessionImage:
        model = self._get_model(image_id)
        model.detection_reviewed = True
        self.sql_session.flush()
        return _model_to_session_image(model)

    def relocate_reviewed(
        self, image_id: str, current_relative_path: str, state: str
    ) -> SessionImage:
        model = self._get_model(image_id)
        model.current_relative_path = current_relative_path
        model.state = state
        model.detection_reviewed = True
        model.is_favorite = False
        model.favorite_reviewed = False
        self.sql_session.flush()
        return _model_to_session_image(model)

    def set_favorite(self, image_id: str, is_favorite: bool) -> SessionImage:
        model = self._get_model(image_id)
        model.is_favorite = is_favorite
        model.favorite_reviewed = True
        self.sql_session.flush()
        return _model_to_session_image(model)

    def _get_model(self, image_id: str) -> SessionImageModel:
        model = self.sql_session.get(SessionImageModel, image_id)
        if model is None:
            raise RecordNotFoundError(f"Session image not found: {image_id}")
        return model


def _model_to_session_image(model: SessionImageModel) -> SessionImage:
    return SessionImage(
        id=model.id,
        session_id=model.session_id,
        source_relative_path=model.source_relative_path,
        initial_relative_path=model.initial_relative_path,
        current_relative_path=model.current_relative_path,
        state=model.state,
        content_digest=model.content_digest,
        content_size_bytes=model.content_size_bytes,
        captured_at=model.captured_at,
        ingested_at=model.ingested_at,
        detection_reviewed=model.detection_reviewed,
        is_favorite=model.is_favorite,
        favorite_reviewed=model.favorite_reviewed,
    )
