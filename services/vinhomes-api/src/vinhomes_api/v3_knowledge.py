"""Scoped published knowledge search for operations users."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection


router = APIRouter(tags=["Vinhomes V3 knowledge"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope="function")]


@router.get("/knowledge/search", summary="Search published knowledge in my scope")
async def search_knowledge(
    scope: Scope,
    query: str = Query(..., min_length=2, max_length=300),
    domain_id: UUID = Query(..., alias="domainId"),
    limit: int = Query(10, ge=1, le=30),
) -> dict[str, object]:
    db, actor_id, _ = scope
    result = await db.execute(text("""
        select d.id as document_id, d.title, d.code, d.language,
               kc.id as chunk_id, kc.text_content, kc.heading_path,
               ts_rank(kc.search_tsv, plainto_tsquery('simple', :query)) as rank
        from knowledge_documents d
        join knowledge_bases kb on kb.id=d.knowledge_base_id and kb.tenant_id=d.tenant_id
        join document_versions dv on dv.id=d.active_version_id and dv.tenant_id=d.tenant_id
        join knowledge_chunks kc on kc.version_id=dv.id and kc.tenant_id=d.tenant_id
        where d.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and kb.domain_id=:domain_id and kb.status='active' and d.status='published'
          and dv.effective_from<=now() and (dv.effective_to is null or dv.effective_to>now())
          and kc.search_tsv @@ plainto_tsquery('simple', :query)
          and exists (
              select 1 from document_scopes ds
              join access_scopes s on s.id=ds.scope_id and s.tenant_id=ds.tenant_id
              join scoped_user_roles r on r.scope_id=s.id and r.tenant_id=s.tenant_id
              join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
              where ds.document_id=d.id and ds.tenant_id=d.tenant_id
                and m.user_id=:actor_id and m.status='active'
                and r.role_code in ('management','staff')
                and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          )
          and exists (
              select 1 from document_acl acl
              where acl.document_id=d.id and acl.tenant_id=d.tenant_id
                and acl.effect='allow' and
                (acl.principal_kind='user' and acl.user_id=:actor_id
                 or acl.principal_kind='role' and exists (
                    select 1 from scoped_user_roles r
                    join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                    where m.user_id=:actor_id and m.status='active'
                      and r.role_code=acl.role_code and r.tenant_id=d.tenant_id
                      and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()))))
          and not exists (
              select 1 from document_acl acl
              where acl.document_id=d.id and acl.tenant_id=d.tenant_id
                and acl.effect='deny' and
                (acl.principal_kind='user' and acl.user_id=:actor_id
                 or acl.principal_kind='role' and exists (
                    select 1 from scoped_user_roles r
                    join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
                    where m.user_id=:actor_id and m.status='active'
                      and r.role_code=acl.role_code and r.tenant_id=d.tenant_id
                      and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()))))
        order by rank desc, d.id, kc.ordinal limit :limit
    """), {"query": query.strip(), "domain_id": domain_id,
           "actor_id": actor_id, "limit": limit})
    return {"items": [dict(row) for row in result.mappings()]}
