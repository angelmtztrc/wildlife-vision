from dataclasses import dataclass


@dataclass(frozen=True)
class PipelinePreprocessInput:
    pass


@dataclass(frozen=True)
class PipelinePreprocessResult:
    pass


def run(input_data: PipelinePreprocessInput) -> None:
    return None
