from dataclasses import dataclass

from wv.core.session import DETECTION_LABELS
from wv.gui.review_detection_preview.state import ReviewDetectionPreviewState, StagedDecision
from wv.use_cases.session.review_detection_apply import (
    ApplyReviewDetectionDecision,
    ApplyReviewDetectionInput,
    ApplyReviewDetectionResult,
    run as apply_review_detection,
)
from wv.use_cases.session.review_detection_preview_load import ReviewDetectionPreviewItem

LABEL_ORDER = ("animal", "human", "vehicle", "domestic", "empty", "other")
LABEL_SHORTCUTS = dict(enumerate(LABEL_ORDER, start=1))


@dataclass(frozen=True)
class ReviewSummary:
    staged_decisions: int
    same_label_reviews: int
    relabel_reviews: int


class ReviewDetectionPreviewController:
    def __init__(self, state: ReviewDetectionPreviewState):
        self.state = state
        self._items_by_id: dict[str, ReviewDetectionPreviewItem] = {}
        self._positions_by_id: dict[str, int] = {}
        self._same_label_reviews = 0
        self._relabel_reviews = 0
        self._index_active_items()

    def active_items(self) -> list[ReviewDetectionPreviewItem]:
        return self.state.active_items

    def label_count(self, label: str) -> int:
        return self.state.label_counts.get(label, 0)

    def focused_item(self) -> ReviewDetectionPreviewItem | None:
        if not self.state.active_items:
            return None
        focused_id = self.state.focused_image_id_by_label.get(self.state.active_label)
        item = self._items_by_id.get(focused_id or "")
        if item is not None:
            return item
        item = self.state.active_items[0]
        self.state.focused_image_id_by_label[self.state.active_label] = item.image_id
        return item

    def focused_index(self) -> int | None:
        item = self.focused_item()
        return None if item is None else self._positions_by_id[item.image_id]

    def set_active_label(self, label: str) -> bool:
        if label not in DETECTION_LABELS:
            raise ValueError(f"Unknown detection label: {label}")
        if label == self.state.active_label:
            return False
        self.state.active_label = label
        self.state.active_items = []
        self._index_active_items()
        return True

    def cycle_label(self, direction: int) -> str:
        index = LABEL_ORDER.index(self.state.active_label)
        self.set_active_label(LABEL_ORDER[(index + direction) % len(LABEL_ORDER)])
        return self.state.active_label

    def replace_active_items(self, items: list[ReviewDetectionPreviewItem], label_counts: dict[str, int]) -> None:
        self.state.active_items = items
        self.state.label_counts = label_counts
        self._index_active_items()
        self.focused_item()

    def focus_item(self, image_id: str) -> tuple[str | None, str | None]:
        previous = self.state.focused_image_id_by_label.get(self.state.active_label)
        if image_id in self._items_by_id:
            self.state.focused_image_id_by_label[self.state.active_label] = image_id
        return previous, self.state.focused_image_id_by_label.get(self.state.active_label)

    def move_focus(self, row_delta: int, column_delta: int) -> tuple[str | None, str | None]:
        item = self.focused_item()
        if item is None:
            return None, None
        index = self._positions_by_id[item.image_id]
        row, column = divmod(index, 3)
        target_index = min(
            max(0, row + row_delta) * 3 + min(2, max(0, column + column_delta)),
            len(self.state.active_items) - 1,
        )
        return self.focus_item(self.state.active_items[target_index].image_id)

    def verify_focused(self) -> tuple[str | None, str | None]:
        item = self.focused_item()
        return (None, None) if item is None else self._stage(item, item.current_label)

    def relabel_focused(self, target_label: str) -> tuple[str | None, str | None]:
        if target_label not in DETECTION_LABELS:
            raise ValueError(f"Unknown detection label: {target_label}")
        item = self.focused_item()
        return (None, None) if item is None else self._stage(item, target_label)

    def staged_label_for(self, item: ReviewDetectionPreviewItem) -> str | None:
        decision = self.state.decisions_by_image_id.get(item.image_id)
        return None if decision is None else decision.target_label

    def has_unsaved_changes(self) -> bool:
        return bool(self.state.decisions_by_image_id)

    def summary(self) -> ReviewSummary:
        return ReviewSummary(
            staged_decisions=len(self.state.decisions_by_image_id),
            same_label_reviews=self._same_label_reviews,
            relabel_reviews=self._relabel_reviews,
        )

    def commit(self) -> ApplyReviewDetectionResult:
        decisions = [
            ApplyReviewDetectionDecision(
                image_id=image_id,
                source_label=decision.source_label,
                target_label=decision.target_label,
            )
            for image_id, decision in sorted(
                self.state.decisions_by_image_id.items(),
                key=lambda pair: (pair[1].current_relative_path, pair[0]),
            )
        ]
        result = apply_review_detection(
            ApplyReviewDetectionInput(session_id=self.state.session_id, decisions=decisions)
        )
        for item_result in result.item_results:
            if item_result.success:
                self.state.decisions_by_image_id.pop(item_result.image_id, None)
        self._recalculate_summary()
        return result

    def _stage(self, item: ReviewDetectionPreviewItem, target_label: str) -> tuple[str | None, str | None]:
        existing = self.state.decisions_by_image_id.get(item.image_id)
        if existing is not None:
            self._remove_summary(existing)
        decision = StagedDecision(
            source_label=item.current_label,
            target_label=target_label,
            current_relative_path=item.current_relative_path,
        )
        self.state.decisions_by_image_id[item.image_id] = decision
        self._add_summary(decision)
        index = self._positions_by_id[item.image_id]
        return self.focus_item(self.state.active_items[min(index + 1, len(self.state.active_items) - 1)].image_id)

    def _index_active_items(self) -> None:
        self._items_by_id = {item.image_id: item for item in self.state.active_items}
        self._positions_by_id = {item.image_id: index for index, item in enumerate(self.state.active_items)}

    def _add_summary(self, decision: StagedDecision) -> None:
        if decision.source_label == decision.target_label:
            self._same_label_reviews += 1
        else:
            self._relabel_reviews += 1

    def _remove_summary(self, decision: StagedDecision) -> None:
        if decision.source_label == decision.target_label:
            self._same_label_reviews -= 1
        else:
            self._relabel_reviews -= 1

    def _recalculate_summary(self) -> None:
        self._same_label_reviews = 0
        self._relabel_reviews = 0
        for decision in self.state.decisions_by_image_id.values():
            self._add_summary(decision)


def build_controller(
    session_id: str,
    include_reviewed: bool,
    label_counts: dict[str, int],
) -> ReviewDetectionPreviewController:
    active_label = next((label for label in LABEL_ORDER if label_counts.get(label)), LABEL_ORDER[0])
    return ReviewDetectionPreviewController(
        ReviewDetectionPreviewState(
            session_id=session_id,
            include_reviewed=include_reviewed,
            label_counts=label_counts,
            active_label=active_label,
        )
    )
