from dataclasses import dataclass


@dataclass(frozen=True)
class CleanCorruptedInput:
    pass


@dataclass(frozen=True)
class CleanCorruptedResult:
    pass


def run(input_data: CleanCorruptedInput) -> None:
    return None
