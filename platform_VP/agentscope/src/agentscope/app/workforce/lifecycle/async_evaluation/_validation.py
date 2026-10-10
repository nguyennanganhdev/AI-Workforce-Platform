"""Fail-closed policy validation until shared detailed policy DTO is
exported."""

from typing import Any, Dict, Tuple


def validate_policy(
    policy: Dict[str, Any], capabilities: Tuple[str, ...]
) -> Tuple[str, ...]:
    blockers = []
    required = (
        "schema_version",
        "capabilities",
        "event_types",
        "required_facts",
        "completion_condition",
        "human_confirmation",
        "timeout_behavior",
    )
    if (
        any(key not in policy for key in required)
        or policy.get("schema_version") != "1"
    ):
        blockers.append("ASYNC_POLICY_INVALID")
    for key in ("capabilities", "event_types", "required_facts"):
        values = policy.get(key)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(item, str) or not item for item in values)
        ):
            blockers.append("ASYNC_POLICY_INVALID")
    available = policy.get("capabilities", [])
    if not isinstance(available, list) or not set(capabilities).issubset(
        available
    ):
        blockers.append("ASYNC_CAPABILITY_COVERAGE")
    if (
        not isinstance(policy.get("completion_condition"), str)
        or not policy.get("completion_condition")
        or not isinstance(policy.get("human_confirmation"), bool)
        or policy.get("timeout_behavior")
        not in ("status_query", "needs_attention")
    ):
        blockers.append("ASYNC_POLICY_INVALID")
    if set(policy).intersection(
        {
            "ticket_id",
            "job_id",
            "endpoint",
            "workflow_id",
            "group_id",
            "roster",
            "external_ticket_id",
        }
    ):
        blockers.append("RUNTIME_DATA_IN_POLICY")
    return tuple(sorted(set(blockers)))
