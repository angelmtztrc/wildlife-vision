from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DetectionTriageState:
    images: list[Path] = field(default_factory=list)
    index: int = 0

    @property
    def current_image(self) -> Optional[Path]:
        if not self.images:
            return None
        return self.images[self.index]

    @property
    def total_images(self) -> int:
        return len(self.images)

    @property
    def is_completed(self) -> bool:
        return self.index >= len(self.images)
