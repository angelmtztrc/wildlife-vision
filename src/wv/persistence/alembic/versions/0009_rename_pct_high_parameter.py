"""Rename the overexposure near-white percentage parameter.

Revision ID: 0009_rename_pct_high_parameter
Revises: 0008_session_image_review_flags
Create Date: 2026-08-08 00:00:00.000000
"""

import json
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_rename_pct_high_parameter"
down_revision: str | None = "0008_session_image_review_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_parameter(source_key: str, target_key: str) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT session_id, process_name, parameters_json FROM session_processes "
            "WHERE process_name = 'clean_overexposed_ir' AND parameters_json IS NOT NULL"
        )
    ).mappings()
    for row in rows:
        try:
            parameters = json.loads(row["parameters_json"])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Cannot migrate invalid clean_overexposed_ir parameters JSON.") from exc
        if not isinstance(parameters, dict) or source_key not in parameters:
            continue
        if target_key in parameters:
            raise RuntimeError(
                "Cannot migrate clean_overexposed_ir parameters containing both "
                f"{source_key} and {target_key}."
            )
        parameters[target_key] = parameters.pop(source_key)
        connection.execute(
            sa.text(
                "UPDATE session_processes SET parameters_json = :parameters_json "
                "WHERE session_id = :session_id AND process_name = :process_name"
            ),
            {
                "parameters_json": json.dumps(parameters, sort_keys=True, separators=(",", ":")),
                "session_id": row["session_id"],
                "process_name": row["process_name"],
            },
        )


def upgrade() -> None:
    _rename_parameter("ptc_high_threshold", "pct_high_threshold")


def downgrade() -> None:
    _rename_parameter("pct_high_threshold", "ptc_high_threshold")
