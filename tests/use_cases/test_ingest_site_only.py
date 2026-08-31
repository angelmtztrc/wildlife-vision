from pathlib import Path

from wv.use_cases.ingest.ingest import ExplicitIngestIdentity, IngestInput, run


def test_ingest_uses_monitoring_site_for_session_identity(
    configured_workspace: Path, make_image, tmp_path: Path
):
    source = tmp_path / "source"
    source.mkdir()
    make_image(source / "capture.jpg")

    result = run(
        IngestInput(
            source=source,
            mode="copy",
            identity=ExplicitIngestIdentity(monitoring_site_id="SITE001"),
        )
    )

    assert result.destination.parent.name.endswith("__SITE001")
