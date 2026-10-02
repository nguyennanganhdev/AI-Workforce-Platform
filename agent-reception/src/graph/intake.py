"""Deterministic knowledge/policy intake; no mutation port or production mocks."""

from __future__ import annotations

from .budget import CancellationToken
from .decision import GraphFault
from .workflow_contracts import IntakePort


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_policy(value) -> bool:
    if not isinstance(value, dict) or not _nonempty(value.get("policyVersion")):
        return False
    kind = value.get("kind")
    if kind in ("emergency", "needs_staff"):
        return _nonempty(value.get("reason")) and value.get(
            "handoffReason", "needs_staff"
        ) in ("needs_staff", "self_help_declined", "self_help_failed")
    return kind in ("knowledge_chat", "clarify") and _nonempty(value.get("question"))


def valid_knowledge(value) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("kind") == "insufficient":
        return True
    return (
        value.get("kind") == "sufficient"
        and _nonempty(value.get("answer"))
        and _nonempty(value.get("retrievalRunId"))
        and isinstance(value.get("citations"), list)
        and bool(value["citations"])
        and all(
            isinstance(citation, dict)
            and all(
                _nonempty(citation.get(key))
                for key in ("documentId", "version", "chunkId")
            )
            for citation in value["citations"]
        )
    )


async def run_intake(ports: IntakePort, request: dict) -> dict:
    signal: CancellationToken | None = request.get("signal")
    if signal:
        signal.throw_if_aborted()
    review = {
        "kind": "review",
        "reply": "Chưa xác minh được chính sách hỗ trợ; yêu cầu cần người có thẩm quyền xem xét.",
        "emergency": False,
        "citations": [],
    }
    try:
        policy = await ports.evaluate_policy(request)
        if signal:
            signal.throw_if_aborted()
        if not valid_policy(policy):
            return review
        base = {
            "policyVersion": policy["policyVersion"],
            "emergency": policy["kind"] == "emergency",
            "citations": [],
        }
        if policy["kind"] in ("emergency", "needs_staff"):
            return {
                **base,
                "kind": "needs_staff",
                "handoffReason": "emergency"
                if base["emergency"]
                else policy.get("handoffReason", "needs_staff"),
                "reply": "Yêu cầu cần nhân viên chuyên môn xử lý; chưa có xác nhận phân công.",
            }
        knowledge = await ports.search_knowledge(request)
        if signal:
            signal.throw_if_aborted()
        if not valid_knowledge(knowledge):
            raise GraphFault("INVALID_KNOWLEDGE")
        if knowledge["kind"] == "sufficient":
            return {
                **base,
                "kind": "answer",
                "reply": knowledge["answer"],
                "retrievalRunId": knowledge["retrievalRunId"],
                "citations": [
                    {key: citation[key] for key in ("documentId", "version", "chunkId")}
                    for citation in knowledge["citations"]
                ],
            }
        return {**base, "kind": "clarify", "reply": policy["question"]}
    except Exception:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
        if signal:
            signal.throw_if_aborted()
        return review
