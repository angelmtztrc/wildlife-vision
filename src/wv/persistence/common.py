class PersistenceError(ValueError):
    pass


class RecordAlreadyExistsError(PersistenceError):
    pass


class RecordNotFoundError(PersistenceError):
    pass
