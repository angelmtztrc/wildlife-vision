"""Deterministic, filesystem-free burst-reduction planning helpers."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import imagehash
from PIL import Image, ImageFilter, ImageOps, ImageStat

from wv.core.files import parse_ingested_image_filename
from wv.core.images import get_image_datetime


@dataclass(frozen=True)
class BurstCandidate:
    """An image eligible for temporal burst analysis."""

    id: str
    path: Path
    monitoring_site: str
    captured_at: datetime


@dataclass(frozen=True)
class BurstAnalysis:
    """Perceptual similarity and quality information for one burst candidate."""

    candidate: BurstCandidate
    phash: imagehash.ImageHash
    quality: float


@dataclass(frozen=True)
class BurstDecision:
    """A deterministic keep or move decision for one burst candidate."""

    candidate_id: str
    path: Path
    decision: str


@dataclass(frozen=True)
class BurstPlanningFailure:
    """An image-level failure encountered while planning burst reduction."""

    candidate_id: str
    path: Path
    message: str


@dataclass(frozen=True)
class BurstReductionPlan:
    """Complete burst-reduction decisions for a candidate cohort."""

    decisions: tuple[BurstDecision, ...]
    failures: tuple[BurstPlanningFailure, ...]
    bursts: int
    processed: int


def validate_burst_thresholds(
    burst_gap_threshold: int, similarity_threshold: int
) -> None:
    """Validate burst temporal and perceptual-similarity thresholds.

    Args:
        burst_gap_threshold: Maximum seconds between consecutive images in a
            temporal burst.
        similarity_threshold: Maximum 64-bit perceptual-hash distance for
            connecting images in a similarity cluster.

    Raises:
        ValueError: If either threshold is outside the supported range.
    """
    if burst_gap_threshold < 0:
        raise ValueError("burst_gap_threshold must be greater than or equal to 0")
    if not 0 <= similarity_threshold <= 64:
        raise ValueError("similarity_threshold must be between 0 and 64")


def create_burst_candidate(candidate_id: str, path: Path) -> BurstCandidate:
    """Create a burst candidate using ingested metadata or image metadata.

    Args:
        candidate_id: Stable caller-provided identity for the candidate.
        path: Image file path used to resolve capture identity.

    Returns:
        A candidate with normalized monitoring-site identity and capture time.

    Raises:
        OSError: If fallback image metadata or filesystem timestamps cannot be
            read.
    """
    filename_parts = parse_ingested_image_filename(path)
    if filename_parts is not None:
        return BurstCandidate(
            id=candidate_id,
            path=path,
            monitoring_site=filename_parts["monitoring_site"].upper(),
            captured_at=datetime.strptime(
                filename_parts["captured_at"], "%Y%m%d_%H%M%S"
            ),
        )

    return BurstCandidate(
        id=candidate_id,
        path=path,
        monitoring_site=path.parent.name.upper(),
        captured_at=get_image_datetime(path),
    )


def build_burst_reduction_plan(
    candidates: list[BurstCandidate],
    burst_gap_threshold: int,
    similarity_threshold: int,
) -> BurstReductionPlan:
    """Build deterministic keep and move decisions for burst candidates.

    Temporal groups use consecutive capture-time gaps. Images within each group
    are connected transitively when their 64-bit perceptual hashes are within
    ``similarity_threshold``. Hashing and quality scoring normalize EXIF
    orientation first. Analysis failures are retained as ``keep`` decisions and
    returned separately so managed callers can reject incomplete plans.

    Args:
        candidates: Images with already-resolved capture identity.
        burst_gap_threshold: Maximum consecutive capture-time gap in seconds.
        similarity_threshold: Maximum perceptual-hash distance for an edge.

    Returns:
        Complete candidate decisions, image-level analysis failures, temporal
        burst count, and number of successfully processed images.

    Raises:
        ValueError: If thresholds are outside the supported range or candidate
            IDs are not unique.
    """
    validate_burst_thresholds(burst_gap_threshold, similarity_threshold)
    if len({candidate.id for candidate in candidates}) != len(candidates):
        raise ValueError("Burst candidate IDs must be unique.")

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.monitoring_site,
            candidate.captured_at,
            str(candidate.path),
            candidate.id,
        ),
    )
    decisions: dict[str, BurstDecision] = {}
    failures: list[BurstPlanningFailure] = []
    processed = 0
    temporal_bursts = _group_candidates(sorted_candidates, burst_gap_threshold)

    for burst in temporal_bursts:
        if len(burst) == 1:
            candidate = burst[0]
            decisions[candidate.id] = BurstDecision(candidate.id, candidate.path, "keep")
            processed += 1
            continue

        analyses: list[BurstAnalysis] = []
        for candidate in burst:
            try:
                analyses.append(_analyze_candidate(candidate))
                processed += 1
            except Exception as exc:
                failures.append(
                    BurstPlanningFailure(candidate.id, candidate.path, str(exc))
                )
                decisions[candidate.id] = BurstDecision(
                    candidate.id, candidate.path, "keep"
                )

        for cluster in _build_similarity_clusters(analyses, similarity_threshold):
            ranked_cluster = sorted(
                cluster,
                key=lambda analysis: (
                    -analysis.quality,
                    analysis.candidate.captured_at,
                    str(analysis.candidate.path),
                    analysis.candidate.id,
                ),
            )
            keep_amount = _get_keep_amount(len(ranked_cluster))
            for index, analysis in enumerate(ranked_cluster):
                decisions[analysis.candidate.id] = BurstDecision(
                    analysis.candidate.id,
                    analysis.candidate.path,
                    "keep" if index < keep_amount else "move",
                )

    return BurstReductionPlan(
        decisions=tuple(decisions[candidate.id] for candidate in sorted_candidates),
        failures=tuple(failures),
        bursts=sum(1 for burst in temporal_bursts if len(burst) > 1),
        processed=processed,
    )


def _group_candidates(
    candidates: list[BurstCandidate], burst_gap_threshold: int
) -> list[list[BurstCandidate]]:
    if not candidates:
        return []

    bursts = [[candidates[0]]]
    for candidate in candidates[1:]:
        current_burst = bursts[-1]
        previous_candidate = current_burst[-1]
        gap_seconds = (
            candidate.captured_at - previous_candidate.captured_at
        ).total_seconds()
        if (
            candidate.monitoring_site == previous_candidate.monitoring_site
            and gap_seconds <= burst_gap_threshold
        ):
            current_burst.append(candidate)
        else:
            bursts.append([candidate])
    return bursts


def _analyze_candidate(candidate: BurstCandidate) -> BurstAnalysis:
    with Image.open(candidate.path) as image:
        normalized_image = ImageOps.exif_transpose(image)
        normalized_image.load()
        return BurstAnalysis(
            candidate=candidate,
            phash=imagehash.phash(normalized_image),
            quality=_estimate_image_quality(normalized_image),
        )


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


def _build_similarity_clusters(
    analyses: list[BurstAnalysis], similarity_threshold: int
) -> list[list[BurstAnalysis]]:
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(analyses))}
    for left_index, left_analysis in enumerate(analyses):
        for right_index in range(left_index + 1, len(analyses)):
            right_analysis = analyses[right_index]
            if abs(left_analysis.phash - right_analysis.phash) <= similarity_threshold:
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)

    clusters: list[list[BurstAnalysis]] = []
    visited: set[int] = set()
    for start_index in range(len(analyses)):
        if start_index in visited:
            continue

        stack = [start_index]
        visited.add(start_index)
        indexes: list[int] = []
        while stack:
            current_index = stack.pop()
            indexes.append(current_index)
            for neighbor_index in sorted(adjacency[current_index], reverse=True):
                if neighbor_index not in visited:
                    visited.add(neighbor_index)
                    stack.append(neighbor_index)
        clusters.append([analyses[index] for index in sorted(indexes)])
    return clusters


def _get_keep_amount(cluster_size: int) -> int:
    if cluster_size <= 5:
        return 1
    if cluster_size <= 20:
        return 2
    return 3
