"""Reproducible session acceptance cases and optional synthetic-only Jev shadow runs."""

import asyncio
import dataclasses
import json
import re

from sqlalchemy import select

from .config import settings
from .db import Artifact, Record, emit, transaction
from .limits import reconcile, reserve
from .queue import fence_for_execution as fence


def score_case(case: dict, result: dict):
    checks = {
        "status": result.get("status") == case["expected_status"],
        "contains": all(
            text.casefold() in result.get("answer", "").casefold()
            for text in case.get("must_contain", [])
        ),
        "excludes": all(
            text.casefold() not in result.get("answer", "").casefold()
            for text in case.get("must_not_contain", [])
        ),
        "sources": not case.get("require_sources", False)
        or bool(result.get("claims"))
        and not result.get("validation_faults"),
    }
    return {"passed": all(checks.values()), "checks": checks}


async def record_evaluation(db, session, result: dict):
    evaluation = session.board.get("evaluation")
    if not evaluation:
        return
    run = await db.scalar(
        select(Record)
        .where(Record.id == evaluation["run_id"])
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    case = run.body["cases"][evaluation["case"]]
    results = dict(run.body.get("results", {}))
    results[str(evaluation["case"])] = {"session_id": session.id, **score_case(case, result)}
    complete = len(results) == len(run.body["cases"])
    run.body = {
        **run.body,
        "results": results,
        "status": "complete" if complete else "running",
        "passed": complete and all(r["passed"] for r in results.values()),
    }


def baseline(state: dict):
    if state.get("missing_fields"):
        return "clarify"
    if not state.get("evidence_available"):
        return "tool"
    return "answer"


async def execute_shadow(job):
    from agentscope.classifier import ChoiceQuestion, JevClassifierModel
    from agentscope.credential import TypeSafeCredential

    from .runtime import SafeRuntimeError

    if not settings.jev_enabled or not settings.jev_api_key.get_secret_value():
        raise SafeRuntimeError("jev_disabled_or_missing_key")
    if not re.fullmatch(r"jev-\d+\.\d+\.\d+", settings.jev_model):
        raise SafeRuntimeError("jev_version_not_pinned")
    state = job.body["synthetic_state"]
    question = ChoiceQuestion(
        instructions="Choose the next action. Missing user fields need clarify; "
        "missing evidence needs a tool; answer only when sufficient evidence exists.",
        criteria={
            "tool": "Need evidence from an authorized tool",
            "clarify": "Need user clarification",
            "answer": "Enough evidence to draft",
        },
    )
    bound = len(json.dumps(state).encode()) + len(json.dumps(question.model_dump()).encode()) + 2000
    price = {
        "id": "jev-shadow",
        "context_tokens": bound,
        "max_output_tokens": 0,
        "input_micros_per_million": 42000,
        "output_micros_per_million": 0,
        "pricing_version": "typesafe-2026-10-09",
        "rpm": 60,
        "tpm": 1000000,
    }
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        reservation_id = (await reserve(db, session, current, price)).id
    usage = None
    model = JevClassifierModel(
        credential=TypeSafeCredential(api_key=settings.jev_api_key.get_secret_value()),
        model=settings.jev_model,
        timeout=15,
        max_retries=0,
    )
    try:
        async with asyncio.timeout(20):
            response = await model(state=state, questions={"route": question})
        usage = dataclasses.asdict(response.usage) if response.usage else None
        decision = dataclasses.asdict(response.content["route"])
        async with transaction() as db:
            session, current = await fence(db, job.id, job.generation)
            body = {
                "model": response.model,
                "decision": decision,
                "baseline": baseline(state),
                "expected": job.body.get("expected"),
                "shadow_only": True,
                "threshold_calibrated": False,
                "changes_runtime": False,
            }
            db.add(
                Artifact(
                    workspace=session.workspace,
                    session_id=session.id,
                    kind="jev_shadow",
                    turn=session.turn,
                    body=body,
                )
            )
            await emit(db, session, "jev.shadow", body)
            current.status = "done"
            session.status = "idle"
    finally:
        await model.client.aclose()
        async with transaction() as db:
            await reconcile(db, reservation_id, price, usage)
