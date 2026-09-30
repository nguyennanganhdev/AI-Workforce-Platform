"""Adapter that maps DispatcherDecision → GroupChat OpenRoom command.

This is the integration boundary between DEV-1 (Dispatcher) and DEV-4
(agent-coordination GroupChat).  It translates the Dispatcher's TypedDict
output into Pydantic models expected by the GroupChat engine.

Role mapping convention (P3):
  Dispatcher roles (COORDINATOR, SPECIALIST, REVIEWER) are mapped directly.
  GroupChat accepts any string as role, so they pass through unchanged.

Context assembly (P4):
  GroupChat requires a full Context (tenant_id, domain_id, workspace_id, etc).
  These fields come from the original TicketReport, NOT from DispatcherDecision
  alone.  This adapter accepts both and merges them.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from dispatcher.contracts import (
    DispatcherDecision,
    GroupChatContext,
    TicketReport,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role mapping: Dispatcher role → GroupChat-compatible role
# ---------------------------------------------------------------------------

# GroupChat models.py accepts any string as role (Id = str, min 1 char).
# We keep uppercase Dispatcher roles as the canonical format and lowercase
# them for GroupChat convention compatibility.
ROLE_MAP: dict[str, str] = {
    "COORDINATOR": "coordinator",
    "SPECIALIST": "specialist",
    "REVIEWER": "reviewer",
}


def map_role(dispatcher_role: str) -> str:
    """Convert Dispatcher ParticipantRole to GroupChat role string."""
    return ROLE_MAP.get(dispatcher_role, dispatcher_role.lower())


# ---------------------------------------------------------------------------
# Context assembly from TicketReport
# ---------------------------------------------------------------------------

def build_groupchat_context(
    ticket: TicketReport,
    decision: DispatcherDecision,
) -> GroupChatContext:
    """Assemble the full GroupChat Context from TicketReport + Decision.

    GroupChat Context requires:
      tenant_id, principal_id, domain_id, workspace_id,
      ticket_id, ticket_generation, binding_id, run_id

    TicketReport provides tenant_id, ticket_id, and subject (namespace/id).
    Decision provides decision_id and correlation_id.
    Missing fields are derived or generated at the integration boundary.
    """
    subject = ticket.get("subject", {})

    return GroupChatContext(
        tenant_id=ticket["tenant_id"],
        principal_id=ticket.get("correlation_id", str(uuid.uuid4())),
        domain_id=subject.get("namespace", "vinhomes"),
        workspace_id=subject.get("subject_id", ticket["tenant_id"]),
        ticket_id=ticket["ticket_id"],
        ticket_generation=0,  # First generation; incremented on re-triage
        binding_id=decision["decision_id"],
        run_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Main adapter: DispatcherDecision → OpenRoom-compatible dict
# ---------------------------------------------------------------------------

def to_open_room_payload(
    ticket: TicketReport,
    decision: DispatcherDecision,
    groupchat_version_id: str = "v2",
) -> dict[str, Any]:
    """Convert a DispatcherDecision into a GroupChat OpenRoom command payload.

    The returned dict matches the shape of
    agent-coordination/src/groupchat/models.OpenRoom and can be validated
    directly via ``OpenRoom(**payload)``.

    Args:
        ticket: The original TicketReport from DEV-3.
        decision: The DispatcherDecision produced by build_decision().
        groupchat_version_id: GroupChat schema version.

    Returns:
        A dict that can be passed to GroupChat OpenRoom model.
    """
    classification = decision["classification"]
    sla = decision["sla"]
    turn_policy = decision["turn_policy"]

    # Build participants list with mapped roles
    participants = [
        {
            "agent_version_id": agent["agent_version_id"],
            "role": map_role(agent["role"]),
        }
        for agent in decision["selected_agents"]
    ]

    # Build turn policy for GroupChat (subset of Dispatcher's full policy)
    gc_turn_policy = {
        "max_turns": turn_policy["max_turns"],
        "max_consecutive_turns": turn_policy["max_consecutive_turns"],
        "timeout_seconds": turn_policy["timeout_seconds"],
    }

    # Build initial message with classification context
    severity_label = classification["severity"]
    category_label = classification["category"]
    sla_response = sla["response_minutes"]
    sla_resolution = sla["resolution_minutes"]

    initial_content = (
        f"Phân tích ticket {decision['ticket_id']} "
        f"(Danh mục: {category_label}, Mức độ: {severity_label}) "
        f"và đề xuất phương án xử lý.\n"
        f"Cam kết SLA: phản hồi trong {sla_response} phút, "
        f"giải quyết trong {sla_resolution} phút."
    )

    # Add ML signals if available
    signals = decision.get("prediction_signals")
    if signals and signals.get("sla_breach_risk") is not None:
        breach_pct = signals["sla_breach_risk"] * 100
        initial_content += f"\n⚠️ Rủi ro vi phạm SLA: {breach_pct:.0f}%"
    if signals and signals.get("predicted_resolution_hours") is not None:
        hours = signals["predicted_resolution_hours"]
        initial_content += f"\n📊 Thời gian xử lý dự kiến: {hours:.1f} giờ"

    initial_message = {
        "content": initial_content,
        "delivery": "broadcast",
    }

    # Assemble GroupChat Context
    gc_context = build_groupchat_context(ticket, decision)

    payload = {
        "version": 2,
        "operation": "open_room",
        "room_id": None,
        "groupchat_version_id": groupchat_version_id,
        "participants": participants,
        "turn_policy": gc_turn_policy,
        "initial_message": initial_message,
    }

    logger.info(
        "Mapped DispatcherDecision → OpenRoom: ticket=%s, agents=%d, max_turns=%d",
        decision["ticket_id"],
        len(participants),
        gc_turn_policy["max_turns"],
    )

    return {
        "context": gc_context,
        "payload": payload,
    }
