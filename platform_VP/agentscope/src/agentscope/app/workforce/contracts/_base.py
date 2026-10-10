# -*- coding: utf-8 -*-
"""Shared primitives for Workforce contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


OpaqueId = Annotated[str, Field(min_length=1, max_length=200)]
ShortCode = Annotated[str, Field(min_length=1, max_length=128)]
JsonObject = dict[str, Any]


class WorkforceModel(BaseModel):
    """Strict-boundary model shared by public and internal contracts.

    Unknown fields fail closed. This is especially important for partner
    requests: callers cannot inject internal scope, group, agent, or
    credential identifiers through fields the contract does not define.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class RevisionedModel(WorkforceModel):
    """Base for immutable snapshots guarded by optimistic concurrency."""

    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
