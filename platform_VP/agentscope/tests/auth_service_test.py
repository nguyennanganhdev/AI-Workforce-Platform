# -*- coding: utf-8 -*-
"""Unit tests for authentication cryptographic boundaries."""

from datetime import timedelta
from unittest import TestCase

from agentscope.app.auth import AuthService, InvalidTokenError


class AuthServiceTest(TestCase):
    """Tests that do not require a running PostgreSQL server."""

    def setUp(self) -> None:
        self.service = AuthService(
            database_url="postgresql+asyncpg://unused/unused",
            jwt_secret="j" * 48,
            refresh_pepper="p" * 48,
            access_ttl=timedelta(minutes=15),
        )

    def test_access_token_round_trip(self) -> None:
        token = self.service._access_token(
            user_id="user-1",
            tenant_id="tenant-1",
            session_id="session-1",
            role="AREA_MANAGER",
            domain_id="vinhomes",
            area_id="ocean-park-1",
        )
        principal = self.service.verify_access_token(token)
        self.assertEqual(principal.user_id, "user-1")
        self.assertEqual(principal.tenant_id, "tenant-1")
        self.assertEqual(principal.session_id, "session-1")
        self.assertEqual(principal.role, "AREA_MANAGER")
        self.assertEqual(principal.domain_id, "vinhomes")
        self.assertEqual(principal.area_id, "ocean-park-1")

    def test_rejects_non_access_token(self) -> None:
        import jwt

        token = jwt.encode(
            {"type": "refresh"},
            "j" * 48,
            algorithm="HS256",
        )
        with self.assertRaises(InvalidTokenError):
            self.service.verify_access_token(token)

    def test_refresh_hash_is_keyed_and_stable(self) -> None:
        digest = self.service._refresh_hash("token")
        self.assertEqual(digest, self.service._refresh_hash("token"))
        self.assertNotEqual(
            digest,
            AuthService(
                database_url="postgresql+asyncpg://unused/unused",
                jwt_secret="j" * 48,
                refresh_pepper="different-pepper-value-with-more-than-32-bytes",
            )._refresh_hash("token"),
        )

    def test_registration_validation(self) -> None:
        tenant, email, username = self.service._validate_registration(
            "tenant",
            " Alice@Example.COM ",
            " Alice ",
            "long-enough-password",
        )
        self.assertEqual(
            (tenant, email, username),
            (
                "tenant",
                "alice@example.com",
                "alice",
            ),
        )
