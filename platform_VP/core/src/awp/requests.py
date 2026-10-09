"""Requests an agent sends outside the platform, and the structured replies that come back.

One primitive covers what a case needs from the outside world: ask field staff
to do work, ask them for a cost sheet, ask the requester to confirm, or just
tell the requester how far things are (no reply expected). A domain declares
the kinds it supports; the platform checks every field before it leaves and
every reply before it counts as evidence.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import jsonschema
from pydantic import BaseModel, Field


class RequestKind(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    description: str
    # JSON Schema of what the agent must fill in.
    fields: dict = Field(default_factory=lambda: {"type": "object"})
    # JSON Schema of the reply; None means nothing comes back (a progress notice).
    reply: dict | None = None

    @property
    def expects_reply(self) -> bool:
        return self.reply is not None


class RequestError(ValueError):
    pass


def validate(schema: dict | None, value: Any, what: str) -> None:
    try:
        jsonschema.validate(value, schema or {"type": "object"})
    except jsonschema.ValidationError as e:
        where = ".".join(str(p) for p in e.absolute_path) or "(root)"
        raise RequestError(f"{what} is not valid at {where}: {e.message}") from None


def flatten(value: Any, prefix: str = "") -> list[str]:
    """Structured data as `path: value` lines, so every figure can be cited."""
    if isinstance(value, dict):
        return [line for k, v in value.items() for line in flatten(v, f"{prefix}.{k}" if prefix else str(k))]
    if isinstance(value, list):
        return [line for i, v in enumerate(value) for line in flatten(v, f"{prefix}[{i}]")]
    if isinstance(value, bool):
        value = "true" if value else "false"
    return [f"{prefix}: {value}"]


def as_text(data: Any) -> str:
    return "\n".join(flatten(data))


def leaves(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [x for v in value.values() for x in leaves(v)]
    if isinstance(value, list):
        return [x for v in value for x in leaves(v)]
    return [str(value)]


def figures_text(fields: dict) -> str:
    """What the guard reads: the values of the outgoing fields, without keys or indexes."""
    return "\n".join(leaves(fields))


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value).replace(" ", "").replace(",", ""))
    except InvalidOperation:
        raise RequestError(f"{value!r} is not a number") from None
