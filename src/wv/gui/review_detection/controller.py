from dataclasses import dataclass
from pathlib import Path
from wv.gui.review_detection.state import ReviewSessionState, StagedDecision
from wv.use_cases.session.review_detection_apply import (
    ApplyReviewDetectionDecision,
    ApplyReviewDetectionInput,
    ApplyReviewDetectionResult,
    run as apply_review_detection,
)
from wv.use_cases.session.review_detection_load import ReviewDetectionItem


@dataclass(frozen=True)
class ReviewSummary:
    staged_decisions: int
    same_label_reviews: int
    relabel_reviews: int
    move_count: int
    metadata_only_count: int


class ReviewController:
    def __init__(self, state: ReviewSessionState):
        self.state = state

    def has_items(self) -> bool:
        return bool(self.state.items)

    def current_item(self) -> ReviewDetectionItem | None:
        if not self.state.items:
            return None

        self.state.current_index = max(0, min(self.state.current_index, len(self.state.items) - 1))
        return self.state.items[self.state.current_index]

    def current_position(self) -> tuple[int, int]:
        if not self.state.items:
            return (0, 0)
        return (self.state.current_index + 1, len(self.state.items))

    def staged_decision_for(self, image_id: str) -> StagedDecision | None:
        return self.state.decisions_by_image_id.get(image_id)

    def staged_label_for_current(self) -> str | None:
        item = self.current_item()
        if item is None:
            return None
        decision = self.staged_decision_for(item.image_id)
        return None if decision is None else decision.target_label

    def has_unsaved_changes(self) -> bool:
        return bool(self.state.decisions_by_image_id)

    def assign_label(self, target_label: str) -> None:
        item = self.current_item()
        if item is None:
            return

        self.state.decisions_by_image_id[item.image_id] = StagedDecision(target_label=target_label)
        self.next_image()

    def skip_current(self) -> None:
        self.next_image()

    def next_image(self) -> None:
        if not self.state.items:
            return
        self.state.current_index = min(self.state.current_index + 1, len(self.state.items) - 1)

    def previous_image(self) -> None:
        if not self.state.items:
            return
        self.state.current_index = max(self.state.current_index - 1, 0)

    def zoom_in(self) -> None:
        self.state.zoom_scale = min(self.state.zoom_scale * 1.25, 8.0)

    def zoom_out(self) -> None:
        self.state.zoom_scale = max(self.state.zoom_scale / 1.25, 0.1)

    def reset_zoom(self) -> None:
        self.state.zoom_scale = 1.0

    def summary(self) -> ReviewSummary:
        same_label_reviews = 0
        relabel_reviews = 0

        for item in self.state.items:
            decision = self.state.decisions_by_image_id.get(item.image_id)
            if decision is None:
                continue
            if decision.target_label == item.original_label:
                same_label_reviews += 1
            else:
                relabel_reviews += 1

        return ReviewSummary(
            staged_decisions=len(self.state.decisions_by_image_id),
            same_label_reviews=same_label_reviews,
            relabel_reviews=relabel_reviews,
            move_count=relabel_reviews,
            metadata_only_count=same_label_reviews,
        )

    def commit(self) -> ApplyReviewDetectionResult:
        decisions = [
            ApplyReviewDetectionDecision(
                image_id=item.image_id,
                source_label=item.original_label,
                target_label=decision.target_label,
            )
            for item in self.state.items
            for decision in [self.state.decisions_by_image_id.get(item.image_id)]
            if decision is not None
        ]

        result = apply_review_detection(
            ApplyReviewDetectionInput(session_id=self.state.session_id, decisions=decisions)
        )

        if not result.item_results:
            return result

        successful_paths: dict[str, Path] = {}
        for item_result in result.item_results:
            if not item_result.success:
                continue
            successful_paths[item_result.image_id] = item_result.final_path

        for item in self.state.items:
            new_path = successful_paths.get(item.image_id)
            if new_path is None:
                continue

            decision = self.state.decisions_by_image_id.pop(item.image_id, None)
            item.file_path = new_path
            if decision is not None:
                item.original_label = decision.target_label
            item.reviewed = True

        return result


def build_controller(
    session_id: str, source_label: str, items: list[ReviewDetectionItem]
) -> ReviewController:
    return ReviewController(
        ReviewSessionState(
            session_id=session_id,
            source_label=source_label,
            items=items,
        )
    )


__all__ = ["ReviewController", "ReviewSummary", "build_controller"]
