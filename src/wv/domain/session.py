from dataclasses import dataclass, field

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
    detection_reviewed: bool = False
    is_favorite: bool = False
    favorite_reviewed: bool = False


@dataclass(frozen=True)
class SessionImageStateCount:
    state: str
    count: int


@dataclass(frozen=True)
class ImageTaxonPrediction:
    rank: int
    taxon_id: str
    taxon_class: str | None
    taxon_order: str | None
    taxon_family: str | None
    taxon_genus: str | None
    taxon_species: str | None
    common_name: str | None
    confidence: float


@dataclass(frozen=True)
class ImageObjectDetection:
    id: str
    image_id: str
    category: str
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_width: float
    bbox_height: float
    final_taxon_id: str | None = None
    final_taxon_rank: str | None = None
    final_taxon_confidence: float | None = None
    predictions: list[ImageTaxonPrediction] = field(default_factory=list)


@dataclass(frozen=True)
class ImageDetectionResult:
    image_id: str
    predicted_label: str
    predicted_confidence: float
    decision_source: str
    megadetector_model: str
    speciesnet_model: str
    speciesnet_model_version: str | None
    latitude: float
    longitude: float
    failure_message: str | None = None
    detections: list[ImageObjectDetection] = field(default_factory=list)


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
