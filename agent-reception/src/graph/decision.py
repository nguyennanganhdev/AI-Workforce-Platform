"""Validation of model decisions; never an authority or backend DTO."""

from __future__ import annotations

import json
import math
from typing import Any


class GraphFault(Exception):
    def __init__(self, code: str, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def json_value(value: Any) -> Any:
    if value is None or type(value) in (str, bool):
        return value
    if type(value) in (int, float) and math.isfinite(value):
        return value
    if type(value) is list:
        return [json_value(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: json_value(item) for key, item in value.items()}
    raise GraphFault("INVALID_JSON_VALUE")


def compact_json(value: Any) -> str:
    return json.dumps(json_value(value), ensure_ascii=False, separators=(",", ":"))


def facts(value: Any) -> list[dict]:
    if not isinstance(value, list) or len(value) > 32:
        raise GraphFault("INVALID_FACTS")
    result = []
    for item in value:
        if (
            not isinstance(item, dict)
            or "value" not in item
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
            or len(item["name"]) > 128
        ):
            raise GraphFault("INVALID_FACTS")
        result.append({"name": item["name"], "value": json_value(item.get("value"))})
    return result


def parse_decision(content: Any) -> dict:
    if not isinstance(content, str) or len(content) > 32768:
        raise GraphFault("INVALID_DECISION")
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        raise GraphFault("INVALID_DECISION") from None
    if not isinstance(value, dict):
        raise GraphFault("INVALID_DECISION")
    action = value.get("action")
    allowed = (
        {"action", "operation", "input", "inferences"}
        if action == "tool"
        else {"action", "text", "inferences"}
    )
    if set(value) - allowed:
        raise GraphFault("INVALID_DECISION")
    inference = facts(value.get("inferences", []))
    if action == "tool":
        if (
            not isinstance(value.get("operation"), str)
            or not value["operation"].strip()
            or "input" not in value
        ):
            raise GraphFault("INVALID_DECISION")
        return {
            "action": action,
            "operation": value["operation"],
            "input": json_value(value["input"]),
            "inferences": inference,
        }
    if (
        action not in ("clarify", "await_resident", "handoff", "complete")
        or not isinstance(value.get("text"), str)
        or not value["text"].strip()
        or len(value["text"]) > 4096
    ):
        raise GraphFault("INVALID_DECISION")
    return {"action": action, "text": value["text"], "inferences": inference}
