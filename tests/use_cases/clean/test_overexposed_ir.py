from pathlib import Path

import pytest

from wv.core.images import ImageExposureMetrics, is_image_overexposed
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrInput, run


def test_is_image_overexposed_uses_threshold_boundaries():
    assert is_image_overexposed(
        image_metrics=ImageExposureMetrics(mean=200.0, std=25.0, ptc_high=0.1),
        mean_threshold=200.0,
        std_threshold=25.0,
        ptc_high_threshold=0.6,
    )

    assert is_image_overexposed(
        image_metrics=ImageExposureMetrics(mean=100.0, std=50.0, ptc_high=0.6),
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
    assert result.files_processed == 2
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
    assert result.files_processed == 2
    assert result.files_moved == 1
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert not overexposed.exists()
    assert moved_path.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("mean_threshold", -1.0, "mean_threshold"),
        ("mean_threshold", 256.0, "mean_threshold"),
        ("std_threshold", -1.0, "std_threshold"),
        ("high_level", -1, "high_level"),
        ("high_level", 256, "high_level"),
        ("ptc_high_threshold", -0.1, "ptc_high_threshold"),
        ("ptc_high_threshold", 1.1, "ptc_high_threshold"),
    ],
)
def test_run_rejects_invalid_threshold_inputs(
    make_image,
    tmp_path: Path,
    field: str,
    value: float,
    message: str,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    make_image(source / "white.jpg", color=(255, 255, 255))

    input_kwargs = dict(
        source=source,
        output=output,
        mean_threshold=200.0,
        std_threshold=25.0,
        high_level=220,
        ptc_high_threshold=0.6,
    )
    input_kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        run(CleanOverexposedIrInput(**input_kwargs))
