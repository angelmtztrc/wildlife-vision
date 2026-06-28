from pathlib import Path

from wv.use_cases.clean.overexposed_ir import (
    CleanOverexposedIrInput,
    ImageMetrics,
    _is_overexposed,
    run,
)


def test_is_overexposed_uses_threshold_boundaries():
    assert _is_overexposed(
        image_metrics=ImageMetrics(mean=200.0, std=25.0, ptc_high=0.1),
        mean_threshold=200.0,
        std_threshold=25.0,
        ptc_high_threshold=0.6,
    )

    assert _is_overexposed(
        image_metrics=ImageMetrics(mean=100.0, std=50.0, ptc_high=0.6),
        mean_threshold=200.0,
        std_threshold=25.0,
        ptc_high_threshold=0.6,
    )


def test_run_identifies_overexposed_images_in_dry_run(make_image, tmp_path: Path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    overexposed = make_image(source / "white.jpg", color=(255, 255, 255))
    make_image(source / "gray.jpg", color=(100, 100, 100))

    result = run(
        CleanOverexposedIrInput(
            source=source,
            output=output,
            mean_threshold=200.0,
            std_threshold=25.0,
            high_level=220,
            ptc_high_threshold=0.6,
            dry_run=True,
        )
    )

    assert result.destination == output / "ignored" / "overexposed"
    assert result.files_discovered == 2
    assert result.files_overexposed == 1
    assert result.files_moved == 0
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert overexposed.exists()


def test_run_moves_overexposed_images(make_image, tmp_path: Path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    overexposed = make_image(source / "white.jpg", color=(255, 255, 255))
    make_image(source / "gray.jpg", color=(100, 100, 100))

    result = run(
        CleanOverexposedIrInput(
            source=source,
            output=output,
            mean_threshold=200.0,
            std_threshold=25.0,
            high_level=220,
            ptc_high_threshold=0.6,
        )
    )

    moved_path = output / "ignored" / "overexposed" / "white.jpg"
    assert result.files_overexposed == 1
    assert result.files_moved == 1
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert not overexposed.exists()
    assert moved_path.exists()
