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

_CODE_EXECUTION_IDENTIFIERS = frozenset(
    {"bash", "powershell", "shell", "terminal", "sudo", "exec", "eval",
     "repl", "python", "javascript", "nodejs"},
)
_CODE_INPUT_FIELDS = frozenset(
    {"code", "command", "commands", "script", "scripts", "source_code",
     "shell_command", "python_code", "javascript_code", "script_path",
     "script_content", "function"},
)


def _normalise_identifiers(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def mcp_tool_executes_code(tool_name: str, input_schema: dict[str, Any]) -> bool:
    """Recognize execution tools before any permission-mode shortcuts."""
    name = _normalise_identifiers(re.sub(r"([a-z])([A-Z])", r"\1_\2", tool_name))
    if set(name.split("_")) & _CODE_EXECUTION_IDENTIFIERS or any(
        phrase in name for phrase in ("run_code", "execute_code", "run_script", "execute_script")
    ):
        return True
    # shortcut: opaque MCP capabilities still require a trusted provider;
    # replace identifier inference when the catalog defines execution metadata.
    def has_code_input(value: Any) -> bool:
        if isinstance(value, dict):
            if any(
                _normalise_identifiers(re.sub(r"([a-z])([A-Z])", r"\1_\2", key))
                in _CODE_INPUT_FIELDS
                for key in (value.get("properties") or {})
            ):
                return True
            return any(has_code_input(item) for item in value.values())
        if isinstance(value, list):
            return any(has_code_input(item) for item in value)
        return False

    return has_code_input(input_schema)


def mcp_tool_permission(
    tool_name: str,
    annotations: Any,
    input_schema: dict[str, Any] | None = None,
) -> PermissionDecision:
    """Deny code execution; require HITL for sensitive business operations."""
    if mcp_tool_executes_code(tool_name, input_schema or {}):
        return PermissionDecision(
            behavior=PermissionBehavior.DENY,
            message="Code and shell execution is disabled by server policy.",
            decision_reason="Server code execution is forbidden",
        )
    if mcp_tool_requires_confirmation(tool_name, annotations, input_schema):
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
    if mcp_tool_executes_code(tool_name, input_schema or {}):
        return True
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
    sensitive_action = bool(
        action_tokens & _SENSITIVE_ACTION_IDENTIFIERS,
    ) or any(
        phrase in action_identifiers for phrase in _SENSITIVE_ACTION_PHRASES
    )
    pii = bool(pii_tokens & _PII_IDENTIFIERS) or any(
        phrase in pii_identifiers for phrase in _PII_PHRASES
    )
    return destructive or sensitive_action or pii
