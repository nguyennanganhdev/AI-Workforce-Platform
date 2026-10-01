"""Scoped Incident resolution readiness and command endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..commands import CommandReceiptRepository
from ..commands.hashing import command_payload_hash
from ..concurrency import require_expected_version
from ..db.action_request import ActionRequestStatus
from ..db.command_receipt import CommandReceiptStatus
from ..db.dependencies import get_db_session
from ..db.incident import IncidentStatus
from ..events import BusinessEventRepository
from ..incidents.repository import IncidentRepository
from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..work_orders.authority import (
    FieldOperationsAuthority,
    FieldOperationsRole,
    get_field_operations_authority,
)
from .schemas import IncidentResolutionRead, ResolveIncidentInput
from .service import ResolutionBlockedError, check_incident_resolution


router = APIRouter(tags=["incident-resolution"])


def _tenant_uuid(context: RequestContext) -> UUID:
    try:
        return UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc


def _require_scope(scope: DomainScope, incident_id: UUID) -> None:
    if not scope_contains_subject(
        scope,
        namespace="vinhomes",
        subject_type="incident",
        subject_id=str(incident_id),
    ):
        raise HTTPException(status_code=403, detail="Incident is outside the effective domain scope")


def _require_coordinator(context: RequestContext, authority: FieldOperationsAuthority) -> None:
    if context.actor.kind != "user" or FieldOperationsRole.BQL_COORDINATOR not in authority.roles:
        raise HTTPException(status_code=403, detail="BQL coordinator role required")


@router.get(
    "/incidents/{incident_id}/resolution",
    operation_id="checkIncidentResolution",
    response_model=IncidentResolutionRead,
)
async def get_incident_resolution(
    incident_id: UUID,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    session: AsyncSession = Depends(get_db_session),
) -> IncidentResolutionRead:
    tenant_id = _tenant_uuid(context)
    incident = await IncidentRepository(session).get_by_id(
        tenant_id=tenant_id,
        incident_id=incident_id,
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    _require_scope(scope, incident_id)
    return await check_incident_resolution(
        session,
        tenant_id=tenant_id,
        incident=incident,
    )


@router.post(
    "/incidents/{incident_id}/resolve",
    operation_id="resolveIncident",
    response_model=IncidentResolutionRead,
    status_code=status.HTTP_200_OK,
)
async def resolve_incident(
    incident_id: UUID,
    payload: ResolveIncidentInput,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
    authority: FieldOperationsAuthority = Depends(get_field_operations_authority),
    session: AsyncSession = Depends(get_db_session),
) -> IncidentResolutionRead:
    _require_coordinator(context, authority)
    tenant_id = _tenant_uuid(context)
    command_type = "RESOLVE_INCIDENT"
    request_hash = command_payload_hash(
        {"incidentId": str(incident_id), "expectedVersion": payload.expected_version}
    )
    async with session.begin():
        incident = await IncidentRepository(session).get_by_id_for_update(
            tenant_id=tenant_id,
            incident_id=incident_id,
        )
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        _require_scope(scope, incident_id)
        receipts = CommandReceiptRepository(session)
        receipt = await receipts.get(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            for_update=True,
        )
        if receipt is not None:
            if receipt.payload_hash != request_hash:
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
            if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
                raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
            return IncidentResolutionRead.model_validate(receipt.response_json)

        require_expected_version(incident.version, payload.expected_version)
        state = await check_incident_resolution(
            session,
            tenant_id=tenant_id,
            incident=incident,
        )
        if not state.can_resolve:
            raise ResolutionBlockedError(state.blockers)

        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        await session.flush()
        await session.refresh(incident)
        event = await BusinessEventRepository(session).append(
            tenant_id=tenant_id,
            incident_id=incident.id,
            subject_type="Incident",
            subject_id=str(incident.id),
            event_type="INCIDENT_RESOLVED",
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            actor_version=None,
            data={"resolvedAt": incident.resolved_at.isoformat(), "version": incident.version},
            correlation_id=context.correlation_id,
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        result = IncidentResolutionRead(
            incidentId=incident.id,
            status=incident.status,
            resolvedAt=incident.resolved_at,
            canResolve=True,
            blockers=[],
        )
        receipt = receipts.add(
            tenant_id=tenant_id,
            actor_type=context.actor.kind,
            actor_id=context.actor.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            payload_hash=request_hash,
            subject_type="Incident",
            subject_id=str(incident.id),
        )
        await session.flush()
        await receipts.complete(
            receipt,
            subject_id=str(incident.id),
            response_json=result.model_dump(mode="json", by_alias=True),
        )
    return result
