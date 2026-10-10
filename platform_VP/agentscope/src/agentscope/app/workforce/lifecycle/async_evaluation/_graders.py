"""Assert continuation, parked turns, side effects and audience isolation."""

from typing import Any, Mapping, Tuple


def grade_turns(
    case: Mapping[str, Any], evidence: Mapping[str, Any]
) -> Tuple[str, ...]:
    failures = []
    actual = evidence.get("turns")
    expected = case["turns"]
    if not isinstance(actual, list) or len(actual) != len(expected):
        return ("TURN_COVERAGE_MISMATCH",)
    for golden, turn in zip(expected, actual):
        if not isinstance(turn, dict):
            failures.append("INVALID_TURN_EVIDENCE")
            continue
        for key in ("workflow_state", "next_action", "operation_pending"):
            if turn.get(key) != golden[key]:
                failures.append(f"INVALID_{key.upper()}")
        if turn.get("audience_verified") is not True:
            failures.append("cross_audience")
        if turn.get("trigger") != golden["trigger"]:
            failures.append("TRIGGER_MISMATCH")
        if golden["trigger"] in ("none", "duplicate", "out_of_order"):
            if (
                turn.get("llm_calls") != 0
                or turn.get("side_effect_calls") != 0
            ):
                failures.append("UNTRIGGERED_EXECUTION")
        if not golden["operation_pending"]:
            if turn.get("tracking_created") is not False:
                failures.append("SYNC_TRACKING_CREATED")
    if "max_create_calls" in case:
        creates = evidence.get("create_calls")
        if (
            type(creates) is not int
            or not 0 <= creates <= case["max_create_calls"]
        ):
            failures.append("duplicate_side_effect")
    if case.get("assert_ticket_isolation"):
        if evidence.get("ticket_isolation_verified") is not True:
            failures.append("TICKET_CONTEXT_MIXED")
    return tuple(sorted(set(failures)))
