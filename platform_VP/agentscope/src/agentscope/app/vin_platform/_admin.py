"""Administrative projections; never reuse the caller's granted-resource list."""

from sqlalchemy import update, func, select, table, column

from . import _tables as t
from ._contracts import PlatformError
from ._service import digest


class VinAdministration:
    def __init__(self, service):
        self.service = service

    async def page(self, context, collection, *, offset=0, limit=25, **filters):
        self.service.admin(context)
        if offset < 0 or not 1 <= limit <= 100:
            raise PlatformError("INVALID_PAGINATION", 422)
        source = {"policies": t.policies, "catalog": t.catalog, "grants": t.grants,
                  "memberships": t.memberships}.get(collection)
        if source is None:
            raise PlatformError("INVALID_ADMIN_COLLECTION", 422)
        query = select(source).where(source.c.tenant_id == context.tenant_id)
        for key, value in filters.items():
            if value is not None:
                if key == "subject_kind" and collection == "policies":
                    query = query.where(source.c.subject.like(value + ":%"))
                elif key == "environment" and collection == "catalog":
                    query = query.where(source.c.data["environment"].as_string() == value)
                else:
                    query = query.where(source.c[key] == value)
        key = source.c.subject if collection == "policies" else source.c.id
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
            rows = (await db.execute(query.order_by(key).offset(offset).limit(limit))).mappings().all()
        items = []
        for row in rows:
            if collection == "policies":
                item = {"subject": row["subject"], "revision": row["revision"], "active": row["active"], "policy": row["data"]}
            elif collection == "catalog":
                # CatalogEntry is an allowlist; no URL, credentials or secret refs.
                from ._contracts import CatalogEntry
                item = {"catalog_id": row["id"], **CatalogEntry.model_validate(row["data"]).model_dump()}
            else:
                item = {key: value for key, value in row.items() if key != "tenant_id"}
            items.append(item)
        return self._page(items, total, offset, limit)

    @staticmethod
    def _page(items, total, offset, limit):
        return {"items": items, "total": total, "offset": offset, "limit": limit,
                "next_offset": offset + limit if offset + limit < total else None}

    async def accounts(self, context, *, user_id=None, eligible=None, offset=0, limit=25):
        self.service.admin(context)
        users = table("auth_users", column("id"), column("tenant_id"), column("username"), column("role"), column("status"))
        is_eligible = func.coalesce(t.accounts.c.eligible, False)
        query = select(users.c.id.label("user_id"), users.c.username, users.c.role, users.c.status,
                       is_eligible.label("eligible"), func.coalesce(t.accounts.c.revision, 0).label("revision"))
        query = query.select_from(users.outerjoin(t.accounts, (t.accounts.c.user_id == users.c.id) &
                                                  (t.accounts.c.tenant_id == users.c.tenant_id)))
        query = query.where(users.c.tenant_id == context.tenant_id)
        if user_id is not None:
            query = query.where(users.c.id == user_id)
        if eligible is not None:
            query = query.where(is_eligible == eligible)
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
            rows = (await db.execute(query.order_by(users.c.id).offset(offset).limit(limit))).mappings().all()
        return self._page([dict(row) for row in rows], total, offset, limit)

    async def remove_policy(self, context, subject, expected_revision):
        self.service.admin(context)
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            changed = await db.execute(update(t.policies).where(t.policies.c.tenant_id == context.tenant_id,
                t.policies.c.subject == subject, t.policies.c.revision == expected_revision).values(
                    active=False, revision=t.policies.c.revision + 1))
            if changed.rowcount != 1:
                raise PlatformError("REVISION_CONFLICT", 409)
            await self.service.audit(db, context, "quota.policy_removed", subject, expected_revision=expected_revision)

    async def library(self, context, catalog_id):
        self.service.admin(context)
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            entry = (await db.execute(select(t.catalog).where(t.catalog.c.tenant_id == context.tenant_id,
                t.catalog.c.id == catalog_id, t.catalog.c.kind == "knowledge_base"))).mappings().first()
            if entry is None:
                raise PlatformError("RESOURCE_NOT_FOUND", 404)
            # Recheck current owner tenancy, even for an inactive catalog entry.
            owner = await self.service.context(entry["owner_id"])
            if owner.tenant_id != context.tenant_id or owner.role == "VIN_USER":
                # An accidental catalog entry must not turn a customer's
                # private KB into an administratively readable Vin library.
                raise PlatformError("RESOURCE_NOT_FOUND", 404)
        return entry

    @staticmethod
    def document(entry, doc):
        return {"document_id": doc.id, "catalog_id": entry["id"], "knowledge_base_id": entry["resource_id"],
                "owner_id": entry["owner_id"], "filename": doc.data.filename, "status": doc.status,
                "review_status": doc.data.review_status, "version": doc.data.version,
                "revision": digest(doc.model_dump(mode="json")), "source_ref": doc.data.source_ref,
                "size": doc.data.size, "reviewed_by": doc.data.reviewed_by,
                "effective_from": doc.data.effective_from, "effective_until": doc.data.effective_until}

    async def documents(self, context, catalog_id, *, review_status=None, offset=0, limit=25):
        entry = await self.library(context, catalog_id)
        docs = await self.service.storage.list_knowledge_documents(entry["owner_id"], entry["resource_id"])
        docs = sorted((doc for doc in docs if review_status is None or doc.data.review_status == review_status), key=lambda doc: doc.id)
        return self._page([self.document(entry, doc) for doc in docs[offset:offset + limit]], len(docs), offset, limit)

    async def review(self, context, catalog_id, document_id, body):
        entry = await self.library(context, catalog_id)
        doc = await self.service.storage.get_knowledge_document(entry["owner_id"], entry["resource_id"], document_id)
        if doc is None:
            raise PlatformError("DOCUMENT_NOT_FOUND", 404)
        if digest(doc.model_dump(mode="json")) != body.expected_revision:
            raise PlatformError("REVISION_CONFLICT", 409)
        if body.status == "approved" and doc.status != "ready":
            raise PlatformError("DOCUMENT_NOT_READY", 409)
        replacement = doc.model_copy(deep=True)
        replacement.data.review_status = body.status
        replacement.data.reviewed_by = context.initiator_user_id
        changed = await self.service.storage.replace_knowledge_document(doc, replacement)
        if not changed:
            raise PlatformError("REVISION_CONFLICT", 409)
        async with self.service.engine.begin() as db:
            await self.service.audit(db, context, "knowledge.document_reviewed", doc.id, status=body.status,
                                     catalog_id=catalog_id, expected_revision=body.expected_revision)
        current = await self.service.storage.get_knowledge_document(entry["owner_id"], entry["resource_id"], document_id)
        return self.document(entry, current)
