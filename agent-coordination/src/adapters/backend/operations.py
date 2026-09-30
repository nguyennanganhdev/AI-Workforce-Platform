"""Typed operation wrappers share a single validation/transport boundary."""

from typing import Any, Mapping

from .client import BackendClient, BackendResult
from .errors import ValidationError
from .messages import snapshot


async def send(
    client: BackendClient, operation: str, expected_type: str, request: Mapping[str, Any]
) -> BackendResult:
    wire = snapshot(request)
    if wire.get("type") != expected_type:
        raise ValidationError()
    return await client.call(operation, wire)
