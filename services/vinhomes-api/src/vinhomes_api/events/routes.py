"""Incident-scoped, append-only business timeline reads."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.dependencies import get_db_session
from ..incidents.repository import IncidentRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from .repository import BusinessEventRepository
from .schemas import BusinessEventPage, BusinessEventRead


router = APIRouter(tags=["business-events"])


@router.get(
    "/incidents/{incident_id}/timeline",
    operation_id="getIncidentTimeline",
    response_model=BusinessEventPage,
)
async def get_incident_timeline(
    incident_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
    event_type: list[str] | None = Query(default=None, alias="eventType"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BusinessEventPage:
    try:
        tenant_id = UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc
    incident = await IncidentRepository(session).get_by_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(status_code=403, detail="Incident is outside the effective domain scope")

    normalized_types = list(dict.fromkeys(item.strip() for item in event_type or []))
    if any(not item or len(item) > 128 for item in normalized_types):
        raise HTTPException(status_code=422, detail="eventType values must be non-empty and at most 128 characters")
    rows, total = await BusinessEventRepository(session).list_for_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        event_types=normalized_types or None,
        limit=limit,
        offset=offset,
    )
    return BusinessEventPage(
        items=[BusinessEventRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
