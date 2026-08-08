from wv.persistence.common import PersistenceError


class MonitoringAreaError(ValueError):
    pass


def to_monitoring_area_error(exc: PersistenceError) -> MonitoringAreaError:
    return MonitoringAreaError(str(exc))
