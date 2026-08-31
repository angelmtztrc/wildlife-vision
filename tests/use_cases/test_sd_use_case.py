from pathlib import Path

from wv.use_cases.sd.clear import SdClearInput, run as run_clear
from wv.use_cases.sd.initialize import SdInitializeInput, run as run_initialize
from wv.use_cases.sd.show import SdShowInput, run as run_show
from wv.use_cases.sd.update import SdUpdateInput, run as run_update


def test_sd_lifecycle_tracks_only_monitoring_site(
    configured_workspace: Path, tmp_path: Path
):
    sd_path = tmp_path / "sd"
    sd_path.mkdir()

    initialized = run_initialize(
        SdInitializeInput(sd_path, monitoring_site_id="SITE001")
    )
    shown = run_show(SdShowInput(sd_path))

    assert initialized.config.monitoring_site_id == "SITE001"
    assert shown.config == initialized.config

    updated = run_update(SdUpdateInput(sd_path, monitoring_site_id="SITE002"))
    assert updated.config.monitoring_site_id == "SITE002"

    cleared = run_clear(SdClearInput(sd_path))
    assert not cleared.config_path.exists()
