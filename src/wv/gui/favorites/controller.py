from dataclasses import dataclass
from wv.gui.favorites.state import (
    FavoriteSessionState,
    StagedFavoriteDecision,
)
from wv.use_cases.session.favorites_apply import (
    ApplyFavoriteDecision,
    ApplyFavoritesInput,
    ApplyFavoritesResult,
    run as apply_favorites,
)
from wv.use_cases.session.favorites_load import FavoriteItem


@dataclass(frozen=True)
class FavoriteSummary:
    staged_decisions: int
    favorited_count: int
    unfavorited_count: int


class FavoriteController:
    def __init__(self, state: FavoriteSessionState):
        self.state = state

    def current_item(self) -> FavoriteItem | None:
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

    def staged_decision_for(self, image_id: str) -> StagedFavoriteDecision | None:
        return self.state.decisions_by_image_id.get(image_id)

    def staged_favorite_for_current(self) -> bool | None:
        item = self.current_item()
        if item is None:
            return None
        decision = self.staged_decision_for(item.image_id)
        return None if decision is None else decision.is_favorite

    def has_unsaved_changes(self) -> bool:
        return bool(self.state.decisions_by_image_id)

    def favorite_current(self) -> None:
        self._stage_current(True)

    def unfavorite_current(self) -> None:
        self._stage_current(False)

    def _stage_current(self, is_favorite: bool) -> None:
        item = self.current_item()
        if item is None:
            return

        self.state.decisions_by_image_id[item.image_id] = StagedFavoriteDecision(
            is_favorite=is_favorite
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

    def summary(self) -> FavoriteSummary:
        favorited_count = 0
        unfavorited_count = 0

        for decision in self.state.decisions_by_image_id.values():
            if decision.is_favorite:
                favorited_count += 1
            else:
                unfavorited_count += 1

        return FavoriteSummary(
            staged_decisions=len(self.state.decisions_by_image_id),
            favorited_count=favorited_count,
            unfavorited_count=unfavorited_count,
        )

    def commit(self) -> ApplyFavoritesResult:
        decisions = [
            ApplyFavoriteDecision(
                image_id=item.image_id,
                is_favorite=decision.is_favorite,
            )
            for item in self.state.items
            for decision in [self.state.decisions_by_image_id.get(item.image_id)]
            if decision is not None
        ]

        result = apply_favorites(
            ApplyFavoritesInput(
                session_id=self.state.session_id,
                decisions=decisions,
            )
        )

        successful_values: dict[str, bool] = {}
        for item_result in result.item_results:
            if item_result.success:
                successful_values[item_result.image_id] = item_result.is_favorite

        for item in self.state.items:
            committed_value = successful_values.get(item.image_id)
            if committed_value is None:
                continue

            self.state.decisions_by_image_id.pop(item.image_id, None)
            item.is_favorite = committed_value
            item.reviewed = True

        return result


def build_controller(session_id: str, items: list[FavoriteItem]) -> FavoriteController:
    return FavoriteController(
        FavoriteSessionState(session_id=session_id, items=items)
    )
