from dataclasses import dataclass
from pathlib import Path

from wv.persistence.session import session_scope
from wv.use_cases.ingest.common import IngestInput, IngestResult, run as run_ingest
from wv.use_cases.ingest.common import validate_ingest_identity
from wv.workspace.workspace_config import require_workspace_database_path, require_workspace_path


@dataclass(frozen=True)
class IngestFolderInput:
    source: Path
    device_id: str
    monitoring_site_id: str
    mode: str
    dry_run: bool = False


IngestFolderResult = IngestResult


def run(input_data: IngestFolderInput) -> IngestFolderResult:
    workspace_path = require_workspace_path()

    with session_scope(require_workspace_database_path(workspace_path)) as session:
        validate_ingest_identity(
            session, input_data.device_id, input_data.monitoring_site_id
        )

    return run_ingest(
        IngestInput(
            source=input_data.source,
            device_id=input_data.device_id,
            monitoring_site_id=input_data.monitoring_site_id,
            mode=input_data.mode,
            dry_run=input_data.dry_run,
        ),
        workspace_path=workspace_path,
    )
