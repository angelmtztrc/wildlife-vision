from dataclasses import dataclass, field

from wv.use_cases.session.review_detection_preview_load import ReviewDetectionPreviewItem


@dataclass(frozen=True)
class StagedDecision:
    source_label: str
    target_label: str
    current_relative_path: str


@dataclass
class ReviewDetectionPreviewState:
    session_id: str
    include_reviewed: bool
    label_counts: dict[str, int]
    active_label: str
    active_items: list[ReviewDetectionPreviewItem] = field(default_factory=list)
    focused_image_id_by_label: dict[str, str] = field(default_factory=dict)
    decisions_by_image_id: dict[str, StagedDecision] = field(default_factory=dict)
