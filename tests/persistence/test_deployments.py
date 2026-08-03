from pathlib import Path

from wv.domain.deployment import Deployment
from wv.persistence.database import initialize_database
from wv.persistence.repositories import DeploymentRepository
from wv.persistence.sql_session import sql_session_scope


def test_create_and_list_deployments_for_device(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        repository = DeploymentRepository(sql_session)
        first = repository.create(
            Deployment(
                id="dep-1",
                device_id="HNT001",
                monitoring_site_id="SITE001",
                sd_card_path="/Volumes/SD1",
                created_at="2026-07-21T10:00:00+00:00",
                updated_at="2026-07-21T10:00:00+00:00",
            )
        )
        second = repository.create(
            Deployment(
                id="dep-2",
                device_id="HNT001",
                monitoring_site_id="SITE002",
                sd_card_path="/Volumes/SD1",
                created_at="2026-07-21T11:00:00+00:00",
                updated_at="2026-07-21T11:00:00+00:00",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        assert DeploymentRepository(sql_session).list_for_device("HNT001") == [first, second]


def test_list_deployments_for_sd_card_filters_by_path(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        repository = DeploymentRepository(sql_session)
        repository.create(
            Deployment(
                id="dep-1",
                device_id="HNT001",
                monitoring_site_id="SITE001",
                sd_card_path="/Volumes/SD1",
                created_at="2026-07-21T10:00:00+00:00",
                updated_at="2026-07-21T10:00:00+00:00",
            )
        )
        matching = repository.create(
            Deployment(
                id="dep-2",
                device_id="HNT002",
                monitoring_site_id="SITE002",
                sd_card_path="/Volumes/SD2",
                created_at="2026-07-21T11:00:00+00:00",
                updated_at="2026-07-21T11:00:00+00:00",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        assert DeploymentRepository(sql_session).list_for_sd_card("/Volumes/SD2") == [matching]
