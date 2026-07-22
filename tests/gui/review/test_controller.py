from pathlib import Path

from wv.gui.review.controller import build_controller
from wv.use_cases.review import ApplyReviewItemResult, ApplyReviewResult, ReviewItem
import wv.gui.review.controller as controller_module


def _item(path: Path, label: str = "animal", reviewed: bool = False) -> ReviewItem:
    return ReviewItem(file_path=path, original_label=label, reviewed=reviewed)


def test_assign_label_stages_decision_and_advances(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, "animal", items)

    controller.assign_label("human")

    assert controller.state.current_index == 1
    assert controller.state.decisions_by_path[items[0].file_path].target_label == "human"


def test_previous_and_next_stay_in_bounds(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, "animal", items)

    controller.previous_image()
    assert controller.state.current_index == 0

    controller.next_image()
    controller.next_image()
    assert controller.state.current_index == 1


def test_summary_counts_same_label_and_relabels(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, "animal", items)

    controller.assign_label("animal")
    controller.assign_label("human")

    summary = controller.summary()

    assert summary.staged_decisions == 2
    assert summary.same_label_reviews == 1
    assert summary.relabel_reviews == 1
    assert summary.move_count == 1
    assert summary.metadata_only_count == 1


def test_commit_clears_successful_staged_decisions_and_updates_items(
    tmp_path: Path,
    monkeypatch,
):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller(tmp_path, "animal", items)
    controller.assign_label("human")
    controller.assign_label("animal")

    monkeypatch.setattr(
        controller_module,
        "apply_review",
        lambda input_data: ApplyReviewResult(
            files_reviewed=1,
            files_reassigned=1,
            files_moved=1,
            files_failed=1,
            item_results=[
                ApplyReviewItemResult(
                    original_path=items[0].file_path,
                    final_path=tmp_path / "moved.jpg",
                    source_label="animal",
                    target_label="human",
                    moved=True,
                    replaced_existing=False,
                    success=True,
                ),
                ApplyReviewItemResult(
                    original_path=items[1].file_path,
                    final_path=items[1].file_path,
                    source_label="animal",
                    target_label="animal",
                    moved=False,
                    replaced_existing=False,
                    success=False,
                    failure="metadata write failed",
                ),
            ],
        ),
    )

    result = controller.commit()

    assert result.files_failed == 1
    assert items[0].file_path == tmp_path / "moved.jpg"
    assert items[0].original_label == "human"
    assert items[0].reviewed is True
    assert items[1].original_label == "animal"
    assert list(controller.state.decisions_by_path) == [items[1].file_path]
