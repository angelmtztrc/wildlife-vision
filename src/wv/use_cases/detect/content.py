from dataclasses import dataclass


@dataclass(frozen=True)
class DetectContentInput:
    pass


@dataclass(frozen=True)
class DetectContentResult:
    pass


def run(input_data: DetectContentInput) -> None:
    return None
