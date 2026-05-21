import imagehash
import shutil

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageFile, ImageFilter, ImageStat

from wv.core.files import is_allowed_image_file
from wv.core.files import parse_filename
from wv.core.images import get_datetime_from_image
from wv.core.logging import get_logger

ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass
class BurstReducerResult:
    total_files: int = 0
    total_bursts: int = 0
    kept_files: int = 0
    reduced_files: int = 0
    moved_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


@dataclass
class BurstFile:
    path: Path
    phash: imagehash.ImageHash | None
    quality: float


class BurstReducerHandler:
    def __init__(
        self,
        input_path: Path,
        burst_gap_threshold: int,
        similarity_threshold: int,
        output_path: Path,
    ):
        self.input_path = input_path
        self.burst_gap_threshold = burst_gap_threshold
        self.similarity_threshold = similarity_threshold
        self.output_path = output_path
        self.log = get_logger("BurstReducer")

    def run(self, dry_run: bool = False) -> BurstReducerResult:
        self.input_path = Path(self.input_path).resolve()
        self.output_path = Path(self.output_path).resolve()

        if not self.input_path.exists() or not self.input_path.is_dir():
            self.log.error(f"Input path does not exists: {self.input_path}")
            raise FileNotFoundError(self.input_path)

        if not dry_run:
            self.output_path.mkdir(parents=True, exist_ok=True)

        self.log.info(f"ANALYSING: {self.input_path}")

        result = BurstReducerResult()

        files = [
            f
            for f in sorted(self.input_path.iterdir())
            if f.is_file() and is_allowed_image_file(f)
        ]

        result.total_files = len(files)

        bursts = self._group_files_into_bursts(files)

        for burst in bursts:
            burst_files = self._extract_burst_files(burst, result)
            clusters = self._build_similarity_clusters(burst_files)

            for cluster in clusters:
                keep_amount = self._get_keep_amount(len(cluster))
                ranked_clusters = sorted(
                    cluster, key=lambda bf: bf.quality, reverse=True
                )

                for i, bf in enumerate(ranked_clusters):
                    if i < keep_amount:
                        result.kept_files += 1
                        continue

                    result.reduced_files += 1
                    destination = self.output_path / bf.path.name

                    if dry_run:
                        self.log.info(
                            f"DRY RUN: would move {bf.path.relative_to(self.input_path)} → {destination}"
                        )
                        continue

                    try:
                        shutil.move(str(bf.path), destination)
                        self.log.info(
                            f"MOVED: {bf.path.relative_to(self.input_path)} → {destination}"
                        )
                        result.moved_files += 1
                    except Exception as e:
                        result.failed_files += 1
                        self.log.error(f"Failed to move file {bf.path}: {e}")

            return result

    def _get_keep_amount(self, cluster_size: int) -> int:
        if cluster_size <= 2:
            return 1
        elif cluster_size <= 5:
            return 2

        return 3

    def _group_files_into_bursts(self, files: list[Path]) -> list[list[Path]]:
        if not files:
            return []

        scanned: list[tuple[str, datetime, Path]] = []

        for file in files:
            location = file.parent.name.upper()
            captured_at: datetime | None = None

            try:
                parsed = parse_filename(file)
                location = parsed.location.upper()
                captured_at = datetime.strptime(parsed.datetime, "%Y%m%d_%H%M%S")
            except Exception:
                pass

            if captured_at is None:
                core_datetime = get_datetime_from_image(file)
                if isinstance(core_datetime, datetime):
                    captured_at = core_datetime
                else:
                    captured_at = datetime.fromtimestamp(file.stat().st_mtime)

            scanned.append((location, captured_at, file))

        scanned.sort(key=lambda row: (row[0], row[1], str(row[2])))

        bursts: list[list[Path]] = []
        current_burst: list[Path] = []
        prev_location: str | None = None
        prev_datetime: datetime | None = None

        for location, captured_at, file in scanned:
            if not current_burst:
                current_burst = [file]
                prev_location = location
                prev_datetime = captured_at
                continue

            same_location = location == prev_location
            gap_seconds = (captured_at - prev_datetime).total_seconds()  # type: ignore[arg-type]

            if same_location and gap_seconds <= self.burst_gap_threshold:
                current_burst.append(file)
            else:
                bursts.append(current_burst)
                current_burst = [file]

            prev_location = location
            prev_datetime = captured_at

        if current_burst:
            bursts.append(current_burst)

        return bursts

    def _extract_burst_files(
        self, burst: list[Path], result: BurstReducerResult
    ) -> list[BurstFile]:
        burst_files: list[BurstFile] = []

        for file in burst:
            try:
                with Image.open(file) as img:
                    phash = imagehash.phash(img)
                    quality = self._estimate_image_quality(img)
                    burst_files.append(
                        BurstFile(path=file, phash=phash, quality=quality)
                    )
            except Exception as e:
                result.skipped_files += 1
                self.log.warning(f"Failed to process image {file}: {e}")
                burst_files.append(BurstFile(path=file, phash=None, quality=0.0))

        return burst_files

    def _estimate_image_quality(self, img: Image.Image) -> float:
        gray = img.convert("L")
        stats = ImageStat.Stat(gray)

        contrast = float(stats.stddev[0])  # Standard deviation as a measure of contrast
        mean_brightness = float(stats.mean[0])  # Mean pixel value as a proxy

        laplacian = gray.filter(
            ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)
        )

        sharpness_score = float(
            ImageStat.Stat(laplacian).var[0]
        )  # Variance of Laplacian as a measure of sharpness
        darkness_penalty = max(0.0, 55.0 - mean_brightness)

        return sharpness_score + contrast - darkness_penalty

    def _build_similarity_clusters(
        self, burst_files: list[BurstFile]
    ) -> list[list[BurstFile]]:

        if not burst_files:
            return []

        hashable_indexes = [
            i for i, bf in enumerate(burst_files) if bf.phash is not None
        ]
        unreadable_indexes = [i for i, bf in enumerate(burst_files) if bf.phash is None]

        adjacency: dict[int, set[int]] = {i: set() for i in hashable_indexes}

        for pos, i in enumerate(hashable_indexes):
            left_hash = burst_files[i].phash
            for j in hashable_indexes[pos + 1 :]:
                right_hash = burst_files[j].phash
                distance = abs(left_hash - right_hash)  # type: ignore[operator]
                if distance <= self.similarity_threshold:
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        clusters: list[list[BurstFile]] = []
        visited: set[int] = set()

        for start in hashable_indexes:
            if start in visited:
                continue

            stack = [start]
            visited.add(start)
            component_indexes: list[int] = []

            while stack:
                node = stack.pop()
                component_indexes.append(node)
                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

            clusters.append([burst_files[i] for i in component_indexes])

        for i in unreadable_indexes:
            clusters.append([burst_files[i]])

        return clusters
