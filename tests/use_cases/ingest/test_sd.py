from datetime import datetime
from pathlib import Path

import pytest

import wv.use_cases.ingest.sd as sd


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def _freeze_ingest_environment(monkeypatch: pytest.MonkeyPatch, root_path: Path):
    monkeypatch.setattr(sd, "datetime", FrozenDateTime)
    monkeypatch.setattr(sd, "get_root_path", lambda: root_path)
    monkeypatch.setattr(
        sd,
        "get_image_datetime",
        lambda file_path: datetime(2024, 6, 28, 10, 15, 30),
    )


def test_run_dry_copy_counts_files_without_writing(
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    (source / "notes.txt").write_text("ignore me")
    (source / "subdir").mkdir()
    root_path = tmp_path / ".wv"
    _freeze_ingest_environment(monkeypatch, root_path)

    result = sd.run(
        sd.IngestSdInput(
            source=source,
            device="HNT001",
            monitoring_site="gf_stream_feeder",
            mode="copy",
            dry_run=True,
        )
    )

    assert result.destination == root_path / "sessions" / "20240628_120000__HNT001" / "initial"
    assert result.files_discovered == 3
    assert result.files_copied == 1
    assert result.files_deleted == 0
    assert result.files_ignored == 2
    assert result.files_failed == 0
    assert result.files_replaced == 0
    assert result.dry_run is True
    assert image_path.exists()
    assert not result.destination.exists()


def test_run_dry_drain_counts_replacements_and_deletions(
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    root_path = tmp_path / ".wv"
    _freeze_ingest_environment(monkeypatch, root_path)

    file_id = sd.get_file_id(image_path)
    expected_destination = (
        root_path
        / "sessions"
        / "20240628_120000__HNT001"
        / "initial"
        / f"20240628_101530__GF_STREAM_FEEDER__{file_id}.jpg"
    )
    expected_destination.parent.mkdir(parents=True)
    expected_destination.write_bytes(b"existing")

    result = sd.run(
        sd.IngestSdInput(
            source=source,
            device="HNT001",
            monitoring_site="GF_STREAM_FEEDER",
            mode="drain",
            dry_run=True,
        )
    )

    assert result.files_copied == 1
    assert result.files_deleted == 1
    assert result.files_replaced == 1
    assert image_path.exists()


def test_run_copy_writes_expected_file_and_keeps_source(
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    root_path = tmp_path / ".wv"
    _freeze_ingest_environment(monkeypatch, root_path)

    result = sd.run(
        sd.IngestSdInput(
            source=source,
            device="HNT001",
            monitoring_site="gf_stream_feeder",
            mode="copy",
        )
    )

    file_id = sd.get_file_id(image_path)
    expected_destination = (
        root_path
        / "sessions"
        / "20240628_120000__HNT001"
        / "initial"
        / f"20240628_101530__GF_STREAM_FEEDER__{file_id}.jpg"
    )

    assert result.files_copied == 1
    assert result.files_deleted == 0
    assert result.files_failed == 0
    assert expected_destination.exists()
    assert expected_destination.read_bytes() == image_path.read_bytes()
    assert image_path.exists()


def test_run_drain_writes_expected_file_and_deletes_source(
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    root_path = tmp_path / ".wv"
    _freeze_ingest_environment(monkeypatch, root_path)

    result = sd.run(
        sd.IngestSdInput(
            source=source,
            device="HNT001",
            monitoring_site="GF_STREAM_FEEDER",
            mode="drain",
        )
    )

    assert result.files_copied == 1
    assert result.files_deleted == 1
    assert result.files_failed == 0
    assert not image_path.exists()
