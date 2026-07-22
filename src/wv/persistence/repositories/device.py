from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wv.models import Device
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.models.device import DeviceModel


class DeviceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, device: Device) -> Device:
        model = DeviceModel(
            id=device.id,
            name=device.name,
            manufacturer=device.manufacturer,
            serial_number=device.serial_number,
            notes=device.notes,
            monitoring_site_id=device.monitoring_site_id,
        )
        self.session.add(model)

        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise RecordAlreadyExistsError(f"Device already exists: {device.id}") from exc

        return _model_to_device(model)

    def list(self) -> list[Device]:
        models = self.session.scalars(select(DeviceModel).order_by(DeviceModel.id)).all()
        return [_model_to_device(model) for model in models]

    def get(self, device_id: str) -> Device:
        model = self.session.get(DeviceModel, device_id)
        if model is None:
            raise RecordNotFoundError(f"Device not found: {device_id}")
        return _model_to_device(model)

    def update(self, device_id: str, updates: dict[str, str | None]) -> Device:
        model = self.session.get(DeviceModel, device_id)
        if model is None:
            raise RecordNotFoundError(f"Device not found: {device_id}")

        for column, value in updates.items():
            setattr(model, column, value)

        self.session.flush()
        return _model_to_device(model)


def _model_to_device(model: DeviceModel) -> Device:
    return Device(
        id=model.id,
        name=model.name,
        manufacturer=model.manufacturer,
        serial_number=model.serial_number,
        notes=model.notes,
        monitoring_site_id=model.monitoring_site_id,
    )
