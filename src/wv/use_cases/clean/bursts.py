import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import imagehash
from PIL import Image, ImageFilter, ImageStat

from wv.core.files import (
    ensure_directory,
    is_allowed_image_file,
    parse_ingested_image_filename,
)
from wv.core.images import get_image_datetime


@dataclass(frozen=True)
class CleanBurstsInput:
    source: Path
    output: Path
    burst_gap_threshold: int
    similarity_threshold: int
    dry_run: bool = False


@dataclass
class CleanBurstsResult:
    files_discovered: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_bursts: int = 0
    files_reduced: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass(frozen=True)
class ScannedImage:
    path: Path
    monitoring_site: str
    captured_at: datetime


@dataclass(frozen=True)
class BurstImage:
    path: Path
    phash: imagehash.ImageHash | None
    quality: float


def _scan_image(file_path: Path) -> ScannedImage:
    filename_parts = parse_ingested_image_filename(file_path)

    if filename_parts is not None:
        monitoring_site = filename_parts["monitoring_site"].upper()
        captured_at = datetime.strptime(
            filename_parts["captured_at"], "%Y%m%d_%H%M%S"
        )
    else:
        monitoring_site = file_path.parent.name.upper()
        captured_at = get_image_datetime(file_path)

    return ScannedImage(
        path=file_path,
        monitoring_site=monitoring_site,
        captured_at=captured_at,
    )


def _group_files_into_bursts(
    scanned_images: list[ScannedImage], burst_gap_threshold: int
) -> list[list[ScannedImage]]:
    if not scanned_images:
        return []

    bursts: list[list[ScannedImage]] = []
    current_burst = [scanned_images[0]]

    for scanned_image in scanned_images[1:]:
        previous_image = current_burst[-1]
        gap_seconds = (
            scanned_image.captured_at - previous_image.captured_at
        ).total_seconds()

        if (
            scanned_image.monitoring_site == previous_image.monitoring_site
            and gap_seconds <= burst_gap_threshold
        ):
            current_burst.append(scanned_image)
            continue

        bursts.append(current_burst)
        current_burst = [scanned_image]

    bursts.append(current_burst)

    return bursts


def _estimate_image_quality(image: Image.Image) -> float:
    grayscale = image.convert("L")
    grayscale_stats = ImageStat.Stat(grayscale)

    contrast = float(grayscale_stats.stddev[0])
    mean_brightness = float(grayscale_stats.mean[0])
    laplacian = grayscale.filter(
        ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)
    )
    sharpness = float(ImageStat.Stat(laplacian).var[0])
    darkness_penalty = max(0.0, 55.0 - mean_brightness)

    return sharpness + contrast - darkness_penalty


def _build_burst_images(
    burst: list[ScannedImage], result: CleanBurstsResult
) -> list[BurstImage]:
    burst_images: list[BurstImage] = []

    for scanned_image in burst:
        try:
            with Image.open(scanned_image.path) as image:
                burst_images.append(
                    BurstImage(
                        path=scanned_image.path,
                        phash=imagehash.phash(image),
                        quality=_estimate_image_quality(image),
                    )
                )
        except Exception:
            result.files_failed += 1
            burst_images.append(
                BurstImage(path=scanned_image.path, phash=None, quality=0.0)
            )

    return burst_images


def _build_similarity_clusters(
    burst_images: list[BurstImage], similarity_threshold: int
) -> list[list[BurstImage]]:
    if not burst_images:
        return []

    hashable_indexes = [
        index for index, burst_image in enumerate(burst_images) if burst_image.phash is not None
    ]
    unreadable_indexes = [
        index for index, burst_image in enumerate(burst_images) if burst_image.phash is None
    ]
    adjacency: dict[int, set[int]] = {index: set() for index in hashable_indexes}

    for position, left_index in enumerate(hashable_indexes):
        left_hash = burst_images[left_index].phash

        for right_index in hashable_indexes[position + 1 :]:
            right_hash = burst_images[right_index].phash
            if abs(left_hash - right_hash) <= similarity_threshold:  # type: ignore[operator]
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)

    clusters: list[list[BurstImage]] = []
    visited: set[int] = set()

    for start_index in hashable_indexes:
        if start_index in visited:
            continue

        stack = [start_index]
        visited.add(start_index)
        component_indexes: list[int] = []

        while stack:
            current_index = stack.pop()
            component_indexes.append(current_index)

            for neighbor_index in adjacency[current_index]:
                if neighbor_index not in visited:
                    visited.add(neighbor_index)
                    stack.append(neighbor_index)

        clusters.append([burst_images[index] for index in component_indexes])

    for unreadable_index in unreadable_indexes:
        clusters.append([burst_images[unreadable_index]])

    return clusters


def _get_keep_amount(cluster_size: int) -> int:
    if cluster_size <= 5:
        return 1
    if cluster_size <= 20:
        return 2

    return 3


def run(input_data: CleanBurstsInput) -> CleanBurstsResult:
    destination = input_data.output / "ignored" / "bursts"
    result = CleanBurstsResult(destination=destination, dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())
    result.files_discovered = len(source_files)

    scanned_images: list[ScannedImage] = []

    for file_path in source_files:
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        try:
            scanned_images.append(_scan_image(file_path))
        except Exception:
            result.files_failed += 1

    scanned_images.sort(
        key=lambda scanned_image: (
            scanned_image.monitoring_site,
            scanned_image.captured_at,
            str(scanned_image.path),
        )
    )

    bursts = _group_files_into_bursts(
        scanned_images=scanned_images,
        burst_gap_threshold=input_data.burst_gap_threshold,
    )
    result.files_bursts = sum(1 for burst in bursts if len(burst) > 1)

    for burst in bursts:
        burst_images = _build_burst_images(burst=burst, result=result)
        clusters = _build_similarity_clusters(
            burst_images=burst_images,
            similarity_threshold=input_data.similarity_threshold,
        )

        for cluster in clusters:
            ranked_cluster = sorted(cluster, key=lambda burst_image: burst_image.quality, reverse=True)
            keep_amount = _get_keep_amount(len(ranked_cluster))

            for index, burst_image in enumerate(ranked_cluster):
                if index < keep_amount:
                    result.files_ignored += 1
                    continue

                result.files_reduced += 1

                if input_data.dry_run:
                    continue

                try:
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(burst_image.path), destination / burst_image.path.name)
                    result.files_moved += 1
                except Exception:
                    result.files_failed += 1

    return result
