# -*- coding: utf-8 -*-
"""Unit tests for area-platform security boundaries."""

from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase, TestCase
from uuid import uuid4

from agentscope.app.auth import AuthPrincipal
from agentscope.app.business import (
    BusinessAuthorizationError,
    BusinessService,
    InvalidPartnerApiKeyError,
    MemoryEmbeddingUnavailableError,
)
from agentscope.app.business._service import _vector_literal


class _EmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.embeddings = embeddings


class _FakeEmbeddingModel:
    async def __call__(self, inputs: list[str]) -> _EmbeddingResponse:
        assert inputs
        return _EmbeddingResponse([[0.0] * 1536])


class BusinessServiceSecurityTest(TestCase):
    """Test validation that does not need a database connection."""

    def setUp(self) -> None:
        self.service = BusinessService(
            database_url="postgresql+asyncpg://unused/unused",
            api_key_pepper="p" * 48,
            provisioning_secret="s" * 48,
        )

    def test_partner_api_key_format_round_trip(self) -> None:
        key_id = str(uuid4())
        parsed_id, secret = self.service._parse_api_key(
            f"dp_{key_id}.{'x' * 48}",
        )
        self.assertEqual(parsed_id, key_id)
        self.assertEqual(secret, "x" * 48)

    def test_invalid_partner_api_key_is_rejected(self) -> None:
        with self.assertRaises(InvalidPartnerApiKeyError):
            self.service._parse_api_key("wrong")

    def test_provisioning_secret_is_constant_time_checked(self) -> None:
        self.service.verify_provisioning_secret("s" * 48)
        with self.assertRaises(BusinessAuthorizationError):
            self.service.verify_provisioning_secret("x" * 48)

    def test_area_manager_scope_is_required(self) -> None:
        principal = AuthPrincipal(
            user_id="user",
            tenant_id="default",
            session_id="session",
            token_id="token",
            role="AREA_MANAGER",
            domain_id="vinhomes",
            area_id="ocean-park-1",
        )
        self.assertEqual(
            self.service._require_area_manager(principal),
            ("vinhomes", "ocean-park-1"),
        )

    def test_vector_literal(self) -> None:
        self.assertEqual(_vector_literal([1.0, 0.5, -2.0]), "[1,0.5,-2]")


class MemoryEmbeddingTest(IsolatedAsyncioTestCase):
    """Embedding is unavailable unless explicitly configured."""

    async def test_disabled_embedding_fails_closed(self) -> None:
        service = BusinessService(
            database_url="postgresql+asyncpg://unused/unused",
            api_key_pepper="p" * 48,
        )
        with self.assertRaises(MemoryEmbeddingUnavailableError):
            await service._embed_memory("content")

    async def test_configured_embedding_must_match_schema(self) -> None:
        service = BusinessService(
            database_url="postgresql+asyncpg://unused/unused",
            api_key_pepper="p" * 48,
            memory_embedding_model=_FakeEmbeddingModel(),
        )
        vector = await service._embed_memory("approved content")
        self.assertEqual(len(vector), 1536)
        self.assertEqual(datetime.now(timezone.utc).tzinfo, timezone.utc)
