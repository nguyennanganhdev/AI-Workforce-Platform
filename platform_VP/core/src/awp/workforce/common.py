"""Small helpers every workforce module shares."""
from __future__ import annotations

import time
from datetime import datetime, timezone


def now() -> float:
    return time.time()


def iso(ts: float | None) -> str | None:
    """RFC 3339 UTC with a Z suffix (contract section 4)."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def has_control(text: str) -> bool:
    return any(ord(c) < 32 or ord(c) == 127 or 0x80 <= ord(c) < 0xA0 for c in text)


def opaque_id(value: object) -> bool:
    """An id some other system chose (contract 6.2, 7): 1-200 characters, no control characters, nothing more. It is
    stored and compared as it is; what is shown to a model is a separate matter (jobs.attr, partner_tools.ref_of)."""
    return isinstance(value, str) and 1 <= len(value) <= 200 and not has_control(value)
