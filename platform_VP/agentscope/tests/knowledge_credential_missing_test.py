# -*- coding: utf-8 -*-
"""A knowledge base whose credential was deleted stays manageable."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

from agentscope.app._router._credential import delete_credential
from agentscope.app._service._index_worker import _sanitise_error
from agentscope.app.rag.knowledge_base_manager import (
    KnowledgeCredentialMissingError,
)
from agentscope.app.rag.knowledge_base_manager._collection_per_kb import (
    CollectionPerKbManager,
)


def _kb(credential_id: str = "cred-1"):
    return SimpleNamespace(
        user_id="u",
        data=SimpleNamespace(
            name="Quy định khu du lịch",
            collection_name="kb_1",
            embedding_model_config=SimpleNamespace(credential_id=credential_id),
        ),
    )


class KnowledgeCredentialMissingTest(IsolatedAsyncioTestCase):
    async def test_missing_credential_has_a_safe_message(self) -> None:
        storage = SimpleNamespace(
            get_knowledge_base=AsyncMock(return_value=_kb()),
            get_credential=AsyncMock(return_value=None),
        )
        manager = CollectionPerKbManager(storage, SimpleNamespace())
        with self.assertRaises(KnowledgeCredentialMissingError) as error:
            await manager.get_knowledge("u", "kb-1")
        self.assertNotIn("cred-1", str(error.exception))
        self.assertNotIn("kb-1", str(error.exception))

    async def test_document_vectors_are_deleted_without_the_embedding_model(self) -> None:
        vectors = SimpleNamespace(has_collection=AsyncMock(return_value=True), delete=AsyncMock())
        storage = SimpleNamespace(
            get_knowledge_base=AsyncMock(return_value=_kb()),
            get_credential=AsyncMock(return_value=None),
        )
        manager = CollectionPerKbManager(storage, vectors)
        await manager.delete_document_vectors("u", "kb-1", "doc-1")
        vectors.delete.assert_awaited_once_with("kb_1", "doc-1")
        storage.get_credential.assert_not_awaited()

    async def test_a_missing_collection_does_not_block_deleting(self) -> None:
        vectors = SimpleNamespace(has_collection=AsyncMock(return_value=False), delete=AsyncMock())
        storage = SimpleNamespace(get_knowledge_base=AsyncMock(return_value=_kb()))
        await CollectionPerKbManager(storage, vectors).delete_document_vectors("u", "kb-1", "doc-1")
        vectors.delete.assert_not_awaited()

    async def test_a_vector_store_failure_is_raised_so_the_record_stays(self) -> None:
        """Swallowed, the record and blob would go while the chunks stay
        searchable with nothing left to retry the delete from."""
        vectors = SimpleNamespace(has_collection=AsyncMock(side_effect=RuntimeError("down")))
        storage = SimpleNamespace(get_knowledge_base=AsyncMock(return_value=_kb()))
        with self.assertRaises(RuntimeError):
            await CollectionPerKbManager(storage, vectors).delete_document_vectors("u", "kb-1", "doc-1")

    def test_index_errors_shown_to_users_carry_no_internals(self) -> None:
        self.assertEqual(
            _sanitise_error(KnowledgeCredentialMissingError()),
            str(KnowledgeCredentialMissingError()),
        )
        generic = _sanitise_error(RuntimeError("Lost lease on doc-1 at /app/x.py"))
        self.assertNotIn("doc-1", generic)
        self.assertNotIn("RuntimeError", generic)

    async def test_a_credential_used_by_a_knowledge_base_cannot_be_deleted(self) -> None:
        storage = SimpleNamespace(
            list_knowledge_bases=AsyncMock(return_value=[_kb("cred-1"), _kb("other")]),
            delete_credential=AsyncMock(),
        )
        access = SimpleNamespace(resolve_for_edit=AsyncMock(return_value=("u", None)))
        with self.assertRaises(HTTPException) as error:
            await delete_credential("cred-1", "u", storage, access)
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("Quy định khu du lịch", error.exception.detail)
        storage.delete_credential.assert_not_awaited()
        await delete_credential("unused", "u", storage, access)
        storage.delete_credential.assert_awaited_once_with("u", "unused")
