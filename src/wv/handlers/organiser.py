import shutil
from dataclasses import dataclass, field
from pathlib import Path

from wv.core.logging import get_logger
from wv.core.files import allowed_image_exts
from wv.core.images import get_datetime_from_image


@dataclass
class PhotoOrganiserResult:
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


class PhotoOrganiserHandler:

    def __init__(self, input_path: Path, camera_location: str, output_path: Path):
        self.input_path = input_path
        self.camera_location = camera_location
        self.output_path = output_path
        self.log = get_logger("PhotoOrganiser")

    def run(self, dry_run: bool = False) -> None:
        self.input_path = Path(self.input_path).resolve()
        self.output_path = Path(self.output_path).resolve()

        if not self.input_path.exists():
            self.log.error(f"Input path does not exist: {self.input_path}")
            exit(1)

        self.log.info(f"Analysing files in {self.input_path}...")

        result = PhotoOrganiserResult()
        for file in self.input_path.iterdir():
            if file.suffix in allowed_image_exts:
                try:
                    captured_at = get_datetime_from_image(file)
                    date_str = captured_at.strftime("%Y%m%d")
                    time_str = captured_at.strftime("%H%M%S")

                    new_filename = f"{date_str}_{time_str}__{self.camera_location.upper()}{file.suffix.lower()}"
                    new_file_path = self.output_path / new_filename

                    if dry_run:
                        self.log.info(f"DRY RUN: would move {file} → {new_file_path}")
                    else:
                        shutil.move(str(file), new_file_path)
                        self.log.info(f"File moved: {file.name} → {new_file_path}")
                    result.processed_files += 1
                except Exception as e:
                    result.failed_files += 1
                    self.log.error(f"Failed to process file {file}: {e}")

            else:
                result.skipped_files += 1

        return result
