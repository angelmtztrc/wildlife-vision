from dataclasses import dataclass


@dataclass(frozen=True)
class Deployment:
    id: str
    device_id: str
    monitoring_site_id: str
    sd_card_path: str
    created_at: str
    updated_at: str
