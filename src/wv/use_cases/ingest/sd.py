from dataclasses import dataclass


@dataclass(frozen=True)
class IngestSdInput:
    pass


@dataclass(frozen=True)
class IngestSdResult:
    pass


def run(input_data: IngestSdInput) -> None:
    return None
