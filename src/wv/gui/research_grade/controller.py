from dataclasses import dataclass
from pathlib import Path

from wv.gui.research_grade.state import (
    ResearchGradeSessionState,
    StagedResearchGradeDecision,
)
from wv.use_cases.research_grade.apply import (
    ApplyResearchGradeDecision,
    ApplyResearchGradeInput,
    ApplyResearchGradeResult,
    run as apply_research_grade,
)
from wv.use_cases.research_grade.load import ResearchGradeItem


@dataclass(frozen=True)
class ResearchGradeSummary:
    staged_decisions: int
    flagged_count: int
    unflagged_count: int


class ResearchGradeController:
    def __init__(self, state: ResearchGradeSessionState):
        self.state = state

    def current_item(self) -> ResearchGradeItem | None:
        if not self.state.items:
            return None

        self.state.current_index = max(
            0, min(self.state.current_index, len(self.state.items) - 1)
        )
        return self.state.items[self.state.current_index]

    def current_position(self) -> tuple[int, int]:
        if not self.state.items:
            return (0, 0)
        return (self.state.current_index + 1, len(self.state.items))

    def staged_decision_for(self, file_path: Path) -> StagedResearchGradeDecision | None:
        return self.state.decisions_by_path.get(file_path)

    def staged_research_grade_for_current(self) -> bool | None:
        item = self.current_item()
        if item is None:
            return None
        decision = self.staged_decision_for(item.file_path)
        return None if decision is None else decision.research_grade

    def has_unsaved_changes(self) -> bool:
        return bool(self.state.decisions_by_path)

    def flag_current(self) -> None:
        self._stage_current(True)

    def unflag_current(self) -> None:
        self._stage_current(False)

    def _stage_current(self, research_grade: bool) -> None:
        item = self.current_item()
        if item is None:
            return

        self.state.decisions_by_path[item.file_path] = StagedResearchGradeDecision(
            research_grade=research_grade
        )
        self.next_image()

    def skip_current(self) -> None:
        self.next_image()

    def next_image(self) -> None:
        if not self.state.items:
            return
        self.state.current_index = min(
            self.state.current_index + 1, len(self.state.items) - 1
        )

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

    def summary(self) -> ResearchGradeSummary:
        flagged_count = 0
        unflagged_count = 0

        for decision in self.state.decisions_by_path.values():
            if decision.research_grade:
                flagged_count += 1
            else:
                unflagged_count += 1

        return ResearchGradeSummary(
            staged_decisions=len(self.state.decisions_by_path),
            flagged_count=flagged_count,
            unflagged_count=unflagged_count,
        )

    def commit(self) -> ApplyResearchGradeResult:
        decisions = [
            ApplyResearchGradeDecision(
                file_path=item.file_path,
                research_grade=decision.research_grade,
            )
            for item in self.state.items
            for decision in [self.state.decisions_by_path.get(item.file_path)]
            if decision is not None
        ]

        result = apply_research_grade(
            ApplyResearchGradeInput(
                session_path=self.state.session_path,
                decisions=decisions,
            )
        )

        successful_values: dict[Path, bool] = {}
        for item_result in result.item_results:
            if item_result.success:
                successful_values[item_result.file_path] = item_result.research_grade

        for item in self.state.items:
            committed_value = successful_values.get(item.file_path)
            if committed_value is None:
                continue

            self.state.decisions_by_path.pop(item.file_path, None)
            item.research_grade = committed_value

        return result


def build_controller(
    session_path: Path, items: list[ResearchGradeItem]
) -> ResearchGradeController:
    return ResearchGradeController(
        ResearchGradeSessionState(session_path=session_path, items=items)
    )
