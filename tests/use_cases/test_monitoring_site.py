import pytest

from wv.use_cases.monitoring_site._shared import MonitoringSiteError
from wv.use_cases.monitoring_site.create import CreateMonitoringSiteInput, run as run_create
from wv.use_cases.monitoring_site.list import ListMonitoringSitesInput, run as run_list


def test_site_creation_requires_existing_area_and_valid_coordinates(configured_workspace):
    with pytest.raises(MonitoringSiteError, match="Monitoring area not found"):
        run_create(
            CreateMonitoringSiteInput("SITE003", "MISSING", "Missing", 28.57, -101.16)
        )
    with pytest.raises(MonitoringSiteError, match="Latitude"):
        run_create(
            CreateMonitoringSiteInput("SITE003", "AREA001", "Invalid", 91, -101.16)
        )


def test_site_list_filters_by_immutable_area(configured_workspace):
    result = run_list(ListMonitoringSitesInput(monitoring_area_id="AREA001"))

    assert [site.id for site in result.items] == ["SITE001", "SITE002"]
