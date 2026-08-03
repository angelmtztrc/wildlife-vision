from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringSite:
    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None
