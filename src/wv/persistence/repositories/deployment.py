from sqlalchemy import select
from sqlalchemy.orm import Session

from wv.models import Deployment
from wv.persistence.models.deployment import DeploymentModel


class DeploymentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, deployment: Deployment) -> Deployment:
        model = DeploymentModel(
            id=deployment.id,
            device_id=deployment.device_id,
            monitoring_site_id=deployment.monitoring_site_id,
            sd_card_path=deployment.sd_card_path,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
        )
        self.session.add(model)
        self.session.flush()
        return _model_to_deployment(model)

    def list_for_device(self, device_id: str) -> list[Deployment]:
        models = self.session.scalars(
            select(DeploymentModel)
            .where(DeploymentModel.device_id == device_id)
            .order_by(DeploymentModel.created_at, DeploymentModel.id)
        ).all()
        return [_model_to_deployment(model) for model in models]

    def list_for_sd_card(self, sd_card_path: str) -> list[Deployment]:
        models = self.session.scalars(
            select(DeploymentModel)
            .where(DeploymentModel.sd_card_path == sd_card_path)
            .order_by(DeploymentModel.created_at, DeploymentModel.id)
        ).all()
        return [_model_to_deployment(model) for model in models]


def _model_to_deployment(model: DeploymentModel) -> Deployment:
    return Deployment(
        id=model.id,
        device_id=model.device_id,
        monitoring_site_id=model.monitoring_site_id,
        sd_card_path=model.sd_card_path,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
