from pathlib import Path

from wv.persistence.database import initialize_database
from wv.persistence.deployments import (
    DeploymentRecord,
    create_deployment,
    list_deployments_for_device,
    list_deployments_for_sd_card,
)


def test_create_and_list_deployments_for_device(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    first = create_deployment(
        database_path,
        DeploymentRecord(
            id="dep-1",
            device_id="HNT001",
            monitoring_site_id="SITE001",
            sd_card_path="/Volumes/SD1",
            created_at="2026-07-21T10:00:00+00:00",
            updated_at="2026-07-21T10:00:00+00:00",
        ),
    )
    second = create_deployment(
        database_path,
        DeploymentRecord(
            id="dep-2",
            device_id="HNT001",
            monitoring_site_id="SITE002",
            sd_card_path="/Volumes/SD1",
            created_at="2026-07-21T11:00:00+00:00",
            updated_at="2026-07-21T11:00:00+00:00",
        ),
    )

    assert list_deployments_for_device(database_path, "HNT001") == [first, second]


def test_list_deployments_for_sd_card_filters_by_path(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    create_deployment(
        database_path,
        DeploymentRecord(
            id="dep-1",
            device_id="HNT001",
            monitoring_site_id="SITE001",
            sd_card_path="/Volumes/SD1",
            created_at="2026-07-21T10:00:00+00:00",
            updated_at="2026-07-21T10:00:00+00:00",
        ),
    )
    matching = create_deployment(
        database_path,
        DeploymentRecord(
            id="dep-2",
            device_id="HNT002",
            monitoring_site_id="SITE002",
            sd_card_path="/Volumes/SD2",
            created_at="2026-07-21T11:00:00+00:00",
            updated_at="2026-07-21T11:00:00+00:00",
        ),
    )

    assert list_deployments_for_sd_card(database_path, "/Volumes/SD2") == [matching]
