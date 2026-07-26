from wv.persistence.common import PersistenceError


class DeviceError(ValueError):
    pass


def to_device_error(exc: PersistenceError) -> DeviceError:
    return DeviceError(str(exc))
