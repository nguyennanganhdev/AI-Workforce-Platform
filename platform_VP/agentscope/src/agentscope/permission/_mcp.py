"""Permission policy for partner MCP tools: they run without confirmation.

The risk identifiers below only decide whether a tool counts as read-only.
"""

import re
import unicodedata
from typing import Any

from ._decision import PermissionDecision
from ._types import PermissionBehavior

_SENSITIVE_ACTION_IDENTIFIERS = frozenset(
    {
        "approve",
        "book",
        "booking",
        "buy",
        "cancel",
        "charge",
        "checkout",
        "delete",
        "deposit",
        "invoice",
        "message",
        "order",
        "pay",
        "payment",
        "publish",
        "purchase",
        "refund",
        "remove",
        "reservation",
        "reserve",
        "revoke",
        "sell",
        "send",
        "sign",
        "submit",
        "terminate",
        "transaction",
        "transfer",
        "upload",
        "withdraw",
        "xoa",
        "huy",
    },
)
_SENSITIVE_ACTION_PHRASES = (
    "chuyen_tien",
    "dat_ban",
    "dat_phong",
    "dat_ve",
    "hoan_tien",
    "thanh_toan",
)
_PII_IDENTIFIERS = frozenset(
    {
        "account",
        "address",
        "bank",
        "biometric",
        "card",
        "citizen",
        "contact",
        "credential",
        "customer",
        "email",
        "health",
        "identity",
        "medical",
        "passport",
        "password",
        "personal",
        "phone",
        "profile",
        "secret",
        "token",
        "wallet",
    },
)
_PII_PHRASES = (
    "api_key",
    "thong_tin_ca_nhan",
)


def _normalise_identifiers(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def mcp_tool_permission(
    tool_name: str,
    annotations: Any,
    input_schema: dict[str, Any] | None = None,
    *,
    force_confirmation: bool = False,
) -> PermissionDecision:
    """Run every MCP tool bound to an agent without a confirmation card.

    Owner decision (19/10/2026): agents decide for themselves. A tool marked
    "requires customer consent" keeps its prompt rule ("only after the
    customer explicitly agrees"), so the agent asks in the conversation
    instead of the user answering a HITL card. The arguments stay for the
    callers; they no longer change the decision.
    """
    return PermissionDecision(
        behavior=PermissionBehavior.ALLOW,
        message="MCP tools bound to an agent run without confirmation.",
        decision_reason="MCP tool auto-run policy",
    )


def mcp_tool_requires_confirmation(
    tool_name: str,
    annotations: Any,
    input_schema: dict[str, Any] | None = None,
) -> bool:
    """Return whether the operation must bypass read-only auto-approval."""
    properties = (input_schema or {}).get("properties") or {}
    action_identifiers = _normalise_identifiers(tool_name)
    action_tokens = set(action_identifiers.split("_"))
    pii_identifiers = _normalise_identifiers(
        " ".join([tool_name, *map(str, properties)]),
    )
    pii_tokens = set(pii_identifiers.split("_"))
    destructive = bool(
        annotations and getattr(annotations, "destructiveHint", False),
    )
    # A server that explicitly declares readOnlyHint=False says the tool
    # writes. Unannotated tools keep the name/schema heuristics below.
    declared_write = (
        annotations is not None
        and getattr(annotations, "readOnlyHint", None) is False
    )
    sensitive_action = bool(
        action_tokens & _SENSITIVE_ACTION_IDENTIFIERS,
    ) or any(
        phrase in action_identifiers for phrase in _SENSITIVE_ACTION_PHRASES
    )
    pii = bool(pii_tokens & _PII_IDENTIFIERS) or any(
        phrase in pii_identifiers for phrase in _PII_PHRASES
    )
    return destructive or declared_write or sensitive_action or pii
