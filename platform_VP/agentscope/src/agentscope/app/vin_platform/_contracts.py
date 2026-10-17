"""Versioned, strict contracts shared with the runtime/UI implementation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CONTRACT_VERSION = "vin-platform-1"


class PlatformError(Exception):
    def __init__(self, code: str, status: int = 403, **safe_details):
        super().__init__(code)
        self.code, self.status, self.details = code, status, safe_details


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionContext(Contract):
    tenant_id: str
    initiator_user_id: str
    billing_subject_id: str
    workspace_id: str
    role: str
    authorization_revision: int = 1
    acting_link_id: str | None = None
    purpose: str = "chat"
    environment: Literal["production", "sandbox"] = "production"


class QuotaPolicy(Contract):
    daily_tokens: int = Field(ge=0)
    monthly_tokens: int = Field(ge=0)
    max_output_tokens: int = Field(default=1024, ge=1, le=32768)
    max_concurrency: int = Field(default=2, ge=1, le=100)
    storage_bytes: int = Field(default=0, ge=0)
    max_file_bytes: int = Field(default=0, ge=0)
    embedding_daily_tokens: int = Field(default=0, ge=0)
    models: list[str] = Field(default_factory=list, max_length=50)
    enabled: bool = False


class CatalogEntry(Contract):
    kind: Literal["credential", "agent", "knowledge_base", "mcp", "skill"]
    resource_id: str = Field(min_length=1, max_length=255)
    owner_id: str = Field(min_length=1, max_length=255)
    version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=3000)
    environment: Literal["production", "sandbox"] = "production"
    model_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    active: bool = True


class ResourceGrant(Contract):
    catalog_id: str
    subject_kind: Literal["user", "group", "role"]
    subject_id: str
    permissions: list[Literal["view", "bind", "execute", "manage"]]
    expires_at: datetime | None = None


class DomainProvider(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    issuer: str
    client_id: str
    authorization_url: str
    token_url: str
    api_base_url: str
    redirect_uri: str
    client_secret_ref: str
    scopes: list[str] = Field(default_factory=lambda: ["self", "requests"])
    active: bool = False


class ServiceRequest(Contract):
    link_id: str
    idempotency_key: str = Field(min_length=16, max_length=128)
    request: dict


class SourceIntent(Contract):
    case_id: str
    action: str
    expected_version: int = Field(ge=1)
    payload: dict
    idempotency_key: str = Field(min_length=16, max_length=128)


class CaseEvent(Contract):
    schema_version: Literal["vin-case-1"] = "vin-case-1"
    event_id: str
    case_id: str
    sequence: int = Field(ge=1)
    canonical_version: int = Field(ge=1)
    event_type: str
    occurred_at: datetime
    audience: Literal["customer", "operator"]
    data: dict


class AutomationSpec(Contract):
    kind: Literal["schedule", "channel", "delivery", "sandbox", "derived"]
    payload: dict
    expected_revision: int = Field(default=0, ge=0)
