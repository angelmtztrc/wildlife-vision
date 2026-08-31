from wv.persistence.common import PersistenceError


class MonitoringSiteError(ValueError):
    pass


def to_monitoring_site_error(exc: PersistenceError) -> MonitoringSiteError:
    return MonitoringSiteError(str(exc))
