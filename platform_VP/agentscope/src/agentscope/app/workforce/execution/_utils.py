# -*- coding: utf-8 -*-
"""Internal helpers; public DTOs remain owned by Workforce contracts."""

from typing import Any

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from ..contracts import ErrorResponse, PartnerAudience, PublicError, Scope

SCOPE_FIELDS = ("tenant_id", "domain_id", "area_id", "manager_account_id")


class ExecutionError(Exception):
    """A sanitized error that may cross an API boundary."""

    def __init__(
        self, code: Any, status: Any = 409, retryable: Any = False
    ) -> None:
        super().__init__(code)
        self.code, self.status, self.retryable = code, status, retryable
        self.request_id = new_id()

    def public(self) -> dict[str, Any]:
        """Return the common error envelope without provider exception text."""
        return ErrorResponse(
            error=PublicError(
                code=self.code,
                message=self.code,
                request_id=self.request_id,
                retryable=self.retryable,
            )
        ).model_dump(mode="json")


def value(obj: Any) -> Any:
    """Accept mappings or shared Pydantic DTOs, without duplicating models."""
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj


def freeze(obj: Any) -> Any:
    """Copy JSON data and reject NaN or non-serializable arguments."""
    return json.loads(canonical(value(obj)))


def canonical(obj: Any) -> Any:
    """Canonical JSON for contract hashes and idempotency comparisons."""
    return json.dumps(
        value(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(obj: Any) -> Any:
    """Hash JSON without including transport signatures or credentials."""
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def new_id() -> Any:
    """Allocate an opaque platform UUID."""
    return str(uuid4())


def utc_now() -> Any:
    """UTC clock; services accept an injected clock for tests."""
    return datetime.now(timezone.utc)


def timestamp(dt: Any) -> Any:
    """Serialize an aware instant."""
    if dt.tzinfo is None:
        raise ExecutionError("TIMEZONE_REQUIRED", 422)
    return dt.astimezone(timezone.utc).isoformat()


def instant(text: Any) -> Any:
    """Parse an RFC3339 timestamp, rejecting naive values."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ExecutionError("TIMEZONE_REQUIRED", 422)
    return dt


def owner(scope: Scope | dict[str, Any]) -> dict[str, str]:
    """Require all four owner dimensions; never infer owner from actor."""
    try:
        return Scope.model_validate(scope).model_dump(mode="json")
    except ValidationError:
        raise ExecutionError("SCOPE_REQUIRED", 403) from None


def audience_ref(
    audience: PartnerAudience | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize optional audience fields without weakening exact binding."""
    if audience is None:
        return None
    try:
        return PartnerAudience.model_validate(audience).model_dump(
            mode="json", exclude_none=True
        )
    except ValidationError:
        raise ExecutionError("PARTNER_AUDIENCE_INVALID", 403) from None


def require_scope(scope: Any, record: Any) -> Any:
    """Hide resources outside the authenticated owner scope."""
    if record is None or owner(scope) != owner(record["scope"]):
        raise ExecutionError("RESOURCE_NOT_FOUND", 404)
