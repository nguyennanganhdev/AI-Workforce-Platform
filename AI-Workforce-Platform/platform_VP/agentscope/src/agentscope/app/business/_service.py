# -*- coding: utf-8 -*-
"""Area-scoped partner, ticket, and reviewed-memory workflows."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from typing import Any, Self, Sequence
from uuid import UUID, uuid4

from ..auth import AuthPrincipal
from ._models import IssuedPartnerApiKey, PartnerPrincipal

_TICKET_TRANSITIONS = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"in_progress", "closed"},
    "closed": set(),
}


class BusinessError(Exception):
    """Base class for expected business-workflow failures."""


class BusinessNotFoundError(BusinessError):
    """A scoped resource does not exist."""


class BusinessConflictError(BusinessError):
    """The requested state transition cannot be applied."""


class BusinessAuthorizationError(BusinessError):
    """The authenticated principal cannot access the requested scope."""


class InvalidPartnerApiKeyError(BusinessError):
    """A partner API key is malformed, expired, revoked, or unknown."""


class MemoryEmbeddingUnavailableError(BusinessError):
    """Reviewed-memory embedding has not been configured."""


def _vector_literal(values: Sequence[float]) -> str:
    """Serialize a vector using pgvector's text input syntax."""
    if not values:
        raise ValueError("embedding must not be empty")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


class BusinessService(AbstractAsyncContextManager):
    """Own persistence for public directory, partner, ticket, and memory APIs."""

    def __init__(
        self,
        *,
        database_url: str,
        api_key_pepper: str,
        provisioning_secret: str | None = None,
        memory_embedding_model: Any | None = None,
        memory_embedding_dimensions: int = 1536,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if len(api_key_pepper.encode()) < 32:
            raise ValueError("api_key_pepper must contain at least 32 bytes")
        if provisioning_secret is not None and len(provisioning_secret) < 32:
            raise ValueError("provisioning_secret must contain at least 32 bytes")
        if memory_embedding_dimensions != 1536:
            raise ValueError("the packaged pgvector schema requires 1536 dimensions")
        self._database_url = database_url
        self._api_key_pepper = api_key_pepper.encode()
        self._provisioning_secret = provisioning_secret
        self._memory_embedding_model = memory_embedding_model
        self._memory_embedding_dimensions = memory_embedding_dimensions
        self._engine_kwargs = engine_kwargs or {}
        self._engine: Any | None = None
        self._dummy_api_hash = self._api_key_hash(secrets.token_urlsafe(48))

    async def __aenter__(self) -> Self:
        """Create the async connection pool."""
        from sqlalchemy.ext.asyncio import create_async_engine

        self._engine = create_async_engine(
            self._database_url,
            **self._engine_kwargs,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Dispose the async connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None

    def _require_engine(self) -> Any:
        if self._engine is None:
            raise RuntimeError("BusinessService has not entered its lifespan")
        return self._engine

    def verify_provisioning_secret(self, supplied: str | None) -> None:
        """Protect API-key issuance while no administrator role exists."""
        if self._provisioning_secret is None:
            raise BusinessAuthorizationError(
                "partner API-key provisioning is disabled",
            )
        if supplied is None or not hmac.compare_digest(
            self._provisioning_secret,
            supplied,
        ):
            raise BusinessAuthorizationError("invalid provisioning secret")

    def _api_key_hash(self, secret: str) -> str:
        return hmac.new(
            self._api_key_pepper,
            secret.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _parse_api_key(api_key: str) -> tuple[str, str]:
        prefix_and_id, separator, secret = api_key.partition(".")
        prefix, prefix_separator, key_id = prefix_and_id.partition("_")
        if not separator or not prefix_separator or prefix != "dp" or len(secret) < 32:
            raise InvalidPartnerApiKeyError("invalid partner API key")
        try:
            UUID(key_id)
        except ValueError as exc:
            raise InvalidPartnerApiKeyError("invalid partner API key") from exc
        return key_id, secret

    @staticmethod
    def _require_area_manager(principal: AuthPrincipal) -> tuple[str, str]:
        if (
            principal.role != "AREA_MANAGER"
            or not principal.domain_id
            or not principal.area_id
        ):
            raise BusinessAuthorizationError(
                "an area-scoped AREA_MANAGER account is required",
            )
        return principal.domain_id, principal.area_id

    async def list_domains(self, tenant_id: str) -> list[dict[str, Any]]:
        """List active domains available during self-registration."""
        from sqlalchemy import text

        async with self._require_engine().connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT id, name
                        FROM business_domains
                        WHERE tenant_id = :tenant_id AND status = 'active'
                        ORDER BY name
                        """,
                        ),
                        {"tenant_id": tenant_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def list_areas(
        self,
        tenant_id: str,
        domain_id: str,
    ) -> list[dict[str, Any]]:
        """List active areas belonging to one active domain."""
        from sqlalchemy import text

        async with self._require_engine().connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT a.id, a.name, a.domain_id
                        FROM areas a
                        JOIN business_domains d ON d.id = a.domain_id
                        WHERE d.tenant_id = :tenant_id
                          AND d.id = :domain_id
                          AND d.status = 'active'
                          AND a.status = 'active'
                        ORDER BY a.name
                        """,
                        ),
                        {"tenant_id": tenant_id, "domain_id": domain_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def issue_partner_api_key(
        self,
        *,
        tenant_id: str,
        domain_id: str,
        name: str,
        expires_at: datetime | None = None,
    ) -> IssuedPartnerApiKey:
        """Issue one domain-scoped API key, returning its secret once."""
        from sqlalchemy import text

        domain_id = domain_id.strip().lower()
        name = name.strip()
        if not name:
            raise ValueError("client name is required")
        client_id = str(uuid4())
        key_id = str(uuid4())
        secret = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        async with self._require_engine().begin() as connection:
            domain_exists = await connection.scalar(
                text(
                    """
                    SELECT 1 FROM business_domains
                    WHERE id = :domain_id AND tenant_id = :tenant_id
                      AND status = 'active'
                    """,
                ),
                {"domain_id": domain_id, "tenant_id": tenant_id},
            )
            if domain_exists is None:
                raise BusinessNotFoundError("active domain not found")
            await connection.execute(
                text(
                    """
                    INSERT INTO partner_api_clients (
                        id, tenant_id, domain_id, name, status, created_at
                    ) VALUES (
                        :id, :tenant_id, :domain_id, :name, 'active', :now
                    )
                    """,
                ),
                {
                    "id": client_id,
                    "tenant_id": tenant_id,
                    "domain_id": domain_id,
                    "name": name,
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO partner_api_credentials (
                        id, client_id, secret_hash, created_at, expires_at
                    ) VALUES (
                        :id, :client_id, :secret_hash, :now, :expires_at
                    )
                    """,
                ),
                {
                    "id": key_id,
                    "client_id": client_id,
                    "secret_hash": self._api_key_hash(secret),
                    "now": now,
                    "expires_at": expires_at,
                },
            )
        return IssuedPartnerApiKey(
            client_id=client_id,
            key_id=key_id,
            domain_id=domain_id,
            api_key=f"dp_{key_id}.{secret}",
            expires_at=expires_at,
        )

    async def authenticate_partner_api_key(
        self,
        api_key: str,
    ) -> PartnerPrincipal:
        """Verify a domain-level partner API key and return its principal."""
        from sqlalchemy import text

        key_id, secret = self._parse_api_key(api_key)
        async with self._require_engine().connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT k.id AS key_id, k.secret_hash, k.expires_at,
                               c.id AS client_id, c.tenant_id, c.domain_id
                        FROM partner_api_credentials k
                        JOIN partner_api_clients c ON c.id = k.client_id
                        JOIN business_domains d ON d.id = c.domain_id
                        WHERE k.id = :key_id
                          AND k.revoked_at IS NULL
                          AND c.status = 'active'
                          AND d.status = 'active'
                        """,
                        ),
                        {"key_id": key_id},
                    )
                )
                .mappings()
                .first()
            )
        expected = row["secret_hash"] if row else self._dummy_api_hash
        valid = hmac.compare_digest(expected, self._api_key_hash(secret))
        now = datetime.now(timezone.utc)
        if (
            not row
            or not valid
            or (row["expires_at"] is not None and row["expires_at"] <= now)
        ):
            raise InvalidPartnerApiKeyError("invalid or expired partner API key")
        async with self._require_engine().begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE partner_api_credentials
                    SET last_used_at = :now
                    WHERE id = :key_id
                    """,
                ),
                {"now": now, "key_id": key_id},
            )
        return PartnerPrincipal(
            key_id=key_id,
            client_id=row["client_id"],
            tenant_id=row["tenant_id"],
            domain_id=row["domain_id"],
        )

    async def upsert_partner_residence(
        self,
        principal: PartnerPrincipal,
        *,
        residence_id: str,
        external_user_id: str,
        area_id: str,
        residence_status: str = "active",
    ) -> dict[str, Any]:
        """Synchronize a residence-to-area mapping for partner routing."""
        from sqlalchemy import text

        residence_id = residence_id.strip()
        external_user_id = external_user_id.strip()
        area_id = area_id.strip().lower()
        if not residence_id or not external_user_id or not area_id:
            raise ValueError(
                "residence_id, external_user_id, and area_id are required",
            )
        if residence_status not in {"active", "inactive"}:
            raise ValueError("invalid residence status")
        now = datetime.now(timezone.utc)
        async with self._require_engine().begin() as connection:
            area_exists = await connection.scalar(
                text(
                    """
                    SELECT 1 FROM areas a
                    JOIN business_domains d ON d.id = a.domain_id
                    WHERE a.id = :area_id AND a.domain_id = :domain_id
                      AND d.tenant_id = :tenant_id
                      AND a.status = 'active' AND d.status = 'active'
                    """,
                ),
                {
                    "area_id": area_id,
                    "domain_id": principal.domain_id,
                    "tenant_id": principal.tenant_id,
                },
            )
            if area_exists is None:
                raise BusinessAuthorizationError(
                    "area is outside the API key's domain",
                )
            existing_id = await connection.scalar(
                text(
                    """
                    SELECT id FROM partner_residences
                    WHERE partner_client_id = :client_id
                      AND residence_id = :residence_id
                    """,
                ),
                {
                    "client_id": principal.client_id,
                    "residence_id": residence_id,
                },
            )
            residence_row_id = str(existing_id or uuid4())
            if existing_id:
                await connection.execute(
                    text(
                        """
                        UPDATE partner_residences
                        SET external_user_id = :external_user_id,
                            domain_id = :domain_id, area_id = :area_id,
                            status = :status, updated_at = :now
                        WHERE id = :id
                        """,
                    ),
                    {
                        "id": residence_row_id,
                        "external_user_id": external_user_id,
                        "domain_id": principal.domain_id,
                        "area_id": area_id,
                        "status": residence_status,
                        "now": now,
                    },
                )
            else:
                await connection.execute(
                    text(
                        """
                        INSERT INTO partner_residences (
                            id, partner_client_id, external_user_id,
                            residence_id, domain_id, area_id, status,
                            created_at, updated_at
                        ) VALUES (
                            :id, :client_id, :external_user_id,
                            :residence_id, :domain_id, :area_id, :status,
                            :now, :now
                        )
                        """,
                    ),
                    {
                        "id": residence_row_id,
                        "client_id": principal.client_id,
                        "external_user_id": external_user_id,
                        "residence_id": residence_id,
                        "domain_id": principal.domain_id,
                        "area_id": area_id,
                        "status": residence_status,
                        "now": now,
                    },
                )
        return {
            "id": residence_row_id,
            "partner_client_id": principal.client_id,
            "external_user_id": external_user_id,
            "residence_id": residence_id,
            "domain_id": principal.domain_id,
            "area_id": area_id,
            "status": residence_status,
            "updated_at": now,
        }

    async def create_ticket(
        self,
        principal: PartnerPrincipal,
        *,
        external_user_id: str,
        title: str,
        description: str,
        residence_id: str,
        conversation_id: str | None = None,
        external_ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Route a chatbot-created ticket into the matching area queue."""
        from sqlalchemy import text

        external_user_id = external_user_id.strip()
        residence_id = residence_id.strip()
        title = title.strip()
        description = description.strip()
        if not external_user_id or not residence_id or not title or not description:
            raise ValueError(
                "external_user_id, residence_id, title, and description are required",
            )
        now = datetime.now(timezone.utc)
        ticket_id = str(uuid4())
        async with self._require_engine().begin() as connection:
            residence = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT r.area_id
                        FROM partner_residences r
                        JOIN areas a ON a.id = r.area_id
                        JOIN business_domains d ON d.id = r.domain_id
                        WHERE r.partner_client_id = :client_id
                          AND r.residence_id = :residence_id
                          AND r.external_user_id = :external_user_id
                          AND r.domain_id = :domain_id
                          AND d.tenant_id = :tenant_id
                          AND r.status = 'active'
                          AND a.status = 'active'
                          AND d.status = 'active'
                        """,
                        ),
                        {
                            "client_id": principal.client_id,
                            "residence_id": residence_id,
                            "external_user_id": external_user_id,
                            "domain_id": principal.domain_id,
                            "tenant_id": principal.tenant_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if residence is None:
                raise BusinessAuthorizationError(
                    "no active residence mapping matches this user and API key",
                )
            area_id = residence["area_id"]
            active_managers = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM auth_users
                    WHERE tenant_id = :tenant_id
                      AND domain_id = :domain_id
                      AND area_id = :area_id
                      AND role = 'AREA_MANAGER'
                      AND status = 'active'
                    """,
                ),
                {
                    "tenant_id": principal.tenant_id,
                    "domain_id": principal.domain_id,
                    "area_id": area_id,
                },
            )
            if not active_managers:
                raise BusinessConflictError(
                    "the selected area has no active AREA_MANAGER",
                )
            if external_ticket_id:
                existing = (
                    (
                        await connection.execute(
                            text(
                                """
                            SELECT * FROM tickets
                            WHERE partner_client_id = :client_id
                              AND external_ticket_id = :external_ticket_id
                            """,
                            ),
                            {
                                "client_id": principal.client_id,
                                "external_ticket_id": external_ticket_id,
                            },
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    return dict(existing)
            await connection.execute(
                text(
                    """
                    INSERT INTO tickets (
                        id, tenant_id, domain_id, area_id, partner_client_id,
                        external_user_id, residence_id, conversation_id,
                        external_ticket_id, title, description, status,
                        created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :domain_id, :area_id, :client_id,
                        :external_user_id, :residence_id, :conversation_id,
                        :external_ticket_id, :title, :description, 'open',
                        :now, :now
                    )
                    """,
                ),
                {
                    "id": ticket_id,
                    "tenant_id": principal.tenant_id,
                    "domain_id": principal.domain_id,
                    "area_id": area_id,
                    "client_id": principal.client_id,
                    "external_user_id": external_user_id,
                    "residence_id": residence_id,
                    "conversation_id": conversation_id,
                    "external_ticket_id": external_ticket_id,
                    "title": title,
                    "description": description,
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO ticket_events (
                        id, ticket_id, actor_type, actor_id,
                        status, note, created_at
                    ) VALUES (
                        :id, :ticket_id, 'partner_app', :actor_id,
                        'open', 'Ticket created by partner chatbot', :now
                    )
                    """,
                ),
                {
                    "id": str(uuid4()),
                    "ticket_id": ticket_id,
                    "actor_id": principal.client_id,
                    "now": now,
                },
            )
        return {
            "id": ticket_id,
            "tenant_id": principal.tenant_id,
            "domain_id": principal.domain_id,
            "area_id": area_id,
            "partner_client_id": principal.client_id,
            "external_user_id": external_user_id,
            "residence_id": residence_id,
            "conversation_id": conversation_id,
            "external_ticket_id": external_ticket_id,
            "title": title,
            "description": description,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }

    async def list_tickets_for_manager(
        self,
        principal: AuthPrincipal,
        *,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List only tickets in the authenticated manager's area."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        statement = """
            SELECT * FROM tickets
            WHERE tenant_id = :tenant_id
              AND domain_id = :domain_id
              AND area_id = :area_id
        """
        params: dict[str, Any] = {
            "tenant_id": principal.tenant_id,
            "domain_id": domain_id,
            "area_id": area_id,
        }
        if status_filter:
            if status_filter not in _TICKET_TRANSITIONS:
                raise ValueError("invalid ticket status")
            statement += " AND status = :status"
            params["status"] = status_filter
        statement += " ORDER BY updated_at DESC"
        async with self._require_engine().connect() as connection:
            rows = (await connection.execute(text(statement), params)).mappings().all()
        return [dict(row) for row in rows]

    async def update_ticket_status(
        self,
        principal: AuthPrincipal,
        *,
        ticket_id: str,
        new_status: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Advance a ticket while enforcing the manager's area scope."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        if new_status not in _TICKET_TRANSITIONS:
            raise ValueError("invalid ticket status")
        now = datetime.now(timezone.utc)
        async with self._require_engine().begin() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT * FROM tickets
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND domain_id = :domain_id AND area_id = :area_id
                        """,
                        ),
                        {
                            "id": ticket_id,
                            "tenant_id": principal.tenant_id,
                            "domain_id": domain_id,
                            "area_id": area_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise BusinessNotFoundError("ticket not found")
            if new_status == row["status"]:
                return dict(row)
            if new_status not in _TICKET_TRANSITIONS[row["status"]]:
                raise BusinessConflictError(
                    f"cannot move ticket from {row['status']} to {new_status}",
                )
            updated = await connection.execute(
                text(
                    """
                    UPDATE tickets SET status = :status, updated_at = :now
                    WHERE id = :id AND status = :old_status
                    """,
                ),
                {
                    "status": new_status,
                    "now": now,
                    "id": ticket_id,
                    "old_status": row["status"],
                },
            )
            if not updated.rowcount:
                raise BusinessConflictError(
                    "ticket was updated concurrently; reload and retry",
                )
            await connection.execute(
                text(
                    """
                    INSERT INTO ticket_events (
                        id, ticket_id, actor_type, actor_id,
                        status, note, created_at
                    ) VALUES (
                        :id, :ticket_id, 'area_manager', :actor_id,
                        :status, :note, :now
                    )
                    """,
                ),
                {
                    "id": str(uuid4()),
                    "ticket_id": ticket_id,
                    "actor_id": principal.user_id,
                    "status": new_status,
                    "note": note,
                    "now": now,
                },
            )
        result = dict(row)
        result["status"] = new_status
        result["updated_at"] = now
        return result

    async def get_partner_ticket(
        self,
        principal: PartnerPrincipal,
        ticket_id: str,
    ) -> dict[str, Any]:
        """Return a ticket and progress events to the creating partner."""
        from sqlalchemy import text

        async with self._require_engine().connect() as connection:
            ticket = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT * FROM tickets
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND domain_id = :domain_id
                          AND partner_client_id = :client_id
                        """,
                        ),
                        {
                            "id": ticket_id,
                            "tenant_id": principal.tenant_id,
                            "domain_id": principal.domain_id,
                            "client_id": principal.client_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if ticket is None:
                raise BusinessNotFoundError("ticket not found")
            events = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT id, actor_type, status, note, created_at
                        FROM ticket_events
                        WHERE ticket_id = :ticket_id
                        ORDER BY created_at
                        """,
                        ),
                        {"ticket_id": ticket_id},
                    )
                )
                .mappings()
                .all()
            )
        result = dict(ticket)
        result["events"] = [dict(event) for event in events]
        return result

    async def create_memory_candidate(
        self,
        principal: AuthPrincipal,
        *,
        content: str,
        agent_id: str | None = None,
        source_type: str = "manual",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        """Store unembedded content in the manager's review queue."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        content = content.strip()
        if not content:
            raise ValueError("memory content is required")
        if source_type not in {"manual", "conversation", "ticket"}:
            raise ValueError("invalid memory source_type")
        candidate_id = str(uuid4())
        now = datetime.now(timezone.utc)
        result = {
            "id": candidate_id,
            "tenant_id": principal.tenant_id,
            "domain_id": domain_id,
            "area_id": area_id,
            "agent_id": agent_id,
            "source_type": source_type,
            "source_id": source_id,
            "content": content,
            "status": "pending_review",
            "created_by": principal.user_id,
            "reviewed_by": None,
            "reviewed_at": None,
            "rejection_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        async with self._require_engine().begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO memory_candidates (
                        id, tenant_id, domain_id, area_id, agent_id,
                        source_type, source_id, content, status, created_by,
                        created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :domain_id, :area_id, :agent_id,
                        :source_type, :source_id, :content, :status, :created_by,
                        :created_at, :updated_at
                    )
                    """,
                ),
                result,
            )
        return result

    async def list_memory_candidates(
        self,
        principal: AuthPrincipal,
        *,
        status_filter: str = "pending_review",
    ) -> list[dict[str, Any]]:
        """List memory candidates only within the manager's area."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        if status_filter not in {"pending_review", "approved", "rejected"}:
            raise ValueError("invalid candidate status")
        async with self._require_engine().connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT * FROM memory_candidates
                        WHERE tenant_id = :tenant_id
                          AND domain_id = :domain_id
                          AND area_id = :area_id
                          AND status = :status
                        ORDER BY created_at DESC
                        """,
                        ),
                        {
                            "tenant_id": principal.tenant_id,
                            "domain_id": domain_id,
                            "area_id": area_id,
                            "status": status_filter,
                        },
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def _embed_memory(self, content: str) -> list[float]:
        if self._memory_embedding_model is None:
            raise MemoryEmbeddingUnavailableError(
                "memory embedding model is not configured",
            )
        response = await self._memory_embedding_model([content])
        if not response.embeddings or response.embeddings[0] is None:
            raise MemoryEmbeddingUnavailableError(
                "embedding provider returned no vector",
            )
        embedding = [float(value) for value in response.embeddings[0]]
        if len(embedding) != self._memory_embedding_dimensions:
            raise MemoryEmbeddingUnavailableError(
                "embedding dimension does not match the pgvector schema",
            )
        return embedding

    async def approve_memory_candidate(
        self,
        principal: AuthPrincipal,
        candidate_id: str,
    ) -> dict[str, Any]:
        """Embed and activate a candidate only after area-manager review."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        scope = {
            "id": candidate_id,
            "tenant_id": principal.tenant_id,
            "domain_id": domain_id,
            "area_id": area_id,
        }
        async with self._require_engine().connect() as connection:
            candidate = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT * FROM memory_candidates
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND domain_id = :domain_id AND area_id = :area_id
                        """,
                        ),
                        scope,
                    )
                )
                .mappings()
                .first()
            )
        if candidate is None:
            raise BusinessNotFoundError("memory candidate not found")
        if candidate["status"] != "pending_review":
            raise BusinessConflictError("memory candidate has already been reviewed")

        # No vector exists before this explicit approval path reaches here.
        embedding = await self._embed_memory(candidate["content"])
        memory_id = str(uuid4())
        now = datetime.now(timezone.utc)
        async with self._require_engine().begin() as connection:
            locked = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT status FROM memory_candidates
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND domain_id = :domain_id AND area_id = :area_id
                        FOR UPDATE
                        """,
                        ),
                        scope,
                    )
                )
                .mappings()
                .first()
            )
            if locked is None:
                raise BusinessNotFoundError("memory candidate not found")
            if locked["status"] != "pending_review":
                raise BusinessConflictError(
                    "memory candidate has already been reviewed",
                )
            await connection.execute(
                text(
                    """
                    INSERT INTO reme_memories (
                        id, tenant_id, user_id, domain_id, area_id, agent_id,
                        source_session_id, content, memory_type, importance,
                        confidence, status, embedding, metadata, approved_by,
                        approved_at, source_candidate_id
                    ) VALUES (
                        CAST(:id AS uuid), :tenant_id, :user_id, :domain_id,
                        :area_id, :agent_id, NULL, :content, 'business_fact',
                        0.5, 1.0, 'active', CAST(:embedding AS vector),
                        CAST(:metadata AS jsonb), :approved_by, :approved_at,
                        :source_candidate_id
                    )
                    """,
                ),
                {
                    "id": memory_id,
                    "tenant_id": principal.tenant_id,
                    "user_id": principal.user_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                    "agent_id": candidate["agent_id"],
                    "content": candidate["content"],
                    "embedding": _vector_literal(embedding),
                    "metadata": json.dumps(
                        {
                            "source_type": candidate["source_type"],
                            "source_id": candidate["source_id"],
                        },
                    ),
                    "approved_by": principal.user_id,
                    "approved_at": now,
                    "source_candidate_id": candidate_id,
                },
            )
            await connection.execute(
                text(
                    """
                    UPDATE memory_candidates
                    SET status = 'approved', reviewed_by = :reviewed_by,
                        reviewed_at = :reviewed_at, updated_at = :reviewed_at
                    WHERE id = :id
                    """,
                ),
                {
                    "id": candidate_id,
                    "reviewed_by": principal.user_id,
                    "reviewed_at": now,
                },
            )
        return {
            "candidate_id": candidate_id,
            "memory_id": memory_id,
            "status": "approved",
            "approved_by": principal.user_id,
            "approved_at": now,
        }

    async def reject_memory_candidate(
        self,
        principal: AuthPrincipal,
        candidate_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Reject a candidate without ever creating an embedding."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        reason = reason.strip()
        if not reason:
            raise ValueError("rejection reason is required")
        now = datetime.now(timezone.utc)
        async with self._require_engine().begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE memory_candidates
                    SET status = 'rejected', reviewed_by = :reviewed_by,
                        reviewed_at = :reviewed_at,
                        rejection_reason = :reason, updated_at = :reviewed_at
                    WHERE id = :id AND tenant_id = :tenant_id
                      AND domain_id = :domain_id AND area_id = :area_id
                      AND status = 'pending_review'
                    """,
                ),
                {
                    "id": candidate_id,
                    "tenant_id": principal.tenant_id,
                    "domain_id": domain_id,
                    "area_id": area_id,
                    "reviewed_by": principal.user_id,
                    "reviewed_at": now,
                    "reason": reason,
                },
            )
        if not result.rowcount:
            raise BusinessNotFoundError(
                "pending memory candidate not found in this area",
            )
        return {
            "candidate_id": candidate_id,
            "status": "rejected",
            "reviewed_by": principal.user_id,
            "reviewed_at": now,
            "reason": reason,
        }

    async def search_approved_memories(
        self,
        principal: AuthPrincipal,
        *,
        query: str,
        agent_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search only approved active vectors inside the manager's area."""
        from sqlalchemy import text

        domain_id, area_id = self._require_area_manager(principal)
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        embedding = await self._embed_memory(query.strip())
        async with self._require_engine().connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT id, content, memory_type, metadata,
                               approved_by, approved_at,
                               1 - (embedding <=> CAST(:embedding AS vector))
                                   AS similarity
                        FROM reme_memories
                        WHERE tenant_id = :tenant_id
                          AND domain_id = :domain_id
                          AND area_id = :area_id
                          AND status = 'active'
                          AND approved_by IS NOT NULL
                          AND approved_at IS NOT NULL
                          AND (expires_at IS NULL OR expires_at > now())
                          AND (
                              :agent_id IS NULL OR agent_id IS NULL
                              OR agent_id = :agent_id
                          )
                        ORDER BY embedding <=> CAST(:embedding AS vector)
                        LIMIT :limit
                        """,
                        ),
                        {
                            "tenant_id": principal.tenant_id,
                            "domain_id": domain_id,
                            "area_id": area_id,
                            "agent_id": agent_id,
                            "embedding": _vector_literal(embedding),
                            "limit": limit,
                        },
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]
