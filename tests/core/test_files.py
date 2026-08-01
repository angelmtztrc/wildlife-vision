from pathlib import Path

import pytest

from wv.core.files import (
    SymlinkPathError,
    copy_file_preserving_metadata,
    ensure_directory,
    ensure_not_symlink,
    ensure_tree_has_no_symlinks,
    get_file_id,
    is_allowed_image_file,
    move_file_with_staged_copy,
    parse_ingested_image_filename,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("photo.jpg", True),
        ("photo.JPEG", True),
        ("photo.PNG", False),
        ("photo.HeIc", False),
        ("photo.gif", False),
        ("photo", False),
    ],
)
def test_is_allowed_image_file_uses_known_extensions(filename: str, expected: bool):
    assert is_allowed_image_file(Path(filename)) is expected


def test_ensure_directory_accepts_existing_directory(tmp_path: Path):
    ensure_directory(tmp_path)


def test_ensure_directory_raises_for_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ensure_directory(tmp_path / "missing")


def test_ensure_directory_raises_for_file(tmp_path: Path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")

    with pytest.raises(NotADirectoryError):
        ensure_directory(file_path)


def test_ensure_not_symlink_rejects_a_symbolic_link(tmp_path: Path):
    target = tmp_path / "target.txt"
    link = tmp_path / "link.txt"
    target.write_text("content")
    link.symlink_to(target)

    with pytest.raises(SymlinkPathError, match="Symbolic links are not supported"):
        ensure_not_symlink(link)


def test_ensure_tree_has_no_symlinks_accepts_regular_nested_tree(tmp_path: Path):
    nested_file = tmp_path / "nested" / "image.jpg"
    nested_file.parent.mkdir()
    nested_file.write_bytes(b"image")

    ensure_tree_has_no_symlinks(tmp_path)


@pytest.mark.parametrize("link_kind", ["file", "directory", "broken"])
def test_ensure_tree_has_no_symlinks_rejects_links(tmp_path: Path, link_kind: str):
    link = tmp_path / "link"
    if link_kind == "file":
        target = tmp_path / "target.jpg"
        target.write_bytes(b"image")
        link.symlink_to(target)
    elif link_kind == "directory":
        target = tmp_path / "target"
        target.mkdir()
        link.symlink_to(target, target_is_directory=True)
    else:
        link.symlink_to(tmp_path / "missing.jpg")

    with pytest.raises(SymlinkPathError, match=str(link)):
        ensure_tree_has_no_symlinks(tmp_path)


def test_get_file_id_is_stable_for_identical_content(tmp_path: Path):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"same-bytes")
    second.write_bytes(b"same-bytes")

    assert get_file_id(first) == get_file_id(second)


def test_get_file_id_changes_when_content_changes(tmp_path: Path):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    assert get_file_id(first) != get_file_id(second)


def test_parse_ingested_image_filename_accepts_site_ids_with_underscores():
    parsed = parse_ingested_image_filename(
        Path("20240628_101530__GF_STREAM_FEEDER__ABC234.jpg")
    )

    assert parsed == {
        "captured_at": "20240628_101530",
        "monitoring_site": "GF_STREAM_FEEDER",
        "file_id": "ABC234",
    }


@pytest.mark.parametrize(
    "filename",
    [
        "2024062_101530__GF_STREAM_FEEDER__ABC234.jpg",
        "20240628_101530_GF_STREAM_FEEDER_ABC234.jpg",
        "20240628_101530__GF_STREAM_FEEDER__AB123.jpg",
        "20240628_101530__GF_STREAM_FEEDER__ABC239.jpg",
    ],
)
def test_parse_ingested_image_filename_rejects_invalid_names(filename: str):
    assert parse_ingested_image_filename(Path(filename)) is None


def test_parse_ingested_image_filename_matches_ingest_naming_convention(
    tmp_path: Path,
):
    source = tmp_path / "capture.jpg"
    source.write_bytes(b"wildlife-image")
    file_id = get_file_id(source)

    parsed = parse_ingested_image_filename(
        Path(f"20240628_101530__GF_STREAM_FEEDER__{file_id}.jpg")
    )

    assert parsed == {
        "captured_at": "20240628_101530",
        "monitoring_site": "GF_STREAM_FEEDER",
        "file_id": file_id,
    }


def test_copy_file_preserving_metadata_copies_file_bytes(tmp_path: Path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "nested" / "destination.jpg"
    source.write_bytes(b"image-bytes")
    destination.parent.mkdir()

    returned_path = copy_file_preserving_metadata(source, destination)

    assert returned_path == destination
    assert destination.read_bytes() == b"image-bytes"


def test_copy_file_preserving_metadata_raises_for_missing_source(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        copy_file_preserving_metadata(tmp_path / "missing.jpg", tmp_path / "out.jpg")


def test_copy_file_preserving_metadata_raises_for_missing_destination_parent(
    tmp_path: Path,
):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"image-bytes")

    with pytest.raises(FileNotFoundError):
        copy_file_preserving_metadata(source, tmp_path / "missing" / "out.jpg")


def test_copy_file_preserving_metadata_raises_for_destination_directory(
    tmp_path: Path,
):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "destination"
    source.write_bytes(b"image-bytes")
    destination.mkdir()

    with pytest.raises(IsADirectoryError):
        copy_file_preserving_metadata(source, destination)


def test_move_file_with_staged_copy_commits_transformed_copy(tmp_path: Path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "nested" / "destination.jpg"
    source.write_bytes(b"source-bytes")
    destination.parent.mkdir()
    destination.write_bytes(b"old-bytes")

    def transform(staged_file: Path) -> None:
        staged_file.write_bytes(b"updated-bytes")

    moved, replaced_existing = move_file_with_staged_copy(
        source,
        destination,
        transform=transform,
    )

    assert moved is True
    assert replaced_existing is True
    assert not source.exists()
    assert destination.read_bytes() == b"updated-bytes"


def test_move_file_with_staged_copy_preserves_source_when_transform_fails(
    tmp_path: Path,
):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "destination.jpg"
    source.write_bytes(b"source-bytes")

    def transform(staged_file: Path) -> None:
        raise RuntimeError("metadata write failed")

    with pytest.raises(RuntimeError, match="metadata write failed"):
        move_file_with_staged_copy(source, destination, transform=transform)

    assert source.read_bytes() == b"source-bytes"
    assert not destination.exists()


def test_move_file_with_staged_copy_preserves_source_when_verify_fails(
    tmp_path: Path,
):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "destination.jpg"
    source.write_bytes(b"source-bytes")

    with pytest.raises(ValueError, match="verification failed"):
        move_file_with_staged_copy(source, destination, verify=lambda staged: False)

    assert source.read_bytes() == b"source-bytes"
    assert not destination.exists()


def test_move_file_with_staged_copy_preserves_source_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "destination.jpg"
    source.write_bytes(b"source-bytes")
    destination.write_bytes(b"old-bytes")

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        move_file_with_staged_copy(source, destination)

    assert source.read_bytes() == b"source-bytes"
    assert destination.read_bytes() == b"old-bytes"
