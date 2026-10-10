# -*- coding: utf-8 -*-
"""Review-only schema export. No registration with application composition."""

from ..contracts import (
    AsyncProtocolSnapshotRef,
    CloseWorkflowCommand,
    ConversationEvent,
    EventHistoryPage,
    InboundReceipt,
    PartnerRequestEnvelope,
    RequestResult,
    TicketConversationBinding,
    WorkflowRecord,
)
from .partner_events.phase_a import PUBLIC_PAYLOAD_MODELS
from .workflows.phase_a import (
    CommandClaimResult,
    PinnedRuntimeContext,
    RuntimeTurnResult,
    WorkflowCheckpoint,
    WorkflowTrigger,
)

PHASE_A_SCHEMA_VERSION = "phh-phase-a-1"
SHARED_MODELS = (
    WorkflowRecord,
    TicketConversationBinding,
    ConversationEvent,
    EventHistoryPage,
    InboundReceipt,
    PartnerRequestEnvelope,
    CloseWorkflowCommand,
    RequestResult,
    AsyncProtocolSnapshotRef,
)
PROPOSED_MODELS = (
    WorkflowTrigger,
    WorkflowCheckpoint,
    CommandClaimResult,
    PinnedRuntimeContext,
    RuntimeTurnResult,
)


def phase_a_schema_bundle() -> dict[str, object]:
    """Structural schemas; cross-field rules also need model validation."""
    return {
        "schema_version": PHASE_A_SCHEMA_VERSION,
        "status": "proposal_pending_owner_acceptance",
        "shared_models": [model.__name__ for model in SHARED_MODELS],
        "schemas": {
            model.__name__: model.model_json_schema()
            for model in (*SHARED_MODELS, *PROPOSED_MODELS)
        },
        "public_payloads": {
            name: model.model_json_schema()
            for name, model in PUBLIC_PAYLOAD_MODELS.items()
        },
    }
