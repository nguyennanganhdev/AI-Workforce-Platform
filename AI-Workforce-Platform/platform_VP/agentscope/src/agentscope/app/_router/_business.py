# -*- coding: utf-8 -*-
"""Domain directory, partner ticket, and reviewed-memory endpoints."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth import AuthPrincipal, AuthService
from ..business import (
    BusinessAuthorizationError,
    BusinessConflictError,
    BusinessNotFoundError,
    BusinessService,
    InvalidPartnerApiKeyError,
    MemoryEmbeddingUnavailableError,
    PartnerPrincipal,
)
from ..deps import (
    get_auth_service,
    get_business_service,
    get_current_principal,
)

business_router = APIRouter(tags=["area-platform"])


class DomainResponse(BaseModel):
    """Public registration choice for one business domain."""

    id: str
    name: str


class AreaResponse(BaseModel):
    """Public registration choice for one area."""

    id: str
    name: str
    domain_id: str


class IssuePartnerKeyRequest(BaseModel):
    """Provision one machine credential scoped to a domain."""

    domain_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    expires_at: datetime | None = None


class IssuePartnerKeyResponse(BaseModel):
    """One-time plaintext API-key response."""

    client_id: str
    key_id: str
    domain_id: str
    api_key: str
    expires_at: datetime | None


class PartnerTicketCreateRequest(BaseModel):
    """Ticket submitted by a trusted domain partner backend."""

    external_user_id: str = Field(min_length=1, max_length=255)
    residence_id: str = Field(min_length=1, max_length=255)
    conversation_id: str | None = Field(default=None, max_length=255)
    external_ticket_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=10000)


class PartnerResidenceRequest(BaseModel):
    """Residence membership synchronized by a trusted partner backend."""

    external_user_id: str = Field(min_length=1, max_length=255)
    area_id: str = Field(min_length=1, max_length=64)
    status: Literal["active", "inactive"] = "active"


class TicketStatusUpdateRequest(BaseModel):
    """Area-manager ticket progress update."""

    status: Literal["in_progress", "resolved", "closed"]
    note: str | None = Field(default=None, max_length=4000)


class MemoryCandidateCreateRequest(BaseModel):
    """Unembedded content proposed for area memory."""

    content: str = Field(min_length=1, max_length=20000)
    agent_id: str | None = Field(default=None, max_length=255)
    source_type: Literal["manual", "conversation", "ticket"] = "manual"
    source_id: str | None = Field(default=None, max_length=255)


class MemoryRejectRequest(BaseModel):
    """Reason an area manager rejected a memory candidate."""

    reason: str = Field(min_length=1, max_length=4000)


async def _business_call(awaitable: Any) -> Any:
    """Map expected service errors to stable HTTP responses."""
    try:
        return await awaitable
    except BusinessNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BusinessConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MemoryEmbeddingUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def get_partner_principal(
    service: BusinessService = Depends(get_business_service),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> PartnerPrincipal:
    """Authenticate a domain partner without impersonating a manager."""
    scheme, _, value = (authorization or "").partition(" ")
    api_key = value if scheme.lower() == "apikey" else x_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="partner API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    try:
        return await service.authenticate_partner_api_key(api_key)
    except InvalidPartnerApiKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "ApiKey"},
        ) from exc


@business_router.get("/directory/domains", response_model=list[DomainResponse])
async def list_domains(
    auth: AuthService = Depends(get_auth_service),
    service: BusinessService = Depends(get_business_service),
) -> list[dict[str, Any]]:
    """List domains available on the public registration form."""
    return await service.list_domains(auth.default_tenant_id)


@business_router.get(
    "/directory/domains/{domain_id}/areas",
    response_model=list[AreaResponse],
)
async def list_areas(
    domain_id: str,
    auth: AuthService = Depends(get_auth_service),
    service: BusinessService = Depends(get_business_service),
) -> list[dict[str, Any]]:
    """List active areas belonging to the selected domain."""
    return await service.list_areas(auth.default_tenant_id, domain_id)


@business_router.post(
    "/integrations/api-keys",
    response_model=IssuePartnerKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_partner_api_key(
    body: IssuePartnerKeyRequest,
    x_provisioning_secret: str | None = Header(
        default=None,
        alias="X-Provisioning-Secret",
    ),
    auth: AuthService = Depends(get_auth_service),
    service: BusinessService = Depends(get_business_service),
) -> IssuePartnerKeyResponse:
    """Provision a domain API key while no administrator UI exists."""
    try:
        service.verify_provisioning_secret(x_provisioning_secret)
    except BusinessAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    issued = await _business_call(
        service.issue_partner_api_key(
            tenant_id=auth.default_tenant_id,
            **body.model_dump(),
        ),
    )
    return IssuePartnerKeyResponse.model_validate(issued, from_attributes=True)


@business_router.post(
    "/partner/tickets",
    status_code=status.HTTP_201_CREATED,
)
async def create_partner_ticket(
    body: PartnerTicketCreateRequest,
    principal: PartnerPrincipal = Depends(get_partner_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Route one chatbot-created ticket to its area queue."""
    return await _business_call(
        service.create_ticket(principal, **body.model_dump()),
    )


@business_router.put("/partner/residences/{residence_id}")
async def upsert_partner_residence(
    residence_id: str,
    body: PartnerResidenceRequest,
    principal: PartnerPrincipal = Depends(get_partner_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Synchronize the residence mapping used to resolve ticket area."""
    return await _business_call(
        service.upsert_partner_residence(
            principal,
            residence_id=residence_id,
            external_user_id=body.external_user_id,
            area_id=body.area_id,
            residence_status=body.status,
        ),
    )


@business_router.get("/partner/tickets/{ticket_id}")
async def get_partner_ticket(
    ticket_id: str,
    principal: PartnerPrincipal = Depends(get_partner_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Let the partner chatbot poll ticket progress."""
    return await _business_call(service.get_partner_ticket(principal, ticket_id))


@business_router.get("/tickets")
async def list_area_tickets(
    ticket_status: str | None = Query(default=None, alias="status"),
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> list[dict[str, Any]]:
    """List the signed-in Area Manager's shared area queue."""
    return await _business_call(
        service.list_tickets_for_manager(
            principal,
            status_filter=ticket_status,
        ),
    )


@business_router.patch("/tickets/{ticket_id}/status")
async def update_area_ticket_status(
    ticket_id: str,
    body: TicketStatusUpdateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Update progress for a ticket in the manager's own area."""
    return await _business_call(
        service.update_ticket_status(
            principal,
            ticket_id=ticket_id,
            new_status=body.status,
            note=body.note,
        ),
    )


@business_router.post(
    "/memories/candidates",
    status_code=status.HTTP_201_CREATED,
)
async def create_memory_candidate(
    body: MemoryCandidateCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Create reviewable text without generating an embedding."""
    return await _business_call(
        service.create_memory_candidate(principal, **body.model_dump()),
    )


@business_router.get("/memories/candidates")
async def list_memory_candidates(
    candidate_status: str = Query(default="pending_review", alias="status"),
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> list[dict[str, Any]]:
    """List memory-review items in the manager's own area."""
    return await _business_call(
        service.list_memory_candidates(
            principal,
            status_filter=candidate_status,
        ),
    )


@business_router.post("/memories/candidates/{candidate_id}/approve")
async def approve_memory_candidate(
    candidate_id: str,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Approve first, then create the pgvector embedding."""
    return await _business_call(
        service.approve_memory_candidate(principal, candidate_id),
    )


@business_router.post("/memories/candidates/{candidate_id}/reject")
async def reject_memory_candidate(
    candidate_id: str,
    body: MemoryRejectRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> dict[str, Any]:
    """Reject a candidate without creating any vector."""
    return await _business_call(
        service.reject_memory_candidate(principal, candidate_id, body.reason),
    )


@business_router.get("/memories/search")
async def search_approved_memories(
    query: str = Query(min_length=1, max_length=4000),
    agent_id: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=5, ge=1, le=20),
    principal: AuthPrincipal = Depends(get_current_principal),
    service: BusinessService = Depends(get_business_service),
) -> list[dict[str, Any]]:
    """Search approved, active memory only in the manager's area."""
    return await _business_call(
        service.search_approved_memories(
            principal,
            query=query,
            agent_id=agent_id,
            limit=limit,
        ),
    )
