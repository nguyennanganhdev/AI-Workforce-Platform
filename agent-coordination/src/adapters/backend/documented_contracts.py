"""Documented V2 boundary and adapter-local routing/ACK guards.

Source: docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md, V2. Internal wrappers are not extra
Reception schemas. Publishing shared JSON Schema belongs to DEV-5/Team Chien.
Supplied pins augment guards; business rights/dedup still need trusted services.
"""
from __future__ import annotations

import json
from typing import Mapping

from .client import ERROR_CODES
from .messages import require, snapshot, text, validate_event, validate_request
from .reception_messages import validate_input, validate_output, validate_scope


def validate_receipt(wire: dict, identity: str) -> None:
    require(text(wire.get(identity)))
    if wire.get("status") == "error":
        require(set(wire) == {identity, "status", "error"})
        error = wire["error"]
        require(isinstance(error, dict) and set(error) == {"code", "retryable"})
        require(error["code"] in ERROR_CODES and type(error["retryable"]) is bool)
    else:
        require(set(wire) == {identity, "status", "data"})
        require(wire["status"] in {"accepted", "completed"} and isinstance(wire["data"], dict))


class DocumentedContractValidator:
    supported_kinds = frozenset({
        "reception_input", "reception_output", "reception_delivery", "reception_response",
        "reception_verified", "request", "response", "event",
    })

    def validate(self, kind: str, value: Mapping) -> None:
        wire = snapshot(value)
        require(kind in self.supported_kinds)
        if kind == "reception_input":
            validate_input(wire)
        elif kind == "reception_output":
            validate_output(wire)
        elif kind == "reception_delivery":
            require(set(wire) == {"message", "context"})
            validate_output(wire["message"])
            validate_scope(wire["message"], wire["context"])
        elif kind == "reception_verified":
            require({"message", "context", "supervisor_run_id"} <= set(wire)
                    <= {"message", "context", "supervisor_run_id", "room_command"})
            validate_input(wire["message"])
            validate_scope(wire["message"], wire["context"])
            require(text(wire["supervisor_run_id"]))
            if wire.get("room_command") is not None:
                from groupchat.models import Command
                command = Command.model_validate_json(json.dumps(wire["room_command"]), strict=True)
                require(command.payload.operation == "mention_agent"
                        and command.context.model_dump(mode="json", exclude_none=True) == wire["context"]
                        and wire["message"]["message_type"] == "information_provided"
                        and command.payload.instruction == wire["message"]["message"])
        elif kind in {"response", "reception_response"}:
            validate_receipt(wire, "request_id" if kind == "response" else "message_id")
        elif kind == "request":
            validate_request(wire)
        else:
            validate_event(wire)


class AugmentedContractValidator:
    """Keep documented guards and additionally apply explicitly supplied pins."""
    def __init__(self, base: DocumentedContractValidator, additional):
        self._base, self._additional = base, additional
        self.supported_kinds = base.supported_kinds | additional.supported_kinds

    def validate(self, kind: str, value: Mapping) -> None:
        require(kind in self.supported_kinds)
        if kind in self._base.supported_kinds:
            self._base.validate(kind, value)
        if kind in self._additional.supported_kinds:
            self._additional.validate(kind, value)
