from wv.persistence.common import PersistenceError


class SdError(ValueError):
    pass


def to_sd_error(exc: PersistenceError | ValueError) -> SdError:
    return SdError(str(exc))
