from dataclasses import dataclass, field
from wv.use_cases.session.favorites_load import FavoriteItem


@dataclass
class StagedFavoriteDecision:
    is_favorite: bool


@dataclass
class FavoriteSessionState:
    session_id: str
    items: list[FavoriteItem]
    current_index: int = 0
    zoom_scale: float = 1.0
    decisions_by_image_id: dict[str, StagedFavoriteDecision] = field(
        default_factory=dict
    )
