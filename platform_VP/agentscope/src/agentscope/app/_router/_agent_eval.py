# -*- coding: utf-8 -*-
"""Test cases saved from conversations and the runs that replay them."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .._service import ResourceAccessService, get_model
from .._service._agent_eval import (
    MAX_CASES_PER_RUN,
    EvalCaseData,
    EvalLimitError,
    case_from_turn,
    compare_runs,
    reserve_run,
    start_suite,
)
from .._service._case_file import load_turn_messages
from ..deps import get_current_user_id, get_resource_access_service, get_storage
from ..storage import AgentArtifactRecord, AgentRecord, StorageBase

agent_eval_router = APIRouter(prefix="/agent/{agent_id}/eval", tags=["agent-eval"])


class CreateEvalCaseRequest(BaseModel):
    """A case typed by hand, or taken from a conversation turn.

    With ``message_id``, the scenario is that turn's customer message (unless
    given) and the agent's real read results become the case's data.
    """

    expected: str = Field(min_length=1, max_length=2000)
    scenario: str | None = Field(default=None, max_length=2000)
    expect_tool: str = Field(default="", max_length=200)
    session_id: str | None = None
    session_agent_id: str | None = Field(
        default=None, description="Owner of the session (the Leader in a team chat).",
    )
    message_id: str | None = None


async def _agent(storage: StorageBase, user_id: str, agent_id: str) -> AgentRecord:
    record = await storage.get_agent(user_id, agent_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy agent.")
    return record


def _view(record: AgentArtifactRecord) -> dict:
    return {"id": record.id, "created_at": record.created_at, "updated_at": record.updated_at, **record.data}


@agent_eval_router.get("/cases", summary="The agent's saved test cases")
async def list_cases(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[dict]:
    await _agent(storage, user_id, agent_id)
    return [_view(r) for r in await storage.list_agent_artifacts(user_id, agent_id, "eval_case")]


@agent_eval_router.post("/cases", status_code=status.HTTP_201_CREATED, summary="Save a test case")
async def create_case(
    agent_id: str,
    body: CreateEvalCaseRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    await _agent(storage, user_id, agent_id)
    scenario, recorded = (body.scenario or "").strip(), {}
    if body.message_id:
        if not body.session_id or not body.session_agent_id:
            raise HTTPException(status_code=422, detail="Cần session_id và session_agent_id khi lưu từ hội thoại.")
        if await storage.get_session(user_id, body.session_agent_id, body.session_id) is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
        messages = await load_turn_messages(storage, user_id, body.session_id, body.message_id)
        taken = case_from_turn(messages, body.message_id, agent_id, body.session_agent_id)
        if taken is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt hội thoại của tin nhắn này.")
        scenario = scenario or taken[0].strip()
        recorded = taken[1]
    if not scenario:
        raise HTTPException(status_code=422, detail="Ca kiểm thử cần lời khách nói.")
    data = EvalCaseData(
        scenario=scenario[:2000],
        expected=body.expected.strip(),
        expect_tool=body.expect_tool.strip(),
        recorded=recorded,
        source_session_id=body.session_id if body.message_id else None,
        source_message_id=body.message_id,
    )
    record = AgentArtifactRecord(user_id=user_id, agent_id=agent_id, kind="eval_case", data=data.model_dump())
    await storage.upsert_agent_artifact(user_id, record)
    return _view(record)


@agent_eval_router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    agent_id: str,
    case_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> None:
    record = await storage.get_agent_artifact(user_id, case_id)
    if record is None or record.agent_id != agent_id or record.kind != "eval_case":
        raise HTTPException(status_code=404, detail="Không tìm thấy ca kiểm thử.")
    await storage.delete_agent_artifact(user_id, case_id)


@agent_eval_router.post("/runs", status_code=status.HTTP_202_ACCEPTED, summary="Re-run every saved case")
async def start_run(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> dict:
    agent = await _agent(storage, user_id, agent_id)
    cases = await storage.list_agent_artifacts(user_id, agent_id, "eval_case")
    if not cases:
        raise HTTPException(status_code=409, detail="Agent chưa có ca kiểm thử nào.")
    # pylint: disable-next=import-outside-toplevel
    from ._workforce_console import _model_config

    config = await _model_config(storage, user_id)
    model = await get_model(user_id, config, access)
    try:
        reserve_run(user_id)
    except EvalLimitError as error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)) from error
    run = await start_suite(storage, user_id, agent, model, config.model, cases[-MAX_CASES_PER_RUN:])
    return _view(run)


@agent_eval_router.get("/runs", summary="The agent's runs, newest first")
async def list_runs(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[dict]:
    await _agent(storage, user_id, agent_id)
    runs = await storage.list_agent_artifacts(user_id, agent_id, "eval_run")
    return [_view(r) for r in reversed(runs[-limit:])]


@agent_eval_router.get("/runs/{run_id}", summary="One run, optionally compared with an earlier one")
async def get_run(
    agent_id: str,
    run_id: str,
    compare_to: str | None = Query(default=None, description="An earlier run of the same agent."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    run = await storage.get_agent_artifact(user_id, run_id)
    if run is None or run.agent_id != agent_id or run.kind != "eval_run":
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
    view = _view(run)
    if compare_to:
        older = await storage.get_agent_artifact(user_id, compare_to)
        if older is None or older.agent_id != agent_id or older.kind != "eval_run":
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy để so sánh.")
        view["comparison"] = {"run_id": older.id, "version": older.data.get("version"),
                              "cases": compare_runs(older.data, run.data)}
    return view
