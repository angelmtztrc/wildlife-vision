from datetime import datetime, timedelta
from pathlib import Path

import imagehash
import pytest

import wv.use_cases.clean.bursts as bursts


def test_scan_image_parses_ingested_filenames_with_underscores(tmp_path: Path):
    file_path = tmp_path / "20240628_101530__GF_STREAM_FEEDER__ABC234.jpg"
    file_path.write_bytes(b"placeholder")

    scanned = bursts._scan_image(file_path)

    assert scanned.monitoring_site == "GF_STREAM_FEEDER"
    assert scanned.captured_at == datetime(2024, 6, 28, 10, 15, 30)


def test_group_files_into_bursts_splits_by_site_and_gap():
    start = datetime(2024, 6, 28, 10, 15, 30)
    scanned_images = [
        bursts.ScannedImage(Path("a.jpg"), "SITE_A", start),
        bursts.ScannedImage(Path("b.jpg"), "SITE_A", start + timedelta(seconds=30)),
        bursts.ScannedImage(Path("c.jpg"), "SITE_A", start + timedelta(seconds=120)),
        bursts.ScannedImage(Path("d.jpg"), "SITE_B", start + timedelta(seconds=125)),
    ]

    grouped = bursts._group_files_into_bursts(scanned_images, burst_gap_threshold=60)

    assert [[image.path.name for image in group] for group in grouped] == [
        ["a.jpg", "b.jpg"],
        ["c.jpg"],
        ["d.jpg"],
    ]


def test_build_similarity_clusters_groups_hashes_and_keeps_unreadable_singletons():
    burst_images = [
        bursts.BurstImage(Path("a.jpg"), imagehash.hex_to_hash("0000000000000000"), 10.0),
        bursts.BurstImage(Path("b.jpg"), imagehash.hex_to_hash("0000000000000000"), 9.0),
        bursts.BurstImage(Path("c.jpg"), imagehash.hex_to_hash("ffffffffffffffff"), 8.0),
        bursts.BurstImage(Path("d.jpg"), None, 0.0),
    ]

    clusters = bursts._build_similarity_clusters(burst_images, similarity_threshold=0)
    cluster_names = sorted(sorted(image.path.name for image in cluster) for cluster in clusters)

    assert cluster_names == [["a.jpg", "b.jpg"], ["c.jpg"], ["d.jpg"]]


@pytest.mark.parametrize(
    ("cluster_size", "expected_keep_amount"),
    [(1, 1), (5, 1), (6, 2), (20, 2), (21, 3)],
)
def test_get_keep_amount_uses_cluster_boundaries(
    cluster_size: int,
    expected_keep_amount: int,
):
    assert bursts._get_keep_amount(cluster_size) == expected_keep_amount


def test_run_moves_lower_ranked_images_from_a_burst(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    file_paths = [
        source / "20240628_101530__GF_STREAM_FEEDER__ABC234.jpg",
        source / "20240628_101531__GF_STREAM_FEEDER__ABC235.jpg",
        source / "20240628_101532__GF_STREAM_FEEDER__ABC236.jpg",
    ]
    for path in file_paths:
        path.write_bytes(b"placeholder")

    burst_image_map = {
        file_paths[0]: bursts.BurstImage(
            file_paths[0], imagehash.hex_to_hash("0000000000000000"), 30.0
        ),
        file_paths[1]: bursts.BurstImage(
            file_paths[1], imagehash.hex_to_hash("0000000000000000"), 20.0
        ),
        file_paths[2]: bursts.BurstImage(
            file_paths[2], imagehash.hex_to_hash("0000000000000000"), 10.0
        ),
    }

    def fake_build_burst_images(burst, result):
        return [burst_image_map[scanned_image.path] for scanned_image in burst]

    monkeypatch.setattr(bursts, "_build_burst_images", fake_build_burst_images)

    result = bursts.run(
        bursts.CleanBurstsInput(
            source=source,
            output=output,
            burst_gap_threshold=60,
            similarity_threshold=0,
        )
    )

    destination = output / "ignored" / "bursts"
    assert result.files_discovered == 3
    assert result.files_bursts == 1
    assert result.files_reduced == 2
    assert result.files_moved == 2
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert file_paths[0].exists()
    assert not file_paths[1].exists()
    assert not file_paths[2].exists()
    assert (destination / file_paths[1].name).exists()
    assert (destination / file_paths[2].name).exists()
