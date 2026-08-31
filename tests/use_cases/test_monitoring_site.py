import pytest

from wv.use_cases.monitoring_site._shared import MonitoringSiteError
from wv.use_cases.monitoring_site.create import CreateMonitoringSiteInput, run as run_create
from wv.use_cases.monitoring_site.list import ListMonitoringSitesInput, run as run_list
from wv.use_cases.monitoring_site.show import ShowMonitoringSiteInput, run as run_show
from wv.use_cases.monitoring_site.update import UpdateMonitoringSiteInput, run as run_update


def test_site_creation_requires_existing_area_and_valid_coordinates(configured_workspace):
    with pytest.raises(MonitoringSiteError, match="Monitoring area not found"):
        run_create(
            CreateMonitoringSiteInput("MISSING", "Missing", 28.57, -101.16)
        )
    with pytest.raises(MonitoringSiteError, match="Latitude"):
        run_create(
            CreateMonitoringSiteInput("AREA001", "Invalid", 91, -101.16)
        )


def test_site_list_filters_by_immutable_area(configured_workspace):
    result = run_list(ListMonitoringSitesInput(monitoring_area_id="AREA001"))

    assert [site.id for site in result.items] == ["SITE001", "SITE002"]


def test_site_id_is_generated_or_explicitly_overridden(configured_workspace):
    generated = run_create(
        CreateMonitoringSiteInput("AREA001", "Árbol caído", 28.57, -101.16)
    )
    overridden = run_create(
        CreateMonitoringSiteInput(
            "AREA001", "Other tree", 28.58, -101.17, id="custom site"
        )
    )

    assert generated.monitoring_site.id == "ARBOL_CAIDO"
    assert overridden.monitoring_site.id == "CUSTOM_SITE"


def test_site_name_update_preserves_generated_identifier(configured_workspace):
    created = run_create(
        CreateMonitoringSiteInput("AREA001", "Fallen tree", 28.57, -101.16)
    )
    run_update(UpdateMonitoringSiteInput(id=created.monitoring_site.id, name="Riverbank tree"))

    assert run_show(ShowMonitoringSiteInput(created.monitoring_site.id)).monitoring_site.id == "FALLEN_TREE"
