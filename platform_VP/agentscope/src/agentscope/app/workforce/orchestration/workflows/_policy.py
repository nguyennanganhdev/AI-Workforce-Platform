"""Domain-neutral lifecycle, driven by validated tool output and published policy."""

from .._models import require


def continuation(*, policy, outcome, http_pending=False):
    """Called with verified metadata, never parsed from an agent's prose."""
    require(policy.get("effect") in {"read_only", "side_effect"}, "POLICY_EFFECT_INVALID")
    if outcome.get("needs_attention") or outcome.get("creation_status") == "unknown":
        return "needs_attention", "resolve_attention"
    if outcome.get("needs_user"):
        return "awaiting_user", "submit_reply"
    if outcome.get("needs_approval"):
        return "awaiting_approval", "submit_approval"
    if outcome.get("operation_pending"):
        require(bool(policy.get("tracking_protocol")), "TRACKING_CAPABILITY_MISSING")
        return "waiting_external_event", "watch_events"
    if not outcome.get("terminal"):
        require(http_pending, "TURN_OUTCOME_INCOMPLETE")
        return "active", "watch_request"
    if policy["effect"] == "read_only" and policy.get("auto_close"):
        return "closed", "none"
    return "awaiting_confirmation", "confirm_close"


def post_status(request_status):
    require(request_status in {"accepted", "queued", "running", "completed", "failed", "blocked"}, "REQUEST_STATUS_INVALID")
    return 202 if request_status in {"accepted", "queued", "running"} else 200
