from typing import Any, Dict

from ...contracts import (
    AsyncProtocolSnapshotRef,
    EvaluationCaseResult,
    EvaluationReport,
    EvaluationSnapshot,
)
from .._models import EvaluationRecord, ValidationReport


def phase_a_schema_bundle() -> Dict[str, Any]:
    """Return isolated schema documents for Foundation's additive integration.

    Policy is a design proposal only; Builder/Foundation own its shared DTO.
    Snapshot/report schemas come directly from the baseline shared models.
    """
    models = (
        ValidationReport,
        EvaluationSnapshot,
        EvaluationCaseResult,
        EvaluationReport,
        EvaluationRecord,
        AsyncProtocolSnapshotRef,
    )
    schemas = {model.__name__: model.model_json_schema() for model in models}
    names = ("capabilities", "event_types", "required_facts")
    properties: Dict[str, Any] = {
        "schema_version": {"const": "1", "type": "string"},
        "completion_condition": {"type": "string", "minLength": 1},
        "human_confirmation": {"type": "boolean"},
        "timeout_behavior": {
            "type": "string",
            "enum": ["status_query", "needs_attention"],
        },
    }
    for name in names:
        properties[name] = {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        }
    schemas["AsyncHandlingPolicyProposal"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AsyncHandlingPolicyProposal",
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }
    return {"schema_version": "pta-phase-a-1", "schemas": schemas}
