from pathlib import Path

import wv.gui.research_grade.controller as controller_module
from wv.gui.research_grade.controller import build_controller
from wv.use_cases.research_grade.apply import (
    ApplyResearchGradeItemResult,
    ApplyResearchGradeResult,
)
from wv.use_cases.research_grade.load import ResearchGradeItem


def _item(path: Path, research_grade: bool | None = None) -> ResearchGradeItem:
    return ResearchGradeItem(file_path=path, research_grade=research_grade)


def test_flag_current_stages_decision_and_advances(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, items)

    controller.flag_current()

    assert controller.state.current_index == 1
    assert controller.state.decisions_by_path[items[0].file_path].research_grade is True


def test_unflag_current_stages_false(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg", research_grade=True)]
    controller = build_controller(tmp_path, items)

    controller.unflag_current()

    assert controller.state.decisions_by_path[items[0].file_path].research_grade is False


def test_summary_counts_flagged_and_unflagged(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, items)

    controller.flag_current()
    controller.unflag_current()

    summary = controller.summary()

    assert summary.staged_decisions == 2
    assert summary.flagged_count == 1
    assert summary.unflagged_count == 1


def test_commit_clears_successful_decisions_and_updates_items(
    tmp_path: Path, monkeypatch
):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, items)
    controller.flag_current()
    controller.unflag_current()

    monkeypatch.setattr(
        controller_module,
        "apply_research_grade",
        lambda input_data: ApplyResearchGradeResult(
            files_updated=1,
            files_flagged=1,
            files_failed=1,
            item_results=[
                ApplyResearchGradeItemResult(
                    file_path=items[0].file_path,
                    research_grade=True,
                    success=True,
                ),
                ApplyResearchGradeItemResult(
                    file_path=items[1].file_path,
                    research_grade=False,
                    success=False,
                    failure="metadata write failed",
                ),
            ],
        ),
    )

    result = controller.commit()

    assert result.files_failed == 1
    assert items[0].research_grade is True
    assert items[1].research_grade is None
    assert list(controller.state.decisions_by_path) == [items[1].file_path]
