from dataclasses import dataclass


@dataclass(frozen=True)
class IngestFolderInput:
    pass


@dataclass(frozen=True)
class IngestFolderResult:
    pass


def run(input_data: IngestFolderInput) -> None:
    return None
