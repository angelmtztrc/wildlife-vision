from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    monitoring_site_id: str | None = None
