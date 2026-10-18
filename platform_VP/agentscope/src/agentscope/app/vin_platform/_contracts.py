"""Versioned, strict contracts shared with the runtime/UI implementation."""

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from ..workforce.foundation.event_delivery import DurableJob


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


class CapabilityView(ExecutionContext):
    contract_version: Literal["vin-platform-1"] = CONTRACT_VERSION
    eligible: bool
    capabilities: dict[str, bool]


class WorkspaceView(Contract):
    id: str
    kind: Literal["personal", "operations", "administration"]
    label: str
    domain_id: str | None = None
    area_id: str | None = None


class WorkspaceState(Contract):
    contract_version: Literal["vin-platform-1"] = CONTRACT_VERSION
    active_workspace_id: str
    revision: int = Field(ge=0)
    authorization_revision: int = Field(ge=1)
    items: list[WorkspaceView]


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


class CatalogView(CatalogEntry):
    catalog_id: str
    permissions: list[Literal["view", "bind", "execute", "manage"]]


class CatalogPage(Contract):
    items: list[CatalogView]


class ResourceGrant(Contract):
    catalog_id: str
    subject_kind: Literal["user", "group", "role"]
    subject_id: str
    permissions: list[Literal["view", "bind", "execute", "manage"]]
    expires_at: datetime | None = None


class Pack(Contract):
    """A library pack: catalog resources granted to its group plus sample agents."""
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    catalog_ids: list[str] = Field(default_factory=list, max_length=50)
    template_agent_ids: list[str] = Field(default_factory=list, max_length=20)
    link_provider_id: str | None = Field(default=None, max_length=64)
    active: bool = True


class PackView(Pack):
    id: str
    revision: int
    installed: bool = False


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
    environment: Literal["production", "sandbox"] = "production"


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


class CustomerPlan(Contract):
    """C07 resident-visible plan, distinct from work-order approvals."""

    id: str
    title: str
    status: Literal["management_pending", "resident_pending", "approved", "rejected"]
    version: int = Field(ge=0)
    estimatedAmount: str
    steps: list[str]
    canDecide: bool


class PlanDecisionPayload(Contract):
    """SourceIntent.payload for action=plan-decision; version is the plan's."""

    plan_id: str
    expectedVersion: Annotated[StrictInt, Field(ge=0)]
    decision: Literal["approve", "reject"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class PersonalJobPage(Contract):
    """Internal C09 consumer page; not a public job/secret DTO."""

    items: list[DurableJob]
    next_cursor: str | None
    has_more: bool


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


Item = TypeVar("Item")


class AdminPage(Contract, Generic[Item]):
    contract_version: Literal["vin-platform-1"] = CONTRACT_VERSION
    items: list[Item]
    total: int
    offset: int
    limit: int
    next_offset: int | None


class PolicyView(Contract):
    subject: str
    revision: int
    active: bool
    policy: QuotaPolicy


class AdminCatalogView(CatalogEntry):
    catalog_id: str


class GrantView(ResourceGrant):
    id: str
    active: bool
    revision: int


class MembershipView(Contract):
    id: str
    user_id: str
    group_id: str
    domain_id: str | None
    area_id: str | None
    active: bool
    expires_at: datetime | None
    revision: int


class AccountView(Contract):
    user_id: str
    username: str
    role: str
    status: str
    eligible: bool
    revision: int


class LibraryDocumentView(Contract):
    document_id: str
    catalog_id: str
    knowledge_base_id: str
    owner_id: str
    filename: str
    status: str
    review_status: Literal["candidate", "approved", "retired"]
    version: str
    revision: str
    source_ref: str
    size: int
    reviewed_by: str | None
    effective_from: str | None
    effective_until: str | None


class DocumentReview(Contract):
    status: Literal["approved", "retired"]
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
