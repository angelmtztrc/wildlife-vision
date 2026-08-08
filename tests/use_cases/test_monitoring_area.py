from pathlib import Path

from wv.use_cases.monitoring_area.create import CreateMonitoringAreaInput, run as run_create
from wv.use_cases.monitoring_area.list import ListMonitoringAreasInput, run as run_list
from wv.use_cases.monitoring_site.create import CreateMonitoringSiteInput, run as run_create_site
from wv.use_cases.monitoring_site.list import ListMonitoringSitesInput, run as run_list_sites


def test_area_contains_filterable_fixed_sites(configured_workspace: Path):
    run_create(CreateMonitoringAreaInput(id="AREA002", name="South Ranch"))
    run_create_site(
        CreateMonitoringSiteInput(
            id="SITE003",
            monitoring_area_id="AREA002",
            name="Fence Trail",
            latitude=28.57,
            longitude=-101.16,
        )
    )

    assert [area.id for area in run_list(ListMonitoringAreasInput()).items] == [
        "AREA001",
        "AREA002",
    ]
    assert [site.id for site in run_list_sites(ListMonitoringSitesInput("AREA002")).items] == [
        "SITE003"
    ]
