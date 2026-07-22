WORKSPACE_METADATA_DIRNAME = ".wv"
WORKSPACE_DATABASE_NAME = "database.sqlite"
WORKSPACE_CONFIG_NAME = "config.yml"
WORKSPACE_DIRECTORIES = ("sessions", "models", "exports")


class WorkspaceError(ValueError):
    pass
