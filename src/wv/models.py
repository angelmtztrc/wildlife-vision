from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    monitoring_site_id: str | None = None


@dataclass(frozen=True)
class MonitoringSite:
    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class Deployment:
    id: str
    device_id: str
    monitoring_site_id: str
    sd_card_path: str
    created_at: str
    updated_at: str
