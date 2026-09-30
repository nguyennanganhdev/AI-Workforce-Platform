"""Canonical SHA-256 binding for an ActionRequest command envelope."""

import hashlib
import json
from typing import Any


def action_payload_hash(
    *, action_type: str, target_type: str, target_id: str | None, payload: dict[str, Any]
) -> str:
    """Hash action identity and JSON payload with stable key ordering."""

    encoded = json.dumps(
        {
            "actionType": action_type,
            "targetType": target_type,
            "targetId": target_id,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
