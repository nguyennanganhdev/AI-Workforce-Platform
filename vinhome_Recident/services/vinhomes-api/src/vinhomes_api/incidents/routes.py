"""Tenant-scoped Incident read endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.dependencies import get_db_session
from ..db.incident import Incident, IncidentStatus
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from .repository import IncidentRepository
from .schemas import (
    IncidentPage,
    IncidentRead,
    IncidentSlaStatus,
    IncidentSortField,
    IncidentSortOrder,
    incident_read,
)


router = APIRouter(tags=["incidents"])
_MAX_PAGE_SIZE = 100


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated tenant identifier is invalid",
        ) from exc


def _require_incident_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(
            status_code=403,
            detail="Incident is outside the effective domain scope",
        )


def _scoped_incident_ids(scope: DomainScope) -> list[UUID]:
    ids: list[UUID] = []
    for subject in scope.subjects:
        if subject.namespace != "vinhomes" or subject.subject_type != "incident":
            continue
        try:
            ids.append(UUID(subject.subject_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=403,
                detail="Effective Incident scope contains an invalid subject identifier",
            ) from exc
    return ids


@router.get("/incidents", response_model=IncidentPage)
async def list_incidents(
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=25, ge=1, le=_MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    status: IncidentStatus | None = None,
    severity: str | None = Query(default=None, min_length=1, max_length=64),
    category: str | None = Query(default=None, min_length=1, max_length=64),
    tower_id: UUID | None = Query(default=None, alias="towerId"),
    sla_status: IncidentSlaStatus | None = Query(default=None, alias="slaStatus"),
    sort_by: IncidentSortField = Query(default=IncidentSortField.SLA, alias="sortBy"),
    sort_order: IncidentSortOrder | None = Query(default=None, alias="sortOrder"),
) -> IncidentPage:
    tenant_id = _tenant_uuid(context)
    now = datetime.now(timezone.utc)
    incidents, total = await IncidentRepository(session).list_for_queue(
        tenant_id=tenant_id,
        scoped_incident_ids=_scoped_incident_ids(scope),
        limit=limit,
        offset=offset,
        now=now,
        status=status,
        severity=severity,
        category=category,
        tower_id=tower_id,
        sla_status=sla_status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return IncidentPage(
        items=[incident_read(incident, now=now) for incident in incidents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
) -> Incident:
    tenant_id = _tenant_uuid(context)
    incident = await IncidentRepository(session).get_by_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    _require_incident_scope(scope, incident_id)
    return incident_read(incident, now=datetime.now(timezone.utc))
