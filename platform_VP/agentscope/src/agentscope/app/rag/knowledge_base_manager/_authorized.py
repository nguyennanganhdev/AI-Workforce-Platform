"""Recheck KB audience and document provenance for cached retrieval objects."""

from datetime import datetime, timezone

from ...vin_platform._context import execution_context
from ...vin_platform._contracts import PlatformError


class AuthorizedKnowledge:
    def __init__(self, inner, storage, record):
        self.inner, self.storage, self.record = inner, storage, record

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def authorize(self):
        authority = self.storage.vin_platform_service
        context = execution_context.get() or await authority.context(self.record.user_id)
        async with authority.engine.begin() as db:
            await authority.assert_active(db, context)
        if context.initiator_user_id != self.record.user_id:
            _, current = await authority.resolve_catalog(context, "knowledge_base", self.record.id, permission="bind")
            if current.user_id != self.record.user_id:
                raise PlatformError("RESOURCE_REVOKED", 404)

    async def document(self, ident):
        doc = await self.storage.get_knowledge_document(self.record.user_id, self.record.id, ident)
        today = datetime.now(timezone.utc).date().isoformat()
        if doc is None or doc.status != "ready" or doc.data.review_status != "approved" or (
            doc.data.effective_from and doc.data.effective_from > today) or (
            doc.data.effective_until and doc.data.effective_until < today):
            return None
        return doc

    async def search(self, *args, **kwargs):
        await self.authorize()
        result = []
        for hit in await self.inner.search(*args, **kwargs):
            doc = await self.document(hit.document_id)
            if doc is None:
                continue
            hit.chunk.metadata = {**(hit.chunk.metadata or {}), "knowledge_base_id": self.record.id,
                "document_id": doc.id, "source_ref": doc.data.source_ref, "version": doc.data.version}
            result.append(hit)
        return result

    async def list_chunks(self, document_id, *args, **kwargs):
        await self.authorize()
        if await self.document(document_id) is None:
            raise PlatformError("DOCUMENT_NOT_FOUND", 404)
        return await self.inner.list_chunks(document_id, *args, **kwargs)


def protect_knowledge(inner, storage, record):
    return AuthorizedKnowledge(inner, storage, record) if getattr(storage, "vin_platform_service", None) is not None else inner
