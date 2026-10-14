"""Risk-based default permission policy for partner MCP tools."""

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
    """Auto-run ordinary MCP tools and require HITL for risky operations.

    ``force_confirmation`` is set when the agent's owner marked the tool as
    "requires customer consent" (Agent Spec), whatever its name says.
    """
    if force_confirmation or mcp_tool_requires_confirmation(
        tool_name,
        annotations,
        input_schema,
    ):
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message=(
                "This MCP tool can perform a sensitive or destructive action "
                "and requires explicit user confirmation."
            ),
            decision_reason="Sensitive MCP operation",
            bypass_immune=True,
        )

    # shortcut: infer risk from standard annotations and identifiers; require
    # an explicit risk extension if the partner contract later defines one.
    return PermissionDecision(
        behavior=PermissionBehavior.ALLOW,
        message="This MCP tool is covered by the automatic low-risk policy.",
        decision_reason="Low-risk MCP operation",
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
