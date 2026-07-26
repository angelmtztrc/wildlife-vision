from dataclasses import dataclass, field
from pathlib import Path

from wv.use_cases.review.load import ReviewItem


@dataclass
class StagedDecision:
    target_label: str


@dataclass
class ReviewSessionState:
    session_path: Path
    source_label: str
    items: list[ReviewItem]
    current_index: int = 0
    zoom_scale: float = 1.0
    decisions_by_path: dict[Path, StagedDecision] = field(default_factory=dict)
