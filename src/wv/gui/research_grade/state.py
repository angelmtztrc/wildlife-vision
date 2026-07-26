from dataclasses import dataclass, field
from pathlib import Path

from wv.use_cases.research_grade.load import ResearchGradeItem


@dataclass
class StagedResearchGradeDecision:
    research_grade: bool


@dataclass
class ResearchGradeSessionState:
    session_path: Path
    items: list[ResearchGradeItem]
    current_index: int = 0
    zoom_scale: float = 1.0
    decisions_by_path: dict[Path, StagedResearchGradeDecision] = field(
        default_factory=dict
    )
