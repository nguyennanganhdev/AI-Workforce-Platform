"""Deterministic consumer evals; synthetic labels do not measure LLM/NLP quality."""

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "graph"))
from workflow_fixture import (
    INFORMATION,
    REQUEST,
    Intake,
    async_test,
    event_fixture,
    harness,
    resident_resume,
    set_event,
    turn,
    waiting,
)

DATASET = json.loads(
    Path(__file__).with_name("reception.vi.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("sample", DATASET, ids=[s["id"] for s in DATASET])
@async_test
async def test_vietnamese_reception_eval(sample):
    scenario = sample["scenario"]
    if scenario == "knowledge":
        policy = {
            "kind": "knowledge_chat",
            "policyVersion": "eval-policy-1",
            "question": "Bạn hỏi tiện ích nào?",
        }
    elif scenario == "emergency":
        policy = {
            "kind": "emergency",
            "policyVersion": "eval-policy-1",
            "reason": "synthetic-rule",
        }
    else:
        policy = {
            "kind": "needs_staff",
            "policyVersion": "eval-policy-1",
            "reason": "synthetic-rule",
            "handoffReason": scenario
            if scenario.startswith("self_help")
            else "needs_staff",
        }
    intake = Intake(
        policy,
        {
            "kind": "sufficient",
            "answer": "Theo nội quy mẫu, mở lúc 8 giờ.",
            "retrievalRunId": "eval-retrieval",
            "citations": [
                {"documentId": "eval-document", "version": "1", "chunkId": "eval-chunk"}
            ],
        },
    )

    def override(call, value):
        if call["operation"] == "get_verified_resident_context" and scenario in (
            "missing_profile",
            "multiple_units",
        ):
            return {
                "kind": "success",
                "value": {
                    "kind": "selection_required"
                    if scenario == "multiple_units"
                    else "missing",
                    "questions": ["Bạn chọn căn hộ đã xác minh nào?"],
                },
            }
        if call["operation"] == "update_ticket_incident" and scenario in (
            "missing_photo",
            "emergency",
        ):
            return {
                "kind": "success",
                "value": {**value, "missing_fields": ["file_ids"]},
            }
        if call["operation"] == "submit_ticket_assessment" and scenario == "emergency":
            value["triage"].update(
                is_emergency=True, priority="critical", severity="critical"
            )
            return {"kind": "success", "value": value}

    h = harness(
        model=[turn("information", workspace_id="forged")]
        if scenario == "prompt_injection"
        else [INFORMATION, turn("cancel" if scenario == "cancel" else "new_incident")],
        override=override,
        intake=intake,
    )
    request = deepcopy(REQUEST)
    request["message"]["text"] = sample["text"]
    if scenario in ("missing_photo", "emergency"):
        request["message"]["fileIds"] = []
    result = await h.graph.run(request)
    if "expected_calls" in sample:
        assert [c["operation"] for c in h.calls] == sample["expected_calls"]
    if scenario in ("new_incident", "cancel"):
        before = len(h.calls)
        result = await h.graph.resume(
            resident_resume(result, {"id": "eval-followup", "text": sample["text"]})
        )
        followup = [
            c["operation"]
            for c in h.calls[before:]
            if c["operation"] != "register_supervisor_wait"
        ]
        assert followup == (
            [sample["expected_followup_call"]]
            if sample["expected_followup_call"]
            else []
        )
    if scenario in ("duplicate_event", "stale_event"):
        event, resume = event_fixture(result)
        set_event(h, event)
        current = waiting(await h.graph.resume(resume))
        bad, req = event_fixture(
            current,
            event_id=event["event_id"]
            if scenario == "duplicate_event"
            else "stale-eval-event",
        )
        bad["aggregate_version"] = event["aggregate_version"]
        req["source"]["event"]["aggregateVersion"] = event["aggregate_version"]
        set_event(h, bad)
        result = await h.graph.resume(req)
    if "expected_error" in sample:
        assert result["status"] == "failed"
        assert result["code"] == sample["expected_error"]
    else:
        assert result["status"] in ("completed", "interrupted"), result
        assert result["state"]["phase"] == sample["expected_phase"]
        if scenario.startswith("self_help"):
            assert result["state"]["handoff_reason"] == scenario
    state = await h.graph.read(REQUEST["context"])
    assert bool(state.get("active_ticket_id")) == sample["expected_ticket"]
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) <= 1
