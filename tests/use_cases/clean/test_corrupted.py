from pathlib import Path

from wv.use_cases.clean.corrupted import CleanCorruptedInput, run


def test_run_marks_corrupted_images_without_moving_in_dry_run(
    make_corrupted_image,
    make_image,
    tmp_path: Path,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    good_image = make_image(source / "good.jpg")
    broken_image = make_corrupted_image(source / "broken.jpg")
    (source / "notes.txt").write_text("ignore me")

    result = run(CleanCorruptedInput(source=source, output=output, dry_run=True))

    assert result.destination == output / "ignored" / "corrupted"
    assert result.files_discovered == 3
    assert result.files_corrupted == 1
    assert result.files_moved == 0
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert good_image.exists()
    assert broken_image.exists()


def test_run_moves_corrupted_images(make_corrupted_image, make_image, tmp_path: Path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    make_image(source / "good.jpg")
    broken_image = make_corrupted_image(source / "broken.jpg")

    result = run(CleanCorruptedInput(source=source, output=output))

    moved_path = output / "ignored" / "corrupted" / "broken.jpg"
    assert result.files_corrupted == 1
    assert result.files_moved == 1
    assert result.files_failed == 0
    assert not broken_image.exists()
    assert moved_path.exists()
