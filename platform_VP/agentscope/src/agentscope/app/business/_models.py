# -*- coding: utf-8 -*-
"""Value objects for area-scoped platform workflows."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class PartnerPrincipal:
    """Identity derived from a verified domain-level partner API key."""

    key_id: str
    client_id: str
    tenant_id: str
    domain_id: str


@dataclass(slots=True, frozen=True)
class IssuedPartnerApiKey:
    """One-time response returned when a partner credential is issued."""

    client_id: str
    key_id: str
    domain_id: str
    api_key: str
    expires_at: datetime | None
