# -*- coding: utf-8 -*-
"""JSON Schema export for versioned Workforce boundary contracts."""

from pydantic import BaseModel

from ._batch import AgentBuildBatch
from ._catalog import McpConnection, PartnerMcpDefinition, ToolDescriptor
from ._conversation import (
    CloseWorkflowCommand,
    ConversationSnapshot,
    InboundReceipt,
    PartnerRequestEnvelope,
    TicketConversationBinding,
)
from ._errors import ErrorResponse
from ._evaluation import EvaluationReport, EvaluationSnapshot
from ._events import ConversationEvent, EventHistoryPage
from ._execution import (
    PartnerApprovalDecision,
    ProviderEventEnvelope,
    ProviderEventReceipt,
)
from ._identity import ActorContext, PartnerAudience, Scope
from ._manifest import AgentManifest
from ._partner_routing import (
    ResidenceSync,
    ResidenceSyncResult,
    RouteConfirmation,
    RouteConfirmationResult,
)
from ._reuse import ReuseCheck, ReuseDecision


CONTRACT_SCHEMA_VERSION = "1"

SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    Scope,
    ActorContext,
    PartnerAudience,
    RouteConfirmation,
    RouteConfirmationResult,
    ResidenceSync,
    ResidenceSyncResult,
    PartnerMcpDefinition,
    McpConnection,
    ToolDescriptor,
    AgentManifest,
    AgentBuildBatch,
    ReuseCheck,
    ReuseDecision,
    EvaluationSnapshot,
    EvaluationReport,
    PartnerRequestEnvelope,
    InboundReceipt,
    CloseWorkflowCommand,
    ConversationSnapshot,
    TicketConversationBinding,
    ConversationEvent,
    EventHistoryPage,
    PartnerApprovalDecision,
    ProviderEventEnvelope,
    ProviderEventReceipt,
    ErrorResponse,
)


def contract_schema_bundle() -> dict[str, object]:
    """Return deterministic named schemas for docs and client generation."""
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "models": {
            model.__name__: model.model_json_schema(mode="serialization")
            for model in SCHEMA_MODELS
        },
    }
