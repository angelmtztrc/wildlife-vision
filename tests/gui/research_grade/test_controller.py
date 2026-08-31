from pathlib import Path

import wv.gui.favorites.controller as controller_module
from wv.gui.favorites.controller import build_controller
from wv.use_cases.session.favorites_apply import (
    ApplyFavoriteItemResult,
    ApplyFavoritesResult,
)
from wv.use_cases.session.favorites_load import FavoriteItem


def _item(path: Path, is_favorite: bool = False, reviewed: bool = False) -> FavoriteItem:
    return FavoriteItem(path.stem, path, is_favorite, reviewed)


def test_flag_current_stages_decision_and_advances(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller("SESSION001", items)

    controller.favorite_current()

    assert controller.state.current_index == 1
    assert controller.state.decisions_by_image_id[items[0].image_id].is_favorite is True


def test_unflag_current_stages_false(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg", is_favorite=True)]
    controller = build_controller("SESSION001", items)

    controller.unfavorite_current()

    assert controller.state.decisions_by_image_id[items[0].image_id].is_favorite is False


def test_summary_counts_flagged_and_unflagged(tmp_path: Path):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller("SESSION001", items)

    controller.favorite_current()
    controller.unfavorite_current()

    summary = controller.summary()

    assert summary.staged_decisions == 2
    assert summary.favorited_count == 1
    assert summary.unfavorited_count == 1


def test_commit_clears_successful_decisions_and_updates_items(
    tmp_path: Path, monkeypatch
):
    items = [_item(tmp_path / "a.jpg"), _item(tmp_path / "b.jpg")]
    controller = build_controller("SESSION001", items)
    controller.favorite_current()
    controller.unfavorite_current()

    monkeypatch.setattr(
        controller_module,
        "apply_favorites",
        lambda input_data: ApplyFavoritesResult(
            files_updated=1,
            files_favorited=1,
            files_failed=1,
            item_results=[
                ApplyFavoriteItemResult(
                    image_id=items[0].image_id,
                    file_path=items[0].file_path,
                    is_favorite=True,
                    success=True,
                ),
                ApplyFavoriteItemResult(
                    image_id=items[1].image_id,
                    file_path=items[1].file_path,
                    is_favorite=False,
                    success=False,
                    failure="metadata write failed",
                ),
            ],
        ),
    )

    result = controller.commit()

    assert result.files_failed == 1
    assert items[0].is_favorite is True
    assert items[1].is_favorite is False
    assert list(controller.state.decisions_by_image_id) == [items[1].image_id]
