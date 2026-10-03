"""Trusted request context adapter for Vinhomes HTTP endpoints."""

from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _ContextModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_by_alias=True,
        validate_by_name=True,
    )


class ActorRef(_ContextModel):
    kind: Literal["user", "service", "agent"]
    id: str = Field(min_length=1)


class RequestContext(_ContextModel):
    """Fields aligned with ``shared/platform/context.ts`` RequestContext."""

    tenant_id: str = Field(alias="tenantId", min_length=1)
    actor: ActorRef
    correlation_id: str = Field(alias="correlationId", min_length=1)
    trace_id: str = Field(alias="traceId", min_length=1)


class DomainSubjectRef(_ContextModel):
    namespace: str = Field(min_length=1)
    subject_type: str = Field(alias="subjectType", min_length=1)
    subject_id: str = Field(alias="subjectId", min_length=1)


class DomainScope(_ContextModel):
    """Effective subject scope resolved by trusted middleware/domain auth."""

    namespace: str = Field(min_length=1)
    tenant_id: str = Field(alias="tenantId", min_length=1)
    subjects: list[DomainSubjectRef]


async def get_request_context(request: Request) -> RequestContext:
    """Read context injected by trusted server middleware, never client input."""
    raw_context = getattr(request.state, "request_context", None)
    if raw_context is None:
        raise HTTPException(status_code=401, detail="Authenticated request context required")
    try:
        return RequestContext.model_validate(raw_context)
    except ValidationError as exc:
        raise HTTPException(status_code=401, detail="Authenticated request context is invalid") from exc


async def get_domain_scope(
    request: Request,
    context: RequestContext = Depends(get_request_context),
) -> DomainScope:
    """Read the effective scope and ensure it is bound to the context tenant."""
    raw_scope = getattr(request.state, "domain_scope", None)
    if raw_scope is None:
        raise HTTPException(status_code=403, detail="Domain scope required")
    try:
        scope = DomainScope.model_validate(raw_scope)
    except ValidationError as exc:
        raise HTTPException(status_code=403, detail="Domain scope is invalid") from exc
    if scope.tenant_id != context.tenant_id:
        raise HTTPException(status_code=403, detail="Domain scope tenant does not match request")
    return scope


def scope_contains_subject(
    scope: DomainScope,
    *,
    namespace: str,
    subject_type: str,
    subject_id: str,
) -> bool:
    return scope.namespace == namespace and any(
        subject.namespace == namespace
        and subject.subject_type == subject_type
        and subject.subject_id == subject_id
        for subject in scope.subjects
    )
