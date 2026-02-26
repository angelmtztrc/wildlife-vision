import shutil
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageStat, ImageFile


from wv.core.logging import get_logger
from wv.core.files import is_allowed_image_file

ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass
class OverexposedIRDetectorResult:
    total_files: int = 0
    overexposed_files: int = 0
    moved_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


@dataclass
class ImageMetrics:
    mean: float
    std: float
    pct_high: float


class OverexposedIRDetectorHandler:
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        mean_threshold: float,
        std_threshold: float,
        high_level: int,
        pct_high_threshold: float,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.mean_threshold = mean_threshold
        self.std_threshold = std_threshold
        self.high_level = high_level
        self.pct_high_threshold = pct_high_threshold
        self.log = get_logger("OverexposedIRDetector")

    def _compute_metrics(self, file_path: Path) -> ImageMetrics:
        with Image.open(file_path) as img:
            grayscale = img.convert("L")
            stats = ImageStat.Stat(grayscale)
            mean = float(stats.mean[0])
            std = float(stats.stddev[0])

            hist = grayscale.histogram()
            total_pixels = sum(hist)
            high_pixels = (
                sum(hist[self.high_level :]) if 0 <= self.high_level <= 255 else 0
            )
            pct_high = (high_pixels / total_pixels) if total_pixels > 0 else 0.0

        return ImageMetrics(mean=mean, std=std, pct_high=pct_high)

    def _format_pct(self, x: float) -> str:
        return f"{x*100:.1f}%"

    def _is_overexposed(self, metrics: ImageMetrics) -> bool:
        is_bright_and_uniform = (
            metrics.mean >= self.mean_threshold and metrics.std <= self.std_threshold
        )
        has_many_near_white_pixels = metrics.pct_high >= self.pct_high_threshold

        return is_bright_and_uniform or has_many_near_white_pixels

    def run(self, dry_run: bool = False) -> OverexposedIRDetectorResult:
        self.input_path = Path(self.input_path).resolve()
        self.output_path = Path(self.output_path).resolve()

        if not self.input_path.exists():
            self.log.error(f"Input path does not exist: {self.input_path}")
            raise FileNotFoundError(self.input_path)

        if not dry_run:
            self.output_path.mkdir(parents=True, exist_ok=True)

        self.log.info(f"ANALYSING: {self.input_path} for overexposure...")

        result = OverexposedIRDetectorResult()

        files = [
            p
            for p in sorted(self.input_path.iterdir())
            if p.is_file() and is_allowed_image_file(p)
        ]

        result.total_files = len(files)

        for file in files:
            relative_path = file.relative_to(self.input_path)
            try:
                metrics = self._compute_metrics(file)

                is_overexposed = self._is_overexposed(metrics)
                if is_overexposed:
                    self.log.info(
                        f"OVEREXPOSED: {relative_path} (mean={metrics.mean:.1f}, std={metrics.std:.1f}, pct_high={self._format_pct(metrics.pct_high)})"
                    )
                    result.overexposed_files += 1
                    if dry_run:
                        self.log.info(
                            f"DRY RUN: would move {relative_path} → {self.output_path}"
                        )
                    else:
                        new_file_path = self.output_path / file.name
                        shutil.move(str(file), new_file_path)
                        self.log.info(f"MOVED: {relative_path} → {new_file_path}")
                        result.moved_files += 1

            except Exception as e:
                result.failed_files += 1
                self.log.error(f"Failed to process file {relative_path}: {e}")

        result.skipped_files = sum(
            1
            for p in self.input_path.iterdir()
            if p.is_file() and not is_allowed_image_file(p)
        )

        return result
