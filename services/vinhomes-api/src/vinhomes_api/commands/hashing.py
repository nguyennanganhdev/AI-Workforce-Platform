"""Canonical request hash for idempotent commands."""

import hashlib
import json
from typing import Any


def command_payload_hash(command_payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        command_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
