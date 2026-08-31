from pathlib import Path

import wv.gui.review_detection_preview.controller as controller_module
from wv.gui.review_detection_preview.controller import build_controller
from wv.use_cases.session.review_detection_apply import (
    ApplyReviewDetectionItemResult,
    ApplyReviewDetectionResult,
)
from wv.use_cases.session.review_detection_preview_load import ReviewDetectionPreviewItem


def _item(path: Path, label: str = "animal", reviewed: bool = False) -> ReviewDetectionPreviewItem:
    return ReviewDetectionPreviewItem(
        image_id=path.stem,
        file_path=path,
        current_label=label,
        reviewed=reviewed,
        current_relative_path=f"detection/{label}/{path.name}",
    )


def test_verify_and_relabel_stage_decisions_and_advance_focus(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller("SESSION001", False, {"animal": 2})
    controller.replace_active_items(items, {"animal": 2})

    controller.verify_focused()
    assert controller.state.decisions_by_image_id["a"].target_label == "animal"
    assert controller.focused_item() is items[1]

    controller.relabel_focused("human")
    assert controller.state.decisions_by_image_id["b"].target_label == "human"
    assert controller.focused_item() is items[1]


def test_grid_navigation_and_label_cycle(tmp_path: Path):
    items = [_item(tmp_path / f"{index}.jpg") for index in range(4)]
    items.append(_item(tmp_path / "person.jpg", "human"))
    controller = build_controller("SESSION001", False, {"animal": 4, "human": 1})
    controller.replace_active_items(items[:4], {"animal": 4, "human": 1})

    controller.move_focus(1, 0)
    assert controller.focused_item() is items[3]
    controller.move_focus(-1, 1)
    assert controller.focused_item() is items[1]
    controller.cycle_label(1)
    assert controller.state.active_label == "human"
    controller.replace_active_items([items[4]], {"animal": 4, "human": 1})
    assert controller.focused_item() is items[4]


def test_successful_pending_save_removes_reviewed_items(tmp_path: Path, monkeypatch):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller("SESSION001", False, {"animal": 2})
    controller.replace_active_items(items, {"animal": 2})
    controller.verify_focused()

    monkeypatch.setattr(
        controller_module,
        "apply_review_detection",
        lambda input_data: ApplyReviewDetectionResult(
            files_reviewed=1,
            item_results=[
                ApplyReviewDetectionItemResult(
                    image_id="a",
                    original_path=items[0].file_path,
                    final_path=items[0].file_path,
                    source_label="animal",
                    target_label="animal",
                    moved=False,
                    success=True,
                )
            ],
        ),
    )

    controller.commit()

    assert not controller.state.decisions_by_image_id
    assert not controller.state.decisions_by_image_id


def test_successful_relabel_stays_visible_when_including_reviewed(tmp_path: Path, monkeypatch):
    item = _item(tmp_path / "a.jpg")
    controller = build_controller("SESSION001", True, {"animal": 1})
    controller.replace_active_items([item], {"animal": 1})
    controller.relabel_focused("human")
    monkeypatch.setattr(
        controller_module,
        "apply_review_detection",
        lambda input_data: ApplyReviewDetectionResult(
            files_reviewed=1,
            files_reassigned=1,
            files_moved=1,
            item_results=[
                ApplyReviewDetectionItemResult(
                    image_id="a",
                    original_path=item.file_path,
                    final_path=tmp_path / "human" / "a.jpg",
                    source_label="animal",
                    target_label="human",
                    moved=True,
                    success=True,
                )
            ],
        ),
    )

    controller.commit()

    assert not controller.state.decisions_by_image_id
