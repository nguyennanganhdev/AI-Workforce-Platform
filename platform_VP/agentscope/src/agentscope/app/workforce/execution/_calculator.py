# -*- coding: utf-8 -*-
"""Deterministic integer money calculator; no Python or shell evaluation."""

from typing import Any

from ._utils import ExecutionError, digest

INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["currency", "budget_minor", "reserve_minor", "items"],
    "properties": {
        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "budget_minor": {"type": "integer", "minimum": 0, "maximum": 10**18},
        "reserve_minor": {"type": "integer", "minimum": 0, "maximum": 10**18},
        "items": {
            "type": "array",
            "maxItems": 1000,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "label",
                    "amount_minor",
                    "quantity",
                    "fees_minor",
                ],
                "properties": {
                    "label": {"type": "string", "maxLength": 200},
                    "amount_minor": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10**18,
                    },
                    "fees_minor": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10**18,
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                    },
                },
            },
        },
    },
}


def calculator_descriptor(scope: Any) -> Any:
    """
    Return a descriptor for Registry to register explicitly in this scope.
    """
    return {
        "tool_id": "builtin.money",
        "tool_version_id": "builtin.money.v1",
        "source_kind": "builtin",
        "provider_tool_name": "money",
        "llm_alias": "workforce_money",
        "description": "Total verified prices and fees in minor units.",
        "input_schema": INPUT_SCHEMA,
        "schema_hash": digest(INPUT_SCHEMA),
        "capabilities": ["calculate_money"],
        "effect": "read",
        "effect_reviewed": True,
        "available": True,
        "scope": scope,
    }


def calculate(arguments: Any) -> Any:
    """Fees are per line; quantity applies to unit amount only."""
    from jsonschema import Draft202012Validator

    if list(Draft202012Validator(INPUT_SCHEMA).iter_errors(arguments)):
        raise ExecutionError("TOOL_INPUT_INVALID", 422)
    total = sum(
        i["amount_minor"] * i["quantity"] + i["fees_minor"]
        for i in arguments["items"]
    )
    reserve = arguments["reserve_minor"]
    remaining = arguments["budget_minor"] - total - reserve
    return {
        "currency": arguments["currency"],
        "total_minor": total,
        "reserve_minor": reserve,
        "remaining_minor": remaining,
        "within_budget": remaining >= 0,
    }
