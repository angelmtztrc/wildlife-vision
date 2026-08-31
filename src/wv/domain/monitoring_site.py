from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringSite:
    id: str
    monitoring_area_id: str
    name: str
    latitude: float
    longitude: float
    description: str | None = None
    elevation: float | None = None
    notes: str | None = None
