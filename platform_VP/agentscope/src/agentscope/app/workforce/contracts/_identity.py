# -*- coding: utf-8 -*-
"""Identity, ownership scope, and partner audience contracts."""

from enum import StrEnum

from pydantic import Field, model_validator

from ._base import OpaqueId, WorkforceModel


class ManagerRole(StrEnum):
    """The only interactive product role in Workforce v1."""

    AREA_MANAGER = "AREA_MANAGER"


class ActorKind(StrEnum):
    """Authenticated actor source; this is not a product role."""

    MANAGER = "manager"
    PARTNER = "partner"
    SYSTEM = "system"


class CredentialPurpose(StrEnum):
    """Machine credential purpose used for least-privilege authorization."""

    CUSTOMER_API = "customer_api"
    PROVIDER_EVENTS = "provider_events"


class Scope(WorkforceModel):
    """Immutable owner boundary for every Workforce resource."""

    tenant_id: OpaqueId
    domain_id: OpaqueId
    area_id: OpaqueId
    manager_account_id: OpaqueId


class ActorContext(WorkforceModel):
    """Server-derived identity used for authorization and audit."""

    kind: ActorKind
    actor_id: OpaqueId
    role: ManagerRole | None = None
    partner_client_id: OpaqueId | None = None
    credential_id: OpaqueId | None = None
    credential_purpose: CredentialPurpose | None = None
    external_user_id: OpaqueId | None = None
    authentication_source: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_actor_shape(self) -> "ActorContext":
        manager_without_role = (
            self.kind == ActorKind.MANAGER
            and self.role != ManagerRole.AREA_MANAGER
        )
        if manager_without_role:
            raise ValueError("manager actor requires AREA_MANAGER role")
        if self.kind == ActorKind.PARTNER:
            if self.partner_client_id is None or self.credential_id is None:
                raise ValueError(
                    "partner actor requires partner_client_id "
                    "and credential_id",
                )
            if self.credential_purpose is None:
                raise ValueError("partner actor requires credential_purpose")
        return self


class PartnerAudience(WorkforceModel):
    """End-user and conversation boundary asserted by a trusted backend."""

    partner_client_id: OpaqueId
    external_user_id: OpaqueId
    external_conversation_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    residence_id: OpaqueId | None = None
