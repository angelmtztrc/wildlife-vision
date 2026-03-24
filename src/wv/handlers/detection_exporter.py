import os
from dataclasses import dataclass
from pathlib import Path

from wv.core.files import copy_file, is_allowed_image_file
from wv.core.metadata import AvailableDetections, get_detection_from_filename
from wv.core.logging import get_logger


@dataclass
class DetectionExporterResult:
    total_files: int = 0
    exported_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


class DetectionExporterHandler:
    def __init__(
        self, input_path: Path, target_detection: AvailableDetections, output_path: Path
    ):
        self.input_path = input_path
        self.target_detection = target_detection
        self.output_path = output_path
        self.log = get_logger("DetectionExporter")

    def run(self, dry_run: bool = False) -> DetectionExporterResult:
        result = DetectionExporterResult()

        if not self.input_path.exists() or not self.input_path.is_dir():
            self.log.error(
                f"Input path '{self.input_path}' does not exist or is not a directory."
            )
            raise FileNotFoundError(
                f"Input path '{self.input_path}' does not exist or is not a directory."
            )

        if not dry_run:
            self.output_path.mkdir(parents=True, exist_ok=True)

        self.log.info(
            f"ANALYSING: {self.input_path} for files with detection {self.target_detection}..."
        )

        files = [
            f
            for f in self.input_path.iterdir()
            if f.is_file() and is_allowed_image_file(f)
        ]

        result.total_files = len(files)

        for file in files:
            try:
                found_detection = get_detection_from_filename(file)
                if found_detection != self.target_detection:
                    result.skipped_files += 1
                    continue

                source_path = os.path.join(self.input_path, file)
                destination_path = os.path.join(self.output_path, file)

                if dry_run:
                    self.log.info(
                        f"DRY RUN: would export {source_path} → {destination_path}"
                    )

                else:
                    copy_file(source_path, destination_path)
                    result.exported_files += 1
            except Exception as e:
                result.failed_files += 1
                self.log.error(f"Failed to export file {file}: {e}")

        return result
