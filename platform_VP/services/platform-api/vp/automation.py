import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select

from .config import settings
from .db import Artifact, Membership, Record, User, emit, now, transaction
from .domain import create_session, queue_agent, submit_chat
from .security import Principal


def next_cron(spec: dict, timestamp: float | None = None):
    base = datetime.fromtimestamp(timestamp or now(), ZoneInfo(spec["timezone"]))
    return croniter(spec["cron"], base).get_next(datetime).timestamp()


async def start_workflow(db, p, workflow):
    # Copy immutable workflow steps to session; later config edits don't change the run.
    spec = workflow.body
    session = await create_session(
        db, p, spec["name"], spec["agent_ids"], settings.session_budget_micros
    )
    session.board = {
        **session.board,
        "workflow": {
            "id": workflow.id,
            "version": workflow.version,
            "steps": spec["steps"],
            "human_gate": spec["human_gate"],
            "step": 0,
        },
    }
    await submit_chat(db, p, session.id, spec["steps"][0], "workflow-start")
    return session


async def advance_workflow(db, session, result):
    flow = dict(session.board["workflow"])
    if result.status != "complete":
        return
    if flow["step"] + 1 == len(flow["steps"]):
        flow["status"] = "complete"
        session.board = {**session.board, "workflow": flow}
        await emit(db, session, "workflow.completed", {"workflow_id": flow["id"]})
        return
    flow["status"] = "awaiting_gate" if flow["human_gate"] else "ready"
    session.board = {**session.board, "workflow": flow}
    if flow["human_gate"]:
        session.status = "awaiting_approval"
        await emit(db, session, "workflow.gate", {"next_step": flow["step"] + 1})
    else:
        await continue_workflow(db, session)


async def continue_workflow(db, session):
    flow = dict(session.board["workflow"])
    flow["step"] += 1
    flow["status"] = "running"
    text = flow["steps"][flow["step"]]
    session.turn += 1
    session.status = "running"
    session.board = {**session.board, "workflow": flow, "goal": text, "unknowns": []}
    db.add(
        Artifact(
            workspace=session.workspace,
            session_id=session.id,
            kind="user_message",
            turn=session.turn,
            body={"text": text, "sender": "workflow"},
        )
    )
    await emit(db, session, "workflow.step", {"step": flow["step"], "text": text})
    await queue_agent(db, session, session.team[0]["agent_id"], "plan")


async def schedule_tick():
    # One schedule/workspace per transaction, matching the session/wallet lock rule.
    async with transaction() as db:
        ids = (await db.scalars(select(Record.id).where(Record.kind == "schedules"))).all()
    for rid in ids:
        async with transaction() as db:
            schedule = await db.scalar(
                select(Record).where(Record.id == rid).with_for_update(skip_locked=True)
            )
            if not schedule:
                continue
            spec = schedule.body
            if not spec["enabled"] or spec.get("next_run", 0) > now():
                continue
            owner = await db.get(User, schedule.owner)
            member = await db.get(Membership, (schedule.workspace, schedule.owner))
            if not owner or owner.disabled or not member or member.role == "viewer":
                schedule.body = {**spec, "enabled": False, "last_error": "owner_access_revoked"}
                continue
            workflow = await db.get(Record, spec["workflow_id"])
            if not workflow or workflow.workspace != schedule.workspace:
                schedule.body = {**spec, "enabled": False, "last_error": "workflow_missing"}
                continue
            # Keep queue bounded at session admission; missed ticks coalesce after downtime.
            from fastapi import HTTPException

            try:
                async with db.begin_nested():
                    session = await start_workflow(
                        db, Principal(owner.id, schedule.workspace, member.role), workflow
                    )
                schedule.body = {
                    **spec,
                    "next_run": next_cron(spec),
                    "last_run": now(),
                    "last_session_id": session.id,
                    "last_error": "",
                }
            except HTTPException as exc:
                schedule.body = {**spec, "next_run": now() + 60, "last_error": str(exc.detail)}


async def scheduler_loop(stop: asyncio.Event):
    while not stop.is_set():
        await schedule_tick()
        try:
            await asyncio.wait_for(stop.wait(), 15)
        except TimeoutError:
            pass
