from dataclasses import dataclass, field
from wv.use_cases.session.review_detection_load import ReviewDetectionItem


@dataclass
class StagedDecision:
    target_label: str


@dataclass
class ReviewSessionState:
    session_id: str
    source_label: str
    items: list[ReviewDetectionItem]
    current_index: int = 0
    zoom_scale: float = 1.0
    decisions_by_image_id: dict[str, StagedDecision] = field(default_factory=dict)
