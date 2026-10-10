"""Pure checkpoint transitions; durable transactions/leases are injected."""

from copy import deepcopy

from .._models import require


def assert_binding(workflow, audience, workflow_id):
    require(workflow["workflow_id"] == workflow_id and workflow["audience"] == audience,
            "WORKFLOW_BINDING_MISMATCH")


def apply_cause(checkpoint, cause, *, fence, expected_revision):
    require(checkpoint["revision"] == expected_revision, "REVISION_CONFLICT")
    require(fence == checkpoint["fence"], "STALE_WORKER")
    updated = deepcopy(checkpoint)
    if cause["cause_id"] in updated["applied_causes"]:
        return updated
    require(updated["state"] != "closed", "WORKFLOW_CLOSED")
    require(not updated["state"].startswith("blocked"), "WORKFLOW_BLOCKED")
    kind = cause["kind"]
    require(kind in {"user_reply", "approval_result", "operation_progress", "timer"}, "CAUSE_INVALID")
    if kind in {"operation_progress", "timer"} and updated.get("pending_hitl"):
        updated["pending_causes"].append(deepcopy(cause))
        # Status can be logged, but do not wake a parked runtime with a fake reply.
        updated["invoke_runtime"] = False
    else:
        if kind == "approval_result":
            require(updated["state"] == "awaiting_approval", "APPROVAL_NOT_PENDING")
        if kind == "user_reply":
            require(updated["state"] != "awaiting_approval", "APPROVAL_REQUIRED")
        updated["state"] = "active"
        updated["invoke_runtime"] = True
    updated["applied_causes"].append(cause["cause_id"])
    updated["revision"] += 1
    return updated


def close_checkpoint(checkpoint, *, expected_revision, stop_tracking_only=False, operation_pending=False):
    require(checkpoint["revision"] == expected_revision, "REVISION_CONFLICT")
    require(not operation_pending or stop_tracking_only, "STOP_TRACKING_CONFIRMATION_REQUIRED")
    updated = deepcopy(checkpoint)
    if updated["state"] != "closed":
        updated["state"] = "closed"
        updated["next_action"] = "none"
        updated["invoke_runtime"] = False
        updated["revision"] += 1
    return updated
