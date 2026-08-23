import json

from wv.ml.speciesnet import _read_progress


def test_read_progress_returns_valid_worker_snapshot(tmp_path):
    progress_path = tmp_path / "progress.json"
    progress_path.write_text(
        json.dumps({"phase": "classifying", "completed": 16, "total": 31}),
        encoding="utf-8",
    )

    assert _read_progress(progress_path) == {
        "phase": "classifying",
        "completed": 16,
        "total": 31,
    }


def test_read_progress_ignores_invalid_or_partial_snapshot(tmp_path):
    progress_path = tmp_path / "progress.json"
    progress_path.write_text("{", encoding="utf-8")

    assert _read_progress(progress_path) is None
