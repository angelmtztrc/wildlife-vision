from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringArea:
    id: str
    name: str
    description: str | None = None
    notes: str | None = None
