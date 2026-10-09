from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestResult(Strict):
    request_id: str
    request_status: str
    external_ticket_id: str | None
    conversation_id: str
    workflow_id: str
    workflow_state: str
    workflow_revision: int
    next_action: str
    ticket_id: str | None = None
    result: dict | None
    error: dict | None
    accepted_at: str
    completed_at: str | None
    status_url: str
    conversation_url: str
    event_stream_url: str


class Message(Strict):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=20000)
    asset_ids: list[str] = Field(default_factory=list, max_length=8)


class Command(Strict):
    schema_version: Literal["1"] = "1"
    command_type: Literal["start_workflow", "workflow_reply"]
    external_request_id: str = Field(min_length=1, max_length=200)
    external_management_ref: str = Field(min_length=1, max_length=128)
    external_user_id: str = Field(min_length=1, max_length=200)
    external_ticket_id: str | None = Field(default=None, min_length=1, max_length=200)
    external_conversation_id: str = Field(min_length=1, max_length=200)
    workflow_id: str | None = None
    residence_id: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = None
    message: Message

    @field_validator("external_request_id", "external_management_ref", "external_user_id",
                     "external_ticket_id", "external_conversation_id", "residence_id")
    @classmethod
    def opaque(cls, value):
        if value and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("control characters are not allowed in identifiers")
        return value

    @model_validator(mode="after")
    def reference(self):
        if self.command_type == "start_workflow" and self.workflow_id:
            raise ValueError("start_workflow must not include workflow_id")
        return self


class RouteConfirm(Strict):
    schema_version: Literal["1"] = "1"
    external_management_ref: str
    expected_revision: int = Field(ge=1)


class Residence(Strict):
    schema_version: Literal["1"] = "1"
    external_user_id: str
    external_management_ref: str
    status: Literal["active", "inactive"]
    expected_revision: int = Field(ge=0)


class Decision(Strict):
    schema_version: Literal["1"] = "1"
    external_request_id: str = Field(min_length=1, max_length=200)
    external_user_id: str
    external_ticket_id: str | None = None
    external_conversation_id: str
    workflow_id: str
    decision: Literal["approve", "reject"]
    expected_revision: int = Field(ge=1)
    arguments_hash: str
    quote_ref: str


class Close(Strict):
    schema_version: Literal["1"] = "1"
    external_request_id: str = Field(min_length=1, max_length=200)
    external_user_id: str
    external_ticket_id: str | None = None
    external_conversation_id: str
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=200)
    stop_tracking_only: bool = False


class ProviderEvent(Strict):
    schema_version: Literal["1"] = "1"
    external_event_id: str = Field(min_length=1, max_length=200)
    external_job_id: str | None = Field(default=None, max_length=200)
    client_reference: str | None = Field(default=None, max_length=200)
    event_type: str = Field(min_length=1, max_length=200)
    provider_version: int | None = Field(default=None, ge=1)
    occurred_at: str
    data: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def correlation(self):
        if not self.external_job_id and not self.client_reference:
            raise ValueError("a job ID or client reference is required")
        from datetime import datetime
        dt = datetime.fromisoformat(self.occurred_at)
        if not dt.tzinfo:
            raise ValueError("occurred_at must have a timezone")
        import json
        if len(json.dumps(self.data).encode()) > 65536:
            raise ValueError("event data exceeds 64 KiB")
        return self


class Upload(Strict):
    external_management_ref: str
    external_user_id: str
    external_ticket_id: str
    external_conversation_id: str
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size: int = Field(ge=1, le=10485760)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClientCreate(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    purpose: Literal["customer", "provider"]
    operations: list[Literal["submit_request", "reply", "read_result", "receive_events", "submit_consent",
                            "close_workflow", "confirm_route", "sync_residence", "publish_job_event",
                            "read_event_receipt", "upload_asset"]]
    expires: float | None = None
    settings: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def provider_policy(self):
        if self.purpose == "customer":
            if self.settings:
                raise ValueError("customer settings must be empty")
            return self
        if set(self.settings) - {"event_map", "transitions"}:
            raise ValueError("unknown provider settings")
        states = {"pending", "assigned", "offered", "accepted", "in_progress", "confirmed", "completed", "cancelled", "failed", "unknown"}
        from jsonschema import Draft202012Validator, SchemaError
        for name, mapping in self.settings.get("event_map", {}).items():
            if not name or len(name) > 200 or set(mapping) - {"status", "mode", "schema", "public_fields"}:
                raise ValueError("invalid event mapping")
            if mapping.get("status") not in states or mapping.get("mode", "snapshot") not in {"snapshot", "delta"}:
                raise ValueError("invalid mapped status or event mode")
            schema = mapping.get("schema", {"type": "object", "additionalProperties": False})
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise ValueError("invalid provider event JSON schema") from exc
            if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
                raise ValueError("event data needs a closed object schema")
            if set(mapping.get("public_fields", [])) - set(schema.get("properties", {})):
                raise ValueError("public fields must be declared in the event schema")
        for before, after in self.settings.get("transitions", {}).items():
            if before not in states or not isinstance(after, list) or set(after) - states:
                raise ValueError("invalid operation transition map")
        return self


class RouteCreate(Strict):
    client_id: str
    external_management_ref: str = Field(min_length=1, max_length=128)
    workspace: str = Field(min_length=1, max_length=200)
    manager_ref: str = Field(min_length=1, max_length=200)
    leader_profile: str
    ticket_binding_mode: Literal["required", "optional"] = "required"
    require_residence: bool = True
    read_only_auto_close: bool = True
    budget_micros: int = Field(default=500000, ge=1)
    budget_tokens: int = Field(default=100000, ge=1)
    max_active_workflows: int = Field(default=20, ge=1, le=1000)
    asset_capability: bool = False
    integration_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list, max_length=100)


class ToolPolicy(Strict):
    read_only: bool = False
    requires_consent: bool = True
    approval_summary: str = Field(default="Approve this operation", max_length=2000)
    tracks_events: bool = False


class IntegrationCreate(Strict):
    # For tracking integrations this is also the provider-purpose client ID.
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,50}$")
    url: str = Field(max_length=2000)
    headers: dict[str, str] = Field(default_factory=dict)
    context_signing_key: str = Field(min_length=32, max_length=500)
    tools: dict[str, ToolPolicy] = Field(min_length=1, max_length=100)

    @field_validator("url")
    @classmethod
    def endpoint(cls, value):
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("MCP URL must be an HTTP endpoint without credentials or fragment")
        return value


class ReviseRoute(RouteCreate):
    expected_revision: int = Field(ge=1)


class Reconcile(Strict):
    expected_status: Literal["unknown", "started"]
    status: Literal["completed", "confirmed", "failed", "cancelled", "pending"]
    external_job_id: str | None = None
    evidence: str = Field(min_length=1, max_length=4000)


class KnowledgeDocument(Strict):
    knowledge_base_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    document_key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=100000)
    source: str = Field(default="", max_length=2000)
