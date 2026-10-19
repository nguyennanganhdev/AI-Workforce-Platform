"""Public contract adapters. Runtime reservation/settlement stay internal."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import Field, SecretStr
from sqlalchemy import select

from ..auth import AuthPrincipal
from ..deps import get_current_principal
from . import _tables as t
from ._contracts import CapabilityView, CatalogPage, CatalogEntry, Contract, DomainProvider, Pack, QuotaPolicy, ResourceGrant, ServiceRequest, SourceIntent, WorkspaceState
from ._domain import DomainAdapter
from ._contracts import AdminPage, PolicyView, AdminCatalogView, GrantView, MembershipView, AccountView, LibraryDocumentView, DocumentReview

router = APIRouter(tags=["vin-platform"])


def service(request: Request):
    authority = getattr(request.app.state, "vin_platform_service", None)
    if authority is None:
        raise HTTPException(503, detail="VIN_PLATFORM_DISABLED")
    return authority


async def caller(request: Request, principal: AuthPrincipal = Depends(get_current_principal)):
    authority = service(request)
    context = await authority.context(principal.user_id, session_id=principal.session_id)
    return authority, context


class PersonalRegistration(Contract):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=1024)


@router.post("/auth/register-personal", status_code=201)
async def register_personal(body: PersonalRegistration, request: Request):
    authority = service(request)
    from ..auth import UserAlreadyExistsError
    try:
        user = await authority.auth.register_personal(**body.model_dump())
    except UserAlreadyExistsError as exc:
        raise HTTPException(409, detail="ACCOUNT_ALREADY_EXISTS") from exc
    except ValueError as exc:
        raise HTTPException(422, detail="INVALID_REGISTRATION") from exc
    from .._router._auth import UserResponse
    return UserResponse.model_validate(user, from_attributes=True)


@router.get("/me/capabilities", response_model=CapabilityView)
async def capabilities(who=Depends(caller)):
    authority, context = who
    return await authority.capabilities(context)


@router.get("/me/workspaces", response_model=WorkspaceState)
async def workspaces(request: Request, principal: AuthPrincipal = Depends(get_current_principal), who=Depends(caller)):
    from ._workspaces import state
    authority, context = who
    return await state(authority, context, principal.session_id)


class WorkspaceSelection(Contract):
    workspace_id: str = Field(min_length=1, max_length=1000)
    expected_revision: int = Field(ge=0)


@router.put("/me/workspace")
async def select_workspace(body: WorkspaceSelection, principal: AuthPrincipal = Depends(get_current_principal), who=Depends(caller)):
    from ._workspaces import switch
    authority, context = who
    return await switch(authority, context, principal.session_id, body.workspace_id, body.expected_revision)


@router.get("/me/usage")
async def usage(who=Depends(caller)):
    authority, context = who
    return await authority.quota.usage(context)


@router.get("/catalog/{kind}", response_model=CatalogPage)
async def catalog(kind: str, environment: str = "production", who=Depends(caller)):
    authority, context = who
    if environment not in {"production", "sandbox"}:
        raise HTTPException(422, detail="INVALID_ENVIRONMENT")
    context = context.model_copy(update={"environment": environment})
    kind = {"providers": "credential", "agents": "agent", "knowledge": "knowledge_base", "mcps": "mcp", "skills": "skill"}.get(kind, kind)
    return {"items": await authority.catalog(context, kind)}


class Eligibility(Contract):
    eligible: bool


class MigrationRequest(Contract):
    dry_run: bool = True


class Reconciliation(Contract):
    actual_tokens: int = Field(ge=0)
    receipt_ref: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9:._/-]+$")


@router.post("/admin/vin/attempts/{ident}/reconcile")
async def reconcile(ident: str, body: Reconciliation, who=Depends(caller)):
    authority, context = who
    await authority.reconcile_attempt(context, ident, body.actual_tokens, body.receipt_ref)
    return {"settled": True}


@router.post("/admin/vin/credential-migration")
async def migrate_credentials(body: MigrationRequest, who=Depends(caller)):
    authority, context = who
    return await authority.migrate_credentials(context, dry_run=body.dry_run)


@router.put("/admin/vin/accounts/{user_id}/eligibility")
async def eligibility(user_id: str, body: Eligibility, expected_revision: int | None = Query(None, ge=0), who=Depends(caller)):
    authority, context = who
    revision = await authority.set_eligibility(context, user_id, body.eligible, expected_revision=expected_revision)
    return {"updated": True, "revision": revision}


@router.put("/admin/vin/quota-policies/{subject}")
async def policy(subject: str, body: QuotaPolicy, expected_revision: int | None = Query(None, ge=0), who=Depends(caller)):
    authority, context = who
    revision = await authority.set_policy(context, subject, body, expected_revision=expected_revision)
    return {"updated": True, "revision": revision}


@router.post("/admin/vin/catalog", status_code=201)
async def publish(body: CatalogEntry, who=Depends(caller)):
    authority, context = who
    return {"id": await authority.publish_catalog(context, body)}


@router.post("/admin/vin/grants", status_code=201)
async def grant(body: ResourceGrant, who=Depends(caller)):
    authority, context = who
    return {"id": await authority.grant(context, body)}


@router.delete("/admin/vin/grants/{ident}", status_code=204)
async def revoke_grant(ident: str, expected_revision: int | None = Query(None, ge=1), who=Depends(caller)):
    authority, context = who
    await authority.revoke_grant(context, ident, expected_revision=expected_revision)


class Membership(Contract):
    user_id: str
    group_id: str = Field(min_length=1, max_length=255)
    domain_id: str | None = None
    area_id: str | None = None
    expires_at: datetime | None = None


@router.post("/admin/vin/memberships", status_code=201)
async def membership(body: Membership, who=Depends(caller)):
    authority, context = who
    return {"id": await authority.add_membership(context, **body.model_dump())}


@router.delete("/admin/vin/memberships/{ident}", status_code=204)
async def revoke_membership(ident: str, expected_revision: int | None = Query(None, ge=1), who=Depends(caller)):
    authority, context = who
    await authority.revoke_membership(context, ident, expected_revision=expected_revision)


@router.get("/admin/vin/quota-policies", response_model=AdminPage[PolicyView])
async def admin_policies(subject: str | None = None, subject_kind: Literal["user", "group", "role", "pool"] | None = None,
                         active: bool | None = None,
                         offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.page(context, "policies", subject=subject, subject_kind=subject_kind, active=active, offset=offset, limit=limit)


@router.delete("/admin/vin/quota-policies/{subject}", status_code=204)
async def remove_policy(subject: str, expected_revision: int = Query(ge=1), who=Depends(caller)):
    authority, context = who
    await authority.administration.remove_policy(context, subject, expected_revision)


@router.get("/admin/vin/catalog", response_model=AdminPage[AdminCatalogView])
async def admin_catalog(kind: Literal["credential", "agent", "knowledge_base", "mcp", "skill"] | None = None,
                        environment: Literal["production", "sandbox"] | None = None, active: bool | None = None,
                        offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.page(context, "catalog", kind=kind, environment=environment, active=active, offset=offset, limit=limit)


@router.get("/admin/vin/grants", response_model=AdminPage[GrantView])
async def admin_grants(catalog_id: str | None = None, subject_kind: Literal["user", "group", "role"] | None = None,
                       subject_id: str | None = None, active: bool | None = None,
                       offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.page(context, "grants", catalog_id=catalog_id, subject_kind=subject_kind,
        subject_id=subject_id, active=active, offset=offset, limit=limit)


@router.get("/admin/vin/memberships", response_model=AdminPage[MembershipView])
async def admin_memberships(user_id: str | None = None, group_id: str | None = None, active: bool | None = None,
                            offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.page(context, "memberships", user_id=user_id, group_id=group_id,
        active=active, offset=offset, limit=limit)


@router.get("/admin/vin/accounts", response_model=AdminPage[AccountView])
async def admin_accounts(user_id: str | None = None, eligible: bool | None = None,
                         offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.accounts(context, user_id=user_id, eligible=eligible, offset=offset, limit=limit)


@router.get("/admin/vin/catalog/{catalog_id}/documents", response_model=AdminPage[LibraryDocumentView])
async def library_documents(catalog_id: str, review_status: Literal["candidate", "approved", "retired"] | None = None,
                            offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), who=Depends(caller)):
    authority, context = who
    return await authority.administration.documents(context, catalog_id, review_status=review_status, offset=offset, limit=limit)


@router.post("/admin/vin/catalog/{catalog_id}/documents/{document_id}/review", response_model=LibraryDocumentView)
async def library_review(catalog_id: str, document_id: str, body: DocumentReview, who=Depends(caller)):
    authority, context = who
    return await authority.administration.review(context, catalog_id, document_id, body)


class SecretInput(Contract):
    value: SecretStr = Field(min_length=16, max_length=65536)
    purpose: str = Field(pattern=r"^(domain-client|channel|signing)$")


@router.post("/admin/vin/secrets", status_code=201)
async def secret(body: SecretInput, who=Depends(caller)):
    authority, context = who
    return {"secret_ref": await authority.secret_put(context, body.value.get_secret_value(), body.purpose)}


@router.put("/admin/vin/domain-providers/{ident}")
async def provider(ident: str, body: DomainProvider, who=Depends(caller)):
    if ident != body.id:
        raise HTTPException(422, detail="PROVIDER_ID_MISMATCH")
    authority, context = who
    await DomainAdapter(authority).configure(context, body)
    return {"updated": True}


@router.post("/me/domain-links/{provider_id}/start")
async def link_start(provider_id: str, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).start(context, provider_id)


class CompleteLink(Contract):
    transaction_id: str
    state: str = Field(min_length=32, max_length=255)
    code: str = Field(min_length=32, max_length=255)


@router.post("/me/domain-links/{provider_id}/complete")
async def link_complete(provider_id: str, body: CompleteLink, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).complete(context, provider_id, **body.model_dump())


@router.get("/me/domain-links")
async def link_list(who=Depends(caller)):
    authority, context = who
    async with authority.engine.begin() as db:
        await authority.assert_active(db, context, require_eligible=False)
        rows = (await db.execute(select(t.links.c.id, t.links.c.provider_id, t.links.c.status, t.links.c.scopes,
            t.links.c.revision).where(t.links.c.tenant_id == context.tenant_id,
                t.links.c.user_id == context.initiator_user_id))).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.delete("/me/domain-links/{ident}", status_code=204)
async def unlink(ident: str, who=Depends(caller)):
    authority, context = who
    await DomainAdapter(authority).revoke(context, ident)


@router.get("/me/domain-links/{ident}/context")
async def linked_context(ident: str, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).request(context, ident, "GET", "/me")


@router.post("/service-cases", status_code=201)
async def create_case(body: ServiceRequest, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).create_case(context, body)


@router.get("/service-cases")
async def list_cases(offset: int = 0, limit: int = 25, who=Depends(caller)):
    authority, context = who
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, detail="INVALID_PAGINATION")
    async with authority.engine.begin() as db:
        await authority.assert_active(db, context, require_eligible=False)
        rows = (await db.execute(select(t.cases.c.id, t.cases.c.state, t.cases.c.revision).where(
            t.cases.c.tenant_id == context.tenant_id, t.cases.c.user_id == context.initiator_user_id,
        ).order_by(t.cases.c.id).offset(offset).limit(limit))).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/service-cases/{ident}")
async def get_case(ident: str, refresh: bool = False, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).get_case(context, ident, refresh=refresh)


class Materialize(Contract):
    category_id: str
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=128)


@router.get("/service-cases/{ident}/photos/{file_id}")
async def photo(ident: str, file_id: str, who=Depends(caller)):
    authority, context = who
    result = await DomainAdapter(authority).photo(context, ident, file_id)
    return Response(result["content"], media_type=result["content_type"], headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/service-cases/{ident}/tickets", status_code=201)
async def materialize(ident: str, body: Materialize, who=Depends(caller)):
    authority, context = who
    return await DomainAdapter(authority).materialize(context, ident, **body.model_dump())


@router.get("/service-cases/{ident}/events")
async def case_events(ident: str, after: int = 0, limit: int = 50, sync: bool = True, who=Depends(caller)):
    authority, context = who
    if after < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, detail="INVALID_PAGINATION")
    adapter = DomainAdapter(authority)
    await adapter.get_case(context, ident)
    status = await adapter.sync_events(context, ident) if sync else {}
    async with authority.engine.begin() as db:
        rows = (await db.execute(select(t.events.c.data).where(t.events.c.tenant_id == context.tenant_id,
            t.events.c.case_id == ident, t.events.c.audience == "customer", t.events.c.sequence > after,
        ).order_by(t.events.c.sequence).limit(limit + 1))).scalars().all()
    return {**status, "items": rows[:limit], "next_cursor": rows[min(len(rows), limit) - 1]["sequence"] if rows else after,
        "has_more": len(rows) > limit or status.get("has_more", False)}


@router.post("/service-cases/{ident}/decisions")
async def decide(ident: str, body: SourceIntent, who=Depends(caller)):
    if ident != body.case_id:
        raise HTTPException(422, detail="CASE_ID_MISMATCH")
    authority, context = who
    return await DomainAdapter(authority).decide(context, body)


@router.get("/me/packs")
async def my_packs(who=Depends(caller)):
    from ._packs import list_packs
    authority, context = who
    return await list_packs(authority, context)


async def _pack_change(request: Request, pack_id: str, installed: bool, who):
    from .._service._pack_agents import install_templates, withdraw_templates
    from ._packs import get_pack, set_installed
    from ._resources import platform_model_config, private_model_config
    authority, context = who
    pack, owner_id = await get_pack(authority, context, pack_id)
    await set_installed(authority, context, pack_id, installed)
    user_id, storage = context.initiator_user_id, authority.storage
    if not installed:
        await withdraw_templates(storage, user_id, pack_id, pack.template_agent_ids)
        return {"installed": False, "agents": []}
    agents = await install_templates(storage, request.app.state.workspace_manager,
        request.app.state.resource_access_service, user_id, pack_id, owner_id, pack.template_agent_ids,
        await private_model_config(storage, user_id) or await platform_model_config(authority, user_id))
    return {"installed": True, "agents": agents, "link_provider_id": pack.link_provider_id}


@router.post("/me/packs/{pack_id}/install")
async def install_pack(pack_id: str, request: Request, who=Depends(caller)):
    return await _pack_change(request, pack_id, True, who)


@router.post("/me/packs/{pack_id}/remove")
async def remove_pack(pack_id: str, request: Request, who=Depends(caller)):
    return await _pack_change(request, pack_id, False, who)


@router.get("/admin/vin/packs")
async def admin_packs(who=Depends(caller)):
    from ._packs import list_packs
    authority, context = who
    authority.admin(context)
    return await list_packs(authority, context, include_inactive=True)


@router.put("/admin/vin/packs/{pack_id}")
async def save_admin_pack(pack_id: str, body: Pack, expected_revision: int | None = Query(None, ge=0), who=Depends(caller)):
    from ._packs import save_pack
    authority, context = who
    return {"revision": await save_pack(authority, context, pack_id, body, expected_revision=expected_revision)}
