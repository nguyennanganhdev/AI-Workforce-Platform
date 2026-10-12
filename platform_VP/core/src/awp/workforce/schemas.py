"""Request bodies: partner onboarding (contract 8) and admin (spec 7.3, 7.4)."""
from __future__ import annotations

import string
from datetime import datetime, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StrictInt,
                      field_validator, model_validator)

from .common import has_control
from .partner_result import DONE_WORDS, FAILED_WORDS

KNOWN_END = DONE_WORDS | FAILED_WORDS  # the words that say an operation ended well or badly

CAPABILITIES = ("attach_asset",)  # A3


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _clean(v: str) -> str:
    if has_control(v):
        raise ValueError("control characters are not allowed")
    return v


# Ids the partner chooses (contract 6.2) and the management ref.
ExtId = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_clean)]
MgmtRef = Annotated[str, Field(min_length=1, max_length=128), AfterValidator(_clean)]
Slug = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")]
SchemaVersion = Literal["1"]


def _zone(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError("not an IANA timezone")
    return v


Zone = Annotated[str, Field(min_length=1, max_length=64), AfterValidator(_zone)]


# ---- partner onboarding -------------------------------------------------
class ConfirmRouteIn(Strict):
    schema_version: SchemaVersion
    external_management_ref: MgmtRef
    expected_revision: StrictInt = Field(ge=0)


class ResidenceIn(Strict):
    schema_version: SchemaVersion
    external_user_id: ExtId
    external_management_ref: MgmtRef
    status: Literal["active", "inactive"]
    expected_revision: StrictInt | None = Field(default=None, ge=0)


# ---- partner commands (contract 9.1, 9.2, 9.9) -------------------------------
def _not_blank(v: str) -> str:
    """NUL characters go: PostgreSQL cannot store one in text, and no message needs it (the storage is the same on SQLite)."""
    v = v.replace("\x00", "")
    if not v.strip():
        raise ValueError("text must not be blank")
    return v


class MessageIn(Strict):
    type: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=20000), AfterValidator(_not_blank)]


class ImageIn(Strict):
    """A message that carries an image (spec A3: beyond contract v1, only for a client with the capability attach_asset).
    The image is named by the id its upload returned, never by an address; `text` is what the resident wrote with it."""
    type: Literal["image"]
    asset_id: Annotated[str, Field(pattern=r"^ast_[0-9a-f]{32}$")]
    text: Annotated[str, Field(min_length=1, max_length=20000), AfterValidator(_not_blank)] | None = None


class RequestIn(Strict):
    """start_workflow and workflow_reply share one envelope; which fields mean what is the service's job."""
    schema_version: SchemaVersion
    command_type: Literal["start_workflow", "workflow_reply"]
    external_request_id: ExtId
    external_management_ref: MgmtRef
    external_user_id: ExtId
    external_ticket_id: ExtId | None = None
    external_conversation_id: ExtId
    workflow_id: ExtId | None = None
    residence_id: ExtId | None = None
    timezone: Zone | None = None
    message: MessageIn


class ImageRequestIn(RequestIn):
    message: ImageIn


STOP_TRACKING = "resident_requested_stop_tracking"


class CloseIn(Strict):
    schema_version: SchemaVersion
    external_request_id: ExtId
    external_user_id: ExtId
    external_ticket_id: ExtId | None = None
    external_conversation_id: ExtId
    expected_revision: StrictInt = Field(ge=0)
    reason: ExtId  # the contract fixes no format; only stop-tracking has a required value (service)
    stop_tracking_only: StrictBool = False


class DecisionIn(Strict):
    """POST /partner/approvals/{id}/decision (contract 9.8). `expected_revision` is the workflow's (A1)."""
    schema_version: SchemaVersion
    external_request_id: ExtId
    external_user_id: ExtId
    external_ticket_id: ExtId | None = None
    external_conversation_id: ExtId
    workflow_id: ExtId
    decision: Literal["approve", "reject"]
    expected_revision: StrictInt = Field(ge=0)
    arguments_hash: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_clean)]
    quote_ref: ExtId | None = None


# ---- admin: clients and keys ---------------------------------------------
class ClientIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    domain: Slug
    environment: Literal["sandbox", "production"]
    capabilities: list[Literal["attach_asset"]] = []


class ClientPatch(Strict):
    """What an operator may change on a client: its capabilities (the whole list, as it should be from now on)."""
    capabilities: list[Literal["attach_asset"]] = Field(max_length=len(CAPABILITIES))

    @field_validator("capabilities")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("capabilities must be unique")
        return v


def _future(v: datetime | None) -> datetime | None:
    if v is None:
        return None
    v = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if v <= datetime.now(timezone.utc):
        raise ValueError("expires_at must be in the future")
    return v


Expiry = Annotated[datetime | None, AfterValidator(_future)]


class KeyIn(Strict):
    operations: list[str] = Field(min_length=1, max_length=16)
    routes: list[str] = Field(default=["*"], min_length=1, max_length=100)
    expires_at: Expiry = None

    @field_validator("operations")
    @classmethod
    def _unique_ops(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("operations must be unique")
        return v

    @model_validator(mode="after")
    def _routes(self):
        if "*" in self.routes and len(self.routes) > 1:
            raise ValueError('"*" cannot be combined with route ids')
        if len(set(self.routes)) != len(self.routes):
            raise ValueError("routes must be unique")
        return self


class ProviderKeyIn(KeyIn):
    operations: list[str] = Field(default=["publish_job_event", "read_event_receipt"], min_length=1)
    routes: list[str] = Field(default=["*"], min_length=1, max_length=100)


class RotateIn(Strict):
    expires_at: Expiry = None


# ---- admin: routes ---------------------------------------------------------
class PhraseRuleIn(Strict):
    phrases: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=300)
    unless: list[str] = Field(default=[], max_length=20)


class RulesIn(Strict):
    safe_reply: str = Field(default="", max_length=1000)
    phrase_rules: list[PhraseRuleIn] = Field(default=[], max_length=50)


class PolicyIn(Strict):
    auto_close_read_only: StrictBool = True
    approval_ttl_seconds: StrictInt | None = Field(default=None, ge=60, le=30 * 24 * 3600)


class RouteConfig(Strict):
    ticket_binding_mode: Literal["required", "none"] = "required"
    residence_required: StrictBool = False
    timezone: Zone = "UTC"
    wait_seconds: Annotated[float, Field(strict=True, ge=0, le=120)] | None = None
    rules: RulesIn = RulesIn()
    policy: PolicyIn = PolicyIn()


class RouteIn(Strict):
    external_management_ref: MgmtRef
    leader_profile: Slug
    manager_id: Annotated[str, Field(min_length=1, max_length=48)]  # the management account the route belongs to (M6)
    config: RouteConfig = RouteConfig()


class ReplaceRouteIn(Strict):
    external_management_ref: MgmtRef | None = None
    leader_profile: Slug | None = None
    config: RouteConfig | None = None


class ManagerIn(Strict):
    name: str = Field(min_length=1, max_length=120)


class ManagerKeyIn(Strict):
    expires_at: Expiry = None


# ---- admin: integrations (event schema, spec 7.3) --------------------------
Ident = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,39}$")]
EventType = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,63}$")]
Label = Annotated[str, Field(min_length=1, max_length=40)]


class EventDef(Strict):
    status: Label
    rank: StrictInt = Field(ge=0, le=1000)
    terminal: StrictBool = False
    outcome: Label | None = None
    public_status: Label | None = None
    public_fields: list[Ident] = Field(default=[], max_length=30)
    message: str | None = Field(default=None, min_length=1, max_length=500)
    wake: StrictBool = False
    evidence: StrictBool = False
    reopen: StrictBool = False  # a correction: the only kind of event that may follow a finished operation or lower its rank
    # What a public field must be when it is shown: text (the default: a non-empty line, or a number that is not
    # negative) or count (a whole number, 0 or more). An event whose data break it is refused at the door (422).
    field_types: dict[Ident, Literal["text", "count"]] = Field(default={}, max_length=30)

    @model_validator(mode="after")
    def _shape(self):
        if len(set(self.public_fields)) != len(self.public_fields):
            raise ValueError("public_fields must be unique")
        if set(self.field_types) - set(self.public_fields):
            raise ValueError("field_types may only type fields listed in public_fields")
        if self.terminal and (self.outcome or self.status).lower() not in KNOWN_END:
            raise ValueError("a terminal event must say how it ended: its outcome (or, without one, its status) has to be one "
                             f"of {sorted(KNOWN_END)}; put the partner's own word in status and the ending in outcome")
        if self.message:
            for _, name, spec, conv in string.Formatter().parse(self.message):
                if name is None:
                    continue
                if name not in self.public_fields or spec or conv:
                    raise ValueError(f"message may only use plain {{field}} placeholders "
                                     f"from public_fields, got {name!r}")
        return self


class EventSchema(Strict):
    version: Label
    version_mode: Literal["snapshot", "delta"]
    events: dict[EventType, EventDef] = Field(min_length=1, max_length=200)


class IntegrationIn(Strict):
    event_schema: EventSchema


# ---- admin: a route's partner tools over MCP (spec 4, 8) ---------------------------------------------------------------
Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]  # what the model sees: a function name
McpTool = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,120}$")]  # the partner's own name for it
ArgName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
HeaderName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9-]{0,63}$")]
HeaderValue = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_clean)]
NONCE_ARG = "idempotency_nonce"  # the argument the platform adds to an action so a repeat can be deliberate
PROTOCOL_HEADERS = {"host", "content-length", "content-type", "accept", "connection", "transfer-encoding",
                    "mcp-session-id", "mcp-protocol-version", "upgrade", "te"}


class McpServerIn(Strict):
    name: Name
    url: Annotated[str, Field(min_length=8, max_length=2000)]
    transport: Literal["streamable_http"] = "streamable_http"
    headers: dict[HeaderName, HeaderValue] = Field(default={}, max_length=20)
    timeout: float = Field(default=8.0, ge=1.0, le=10.0)  # connecting and listing; a call has its own (tool call_timeout)

    @field_validator("headers")
    @classmethod
    def _headers(cls, v: dict[str, str]) -> dict[str, str]:
        bad = sorted(k for k in v if k.lower() in PROTOCOL_HEADERS)
        if bad:
            raise ValueError(f"these headers belong to the protocol: {bad}")
        return v


class McpServersIn(Strict):
    servers: list[McpServerIn] = Field(max_length=20)

    @model_validator(mode="after")
    def _unique(self):
        if len({s.name for s in self.servers}) != len(self.servers):
            raise ValueError("server names must be unique")
        return self


class ToolIn(Strict):
    name: Name
    server: Name
    mcp_tool: McpTool
    kind: Literal["lookup", "action"]
    read_only: StrictBool = False
    # An action asks the resident first unless a waiver says why it need not (M5). Left out: yes, or no when a waiver is given.
    # On a look-up the waiver is the reason a person gave for calling a tool read-only that its server does not.
    requires_consent: StrictBool | None = None
    consent_waiver: str | None = Field(default=None, min_length=1, max_length=300)
    tracking: Literal["none", "events", "status_query"] = "none"
    client_reference_arg: ArgName | None = None
    idempotency_arg: ArgName | None = None
    status_tool: McpTool | None = None
    integration_id: Annotated[str, Field(min_length=1, max_length=48)] | None = None  # whose provider events follow it
    consent_summary: str | None = Field(default=None, min_length=1, max_length=300)
    call_timeout: float = Field(default=8.0, ge=0.5, le=9.0)  # below the 10 s after which AgentScope would offload (A8)
    description_override: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _shape(self):
        if NONCE_ARG in (self.client_reference_arg, self.idempotency_arg):
            raise ValueError(f"{NONCE_ARG} is reserved for the platform")
        if self.kind == "lookup":
            extra = [n for n, v in (("requires_consent", self.requires_consent), ("tracking", self.tracking != "none"),
                                    ("integration_id", self.integration_id),
                                    ("client_reference_arg", self.client_reference_arg), ("idempotency_arg", self.idempotency_arg),
                                    ("status_tool", self.status_tool), ("consent_summary", self.consent_summary)) if v]
            if extra:
                raise ValueError(f"a look-up changes nothing and takes no {extra}")
            self.requires_consent = False
            return self
        if self.read_only:
            raise ValueError("an action cannot be read_only")
        if self.requires_consent is None:
            self.requires_consent = self.consent_waiver is None
        if not self.requires_consent and not self.consent_waiver:
            raise ValueError("an action asks the resident for consent; to turn that off give consent_waiver (the reason)")
        if self.requires_consent and self.consent_waiver:
            raise ValueError("consent_waiver belongs to an action with requires_consent false")
        if self.consent_summary and not self.requires_consent:
            raise ValueError("consent_summary belongs to a tool that requires_consent")
        if self.tracking == "status_query" and not (self.status_tool and self.client_reference_arg):
            raise ValueError("tracking status_query needs status_tool and client_reference_arg")
        if self.tracking == "events" and not (self.client_reference_arg or self.idempotency_arg):
            raise ValueError("tracking events needs client_reference_arg or idempotency_arg: a provider event is "
                             "matched to the request by the reference the platform sends")
        if self.status_tool and self.tracking != "status_query":
            raise ValueError("status_tool belongs to tracking status_query")
        if self.integration_id and self.tracking != "events":
            raise ValueError("integration_id belongs to tracking events: it names who sends the events")
        return self


class ToolsIn(Strict):
    tools: list[ToolIn] = Field(max_length=100)

    @model_validator(mode="after")
    def _unique(self):
        if len({x.name for x in self.tools}) != len(self.tools):
            raise ValueError("tool names must be unique")
        return self


class ToolPatch(Strict):
    """PATCH of one tool of the store: only what is sent changes, and the result must be a valid tool (ToolIn).
    `status` activates a proposed tool or puts an active one back."""
    status: Literal["active", "proposed"] | None = None
    kind: Literal["lookup", "action"] | None = None
    read_only: StrictBool | None = None
    requires_consent: StrictBool | None = None
    consent_waiver: str | None = Field(default=None, min_length=1, max_length=300)
    tracking: Literal["none", "events", "status_query"] | None = None
    client_reference_arg: ArgName | None = None
    idempotency_arg: ArgName | None = None
    status_tool: McpTool | None = None
    integration_id: Annotated[str, Field(min_length=1, max_length=48)] | None = None
    consent_summary: str | None = Field(default=None, min_length=1, max_length=300)
    call_timeout: float | None = Field(default=None, ge=0.5, le=9.0)
    description_override: str | None = Field(default=None, min_length=1, max_length=1000)


class ResolveIn(Strict):
    action: Literal["resume", "close"]


# ---- provider events (contract 10.1) ---------------------------------------------------------------------------
MAX_EVENT_DATA = 64 * 1024  # contract 6.2


def _rfc3339(v: str) -> str:
    try:
        stamp = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("occurred_at must be an RFC 3339 time")
    if stamp.tzinfo is None:
        raise ValueError("occurred_at needs a time zone (Z or an offset)")
    return v


class ProviderEventIn(Strict):
    """What a provider may send. Nothing that names a manager, a conversation or a workflow: the platform looks
    those up from the operation (an unknown field is a 422, so a provider cannot even try)."""
    schema_version: SchemaVersion
    external_event_id: ExtId
    external_job_id: ExtId | None = None
    client_reference: ExtId | None = None
    event_type: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,63}$")]
    provider_version: StrictInt | None = Field(default=None, ge=0, le=2**53)
    occurred_at: Annotated[str, Field(min_length=20, max_length=40), AfterValidator(_rfc3339)]
    data: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _shape(self):
        if not (self.external_job_id or self.client_reference):
            raise ValueError("external_job_id or client_reference is required")
        return self
