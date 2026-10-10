"""Internal persistence values, not a second shared DTO/Scope package."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4


class OrchestrationError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise OrchestrationError(code)


def read(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)


def scope_key(scope: Any) -> tuple[str, str, str, str]:
    """Read the Foundation-owned Scope structurally; never construct authority."""
    result = tuple(read(scope, key) for key in (
        "tenant_id", "domain_id", "area_id", "manager_account_id",
    ))
    require(all(isinstance(x, str) and x for x in result), "SCOPE_REQUIRED")
    return result


def new_id() -> str:
    return str(uuid4())


def snapshot(value: Any) -> dict:
    """Normalize Foundation/Lifecycle DTOs at the module boundary."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    require(isinstance(value, Mapping), "DTO_INVALID")
    return deepcopy(dict(value))


def stored_scope(value: Any) -> tuple:
    if isinstance(value, (tuple, list)):
        require(len(value) == 4 and all(isinstance(x, str) and x for x in value), "SCOPE_REQUIRED")
        return tuple(value)
    return scope_key(value)


@dataclass
class StoredConversation:
    conversation_id: str
    scope: tuple
    mode: str
    timezone: str
    state_revision: int = 0
    active_run_id: str | None = None
    direct_agent_id: str | None = None
    facts: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    proposals: dict = field(default_factory=dict)
    selected_refs: dict = field(default_factory=dict)
    pending_questions: dict = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)


@dataclass
class StoredRun:
    run_id: str
    scope: tuple
    conversation_id: str
    group_id: str
    leader_session_id: str
    members: list[dict]
    catalog_revision: str
    requirements: tuple[str, ...]
    status: str = "materializing"
    revision: int = 0
    max_handoffs: int = 20
    max_concurrent: int = 4
    token_limit: int = 100_000
    cost_limit_minor: int = 1_000_000
    used_tokens: int = 0
    used_cost_minor: int = 0
    handoffs: dict = field(default_factory=dict)
    pending_members: list[dict] = field(default_factory=list)
    membership_operation_id: str | None = None


@dataclass
class StoredWorkflow:
    workflow_id: str
    scope: tuple
    conversation_id: str
    group_id: str
    audience: dict
    route_id: str
    route_revision: int
    state: str = "accepted"
    next_action: str = "watch_request"
    revision: int = 0
    checkpoint: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)


@dataclass
class StoredCommand:
    request_id: str
    scope: tuple
    partner_client_id: str
    external_request_id: str
    workflow_id: str
    payload_hash: str
    status: str = "accepted"
    revision: int = 0
    result: dict = field(default_factory=dict)
    accepted_at: str = ""
    completed_at: str | None = None


def detached(value: Any) -> Any:
    """Prevent mutable repository values escaping across requests."""
    return deepcopy(value)
