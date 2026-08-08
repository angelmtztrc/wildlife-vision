from dataclasses import dataclass

INGEST_STATUSES = (
    "in_progress",
    "completed",
    "completed_with_failures",
    "failed",
)


@dataclass(frozen=True)
class IngestSession:
    id: str
    monitoring_site_id: str
    source_path: str
    mode: str
    recursive: bool
    started_at: str
    completed_at: str | None = None
    ingest_status: str = "in_progress"
    failure_message: str | None = None
    files_discovered: int = 0
    files_copied: int = 0
    files_deleted: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0


@dataclass(frozen=True)
class SessionImage:
    id: str
    session_id: str
    source_relative_path: str
    initial_relative_path: str
    current_relative_path: str
    state: str
    content_digest: str
    content_size_bytes: int
    captured_at: str
    ingested_at: str


@dataclass(frozen=True)
class SessionImageStateCount:
    state: str
    count: int


@dataclass(frozen=True)
class SessionProcess:
    session_id: str
    process_name: str
    status: str
    attempt_count: int
    started_at: str
    completed_at: str | None = None
    failure_message: str | None = None
    parameters_json: str | None = None
    files_discovered: int = 0
    files_processed: int = 0
    files_selected: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    bursts_count: int = 0
    execution_details_json: str | None = None


@dataclass(frozen=True)
class SessionProcessImagePlan:
    session_id: str
    process_name: str
    image_id: str
    decision: str
    target_relative_path: str | None
    planned_at: str
    decision_details_json: str | None = None
