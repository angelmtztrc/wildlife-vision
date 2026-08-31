from pathlib import Path

import pytest

from wv.use_cases.monitoring_area._shared import MonitoringAreaError
from wv.use_cases.monitoring_area.create import CreateMonitoringAreaInput, run as run_create
from wv.use_cases.monitoring_area.list import ListMonitoringAreasInput, run as run_list
from wv.use_cases.monitoring_site.create import CreateMonitoringSiteInput, run as run_create_site
from wv.use_cases.monitoring_site.list import ListMonitoringSitesInput, run as run_list_sites


def test_area_contains_filterable_fixed_sites(configured_workspace: Path):
    created_area = run_create(CreateMonitoringAreaInput(name="South Ranch"))
    run_create_site(
        CreateMonitoringSiteInput(
            monitoring_area_id="SOUTH_RANCH",
            name="Fence Trail",
            latitude=28.57,
            longitude=-101.16,
        )
    )

    assert created_area.monitoring_area.id == "SOUTH_RANCH"
    assert [area.id for area in run_list(ListMonitoringAreasInput()).items] == [
        "AREA001",
        "SOUTH_RANCH",
    ]
    assert [site.id for site in run_list_sites(ListMonitoringSitesInput("SOUTH_RANCH")).items] == [
        "FENCE_TRAIL"
    ]


def test_area_generated_id_collision_recommends_override(configured_workspace: Path):
    run_create(CreateMonitoringAreaInput(name="Rancho El Cascabel"))

    with pytest.raises(MonitoringAreaError, match="Provide --id"):
        run_create(CreateMonitoringAreaInput(name="Rancho El Cascabel"))
