from pathlib import Path
from typing import Callable, Optional, get_args

from wv.core.files import is_allowed_image_file
from wv.core.metadata import AvailableDetections, read_metadata, set_metadata
from wv.gui.detection_triage.state import DetectionTriageState


class DetectionTriageController:
    def __init__(
        self,
        input_path: Path,
        max_files_per_session: int = 0,
        include_detected: bool = False,
    ):
        self.state = DetectionTriageState()
        self._load_images(input_path, max_files_per_session, include_detected)

        self.on_change_side_effect: Optional[Callable[[], None]] = lambda: None
        self.on_complete_side_effect: Optional[Callable[[], None]] = lambda: None

    def _load_images(
        self, input_path: Path, max_files_per_session: int, include_detected: bool
    ):
        input_path = Path(input_path).resolve()
        if not input_path.is_dir():
            raise ValueError(f"Input path {input_path} is not a directory")

        all_images = sorted(
            [f for f in input_path.iterdir() if is_allowed_image_file(f)],
            reverse=True,
        )

        if not include_detected:
            filtered_images = []
            for img in all_images:
                metadata = read_metadata(img)

                if "Detection" not in metadata:
                    filtered_images.append(img)
                    if 0 < max_files_per_session <= len(filtered_images):
                        break

            self.state.images = filtered_images
        else:
            if len(all_images) > max_files_per_session > 0:
                all_images = all_images[:max_files_per_session]
            self.state.images = all_images

    def _rename_with_detection(self, image_path: Path, detection_value: str) -> None:
        image_path = Path(image_path)
        detection_value = detection_value.upper().strip()

        if not detection_value:
            raise ValueError("Detection value cannot be empty")

        # Expected:
        # 1) YYYYMMDD_HHMMSS__CAMERA_LOCATION
        # 2) YYYYMMDD_HHMMSS__CAMERA_LOCATION__DETECTION
        parts = image_path.stem.split("__", maxsplit=2)

        if len(parts) == 2:
            new_stem = f"{parts[0]}__{parts[1]}__{detection_value}"
        elif len(parts) == 3:
            new_stem = f"{parts[0]}__{parts[1]}__{detection_value}"
        else:
            raise ValueError(
                f"Unexpected filename format for '{image_path.name}'. "
                "Expected 'TIMESTAMP__CAMERA_LOCATION' or "
                "'TIMESTAMP__CAMERA_LOCATION__DETECTION'."
            )

        new_path = image_path.with_name(f"{new_stem}{image_path.suffix}")

        if new_path == image_path:
            return

        if new_path.exists():
            raise FileExistsError(f"Cannot rename: '{new_path.name}' already exists")

        image_path.rename(new_path)

        # Keep controller state in sync after rename
        try:
            idx = self.state.images.index(image_path)
            self.state.images[idx] = new_path
        except ValueError:
            pass

    def set_tag(self, tag_value: AvailableDetections):
        current_image = self.state.current_image
        if not current_image:
            return

        if tag_value not in get_args(AvailableDetections):
            raise ValueError(f"Invalid tag value: {tag_value}")

        set_metadata(current_image, "Detection", tag_value)
        self._rename_with_detection(current_image, tag_value)

        self.state.index += 1

        if self.state.is_completed and self.on_complete_side_effect:
            self.on_complete_side_effect()
        elif self.on_change_side_effect:
            self.on_change_side_effect()

    def next_image(self) -> None:
        if self.state.index < self.state.total_images - 1:
            self.state.index += 1
            if self.on_change_side_effect:
                self.on_change_side_effect()

    def previous_image(self) -> None:
        if self.state.index > 0:
            self.state.index -= 1
            if self.on_change_side_effect:
                self.on_change_side_effect()
