"""Agent Studio API: manage business agents through forms, not only chat.

Every write goes through the Agent Spec draft. Publishing requires a test
run of that exact draft (hash-bound) that passes, then renders the prompt,
applies tool/knowledge bindings and records an immutable version.
"""

import asyncio
import os
from collections import defaultdict
from datetime import datetime
from typing import Literal

from .._service._catalog_resources import resolve_catalog_resource

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..._utils._common import _generate_id
from ...model import ChatModelBase
from .._agent_memory import AgentMemoryService
from .._agent_spec import AgentSpec, diff_specs, render_prompt, spec_hash
from .._agent_templates import TEMPLATES, template_list
from .._service import ResourceAccessService, get_model
from .._service._model import apply_reasoning_effort
from .._service._agent_eval import run_spec_tests
from .._service._agent_studio import (
    CompositionPlan,
    CopilotReply,
    apply_bindings,
    copilot_turn,
    draft_spec,
    ensure_spec,
    knowledge_catalog,
    last_test_for,
    materialize,
    plan_composition,
    published_spec,
    record_test_run,
    runtime_prompt,
    set_draft,
    skill_catalog,
    tool_catalog,
    tool_runner,
)
from .._service._eval_sandbox import eval_sandbox
from .._service._publish_gate import MIN_TESTS_TO_PUBLISH, publish_blocker
from ..deps import (
    get_current_user_id,
    get_resource_access_service,
    get_session_service,
    get_shared_context_storage,
    get_skill_hubs,
    get_storage,
    get_workspace_manager,
    get_workspace_service,
)
from ..storage import AgentData, AgentRecord, InviteConfig, SessionConfig, StorageBase
from ..storage._base import AgentRevisionConflict
from ..workspace_manager import WorkspaceManagerBase
from ._workforce_console import _FIXED_CONTEXT, _FIXED_REACT, _model_config

workforce_studio_router = APIRouter(
    prefix="/workforce/console/studio",
    tags=["workforce-studio"],
)

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


# ---------------------------------------------------------------- views


class VersionView(BaseModel):
    version: int
    author: str
    note: str = ""
    created_at: str = ""
    evaluation: dict | None = None


class AgentSummaryView(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    lifecycle_state: str
    published_version: int = 0
    has_draft: bool = False
    tool_count: int = 0
    rule_count: int = 0
    learned_rule_count: int = 0
    test_count: int = 0
    last_test: dict | None = None


class AgentDetailView(BaseModel):
    agent_id: str
    lifecycle_state: str
    published_version: int
    published: AgentSpec | None = None
    draft: AgentSpec
    draft_meta: dict = Field(default_factory=dict)
    changes: list[dict] = Field(default_factory=list)
    rendered_prompt: str = ""
    versions: list[VersionView] = Field(default_factory=list)
    last_test: dict | None = None
    can_publish: bool = False
    publish_blocker: str = ""


class CreateAgentRequest(BaseModel):
    spec: AgentSpec | None = None
    template_id: str | None = None
    clone_from: str | None = None


class ComposeRequest(BaseModel):
    description: str = Field(min_length=3, max_length=8000)
    template_id: str | None = None
    allow_team: bool = False
    """Let the Builder split the description into a team of agents."""
    run_tests: bool = False
    """Run each new agent's tests right away (real model)."""


class DraftRequest(BaseModel):
    spec: AgentSpec
    note: str = ""


class CopilotRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class CopilotView(BaseModel):
    reply: CopilotReply
    changes: list[dict]
    agent: AgentDetailView


class ComposeView(CopilotView):
    plan: CompositionPlan | None = None
    agents: list[AgentDetailView] = []
    """Every agent created (the first is ``agent``)."""
    test_reports: dict[str, dict] = {}


class PublishRequest(BaseModel):
    note: str = ""


class RollbackRequest(BaseModel):
    version: int = Field(ge=1)
    note: str = ""


# ---------------------------------------------------------------- helpers


def _summary(record: AgentRecord) -> AgentSummaryView:
    spec = draft_spec(record)
    return AgentSummaryView(
        agent_id=record.id,
        name=spec.name,
        description=spec.description,
        lifecycle_state=record.data.lifecycle_state,
        published_version=record.data.published_version,
        has_draft=record.data.draft_spec is not None,
        tool_count=len(spec.tools),
        rule_count=len([r for r in spec.rules if r.source != "agent"]),
        learned_rule_count=len([r for r in spec.rules if r.source == "agent"]),
        test_count=len(spec.tests),
        last_test=(record.data.draft_meta or {}).get("last_test")
        and {
            k: record.data.draft_meta["last_test"].get(k)
            for k in ("pass_rate", "passed", "total", "ran_at", "publishable", "errors", "model_error")
        },
    )


def _publish_blocker(record: AgentRecord, spec: AgentSpec) -> str:
    if record.data.draft_spec is None:
        if record.data.lifecycle_state == "withdrawn" and record.data.published_version:
            return publish_blocker(spec, record.data.evaluation)
        if record.data.lifecycle_state == "published":
            return "Không có thay đổi nào cần phát hành."
    return publish_blocker(spec, last_test_for(record, spec))


def _detail(record: AgentRecord) -> AgentDetailView:
    published = AgentSpec.model_validate(record.data.spec) if record.data.spec and record.data.published_version else None
    draft = draft_spec(record)
    blocker = _publish_blocker(record, draft)
    return AgentDetailView(
        agent_id=record.id,
        lifecycle_state=record.data.lifecycle_state,
        published_version=record.data.published_version,
        published=published,
        draft=draft,
        draft_meta={k: v for k, v in (record.data.draft_meta or {}).items() if k != "last_test"},
        changes=[c.model_dump(mode="json") for c in diff_specs(published, draft)],
        rendered_prompt=runtime_prompt(draft),
        versions=[
            VersionView(**{k: v.get(k) for k in VersionView.model_fields if k in v})
            for v in reversed(record.data.versions)
        ],
        last_test=last_test_for(record, draft),
        can_publish=not blocker,
        publish_blocker=blocker,
    )


async def _save_agent(storage: StorageBase, user_id: str, record: AgentRecord) -> None:
    try:
        await storage.upsert_agent(user_id, record)
    except AgentRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _business_agent(storage: StorageBase, user_id: str, agent_id: str) -> AgentRecord:
    record = await storage.get_agent(user_id, agent_id)
    if record is None or record.data.system_role != "business" or record.source != "user":
        raise HTTPException(status_code=404, detail="Không tìm thấy agent")
    if ensure_spec(record):
        await _save_agent(storage, user_id, record)
    return record


async def _models(
    storage: StorageBase,
    user_id: str,
    access: ResourceAccessService,
    spec: AgentSpec | None = None,
) -> tuple[ChatModelBase, ChatModelBase]:
    """The working model (spec tier) and the judge/copilot model."""

    config = await _model_config(storage, user_id)
    from ..vin_platform import enabled
    from ..vin_platform._resources import PLATFORM_PROVIDER_ID
    # The deployment's strong model name belongs to the platform provider; a
    # customer's own provider keeps the model chosen for that key.
    own_key = enabled() and config.credential_id != PLATFORM_PROVIDER_ID
    strong = "" if own_key else os.getenv("WORKFORCE_LEADER_MODEL_NAME", "").strip()
    strong_config = config.model_copy(update={"model": strong}) if strong else config
    working = strong_config if spec is not None and spec.model_tier == "strong" else config
    copilot = await get_model(user_id, strong_config, access)
    apply_reasoning_effort(copilot, "builder")
    return await get_model(user_id, working, access), copilot


async def _create_record(
    storage: StorageBase,
    workspace_manager: WorkspaceManagerBase,
    user_id: str,
    spec: AgentSpec,
) -> AgentRecord:
    config = await _model_config(storage, user_id)
    record = AgentRecord(
        user_id=user_id,
        data=AgentData(
            name=spec.name,
            system_prompt=runtime_prompt(spec),
            context_config=_FIXED_CONTEXT.model_copy(deep=True),
            react_config=_FIXED_REACT.model_copy(deep=True),
            invite_config=InviteConfig(invitable=False, invite_description=spec.description or None),
            system_role="business",
            lifecycle_state="draft",
            build_description=spec.description or spec.goal,
            spec=spec.model_dump(mode="json"),
        ),
    )
    set_draft(record, spec, author="manager", note="Tạo mới")
    await _save_agent(storage, user_id, record)
    workspace_id = await workspace_manager.assign_workspace_id(
        user_id=user_id,
        agent_id=record.id,
        session_id=_generate_id(),
    )
    await storage.upsert_session(
        user_id=user_id,
        agent_id=record.id,
        config=SessionConfig(
            workspace_id=workspace_id,
            name="Agent Studio primary session",
            chat_model_config=config,
        ),
    )
    return record


# ---------------------------------------------------------------- routes


@workforce_studio_router.get("/agents/{agent_id}/resources")
async def effective_resources(agent_id: str, user_id=Depends(get_current_user_id), storage=Depends(get_storage),
                              access=Depends(get_resource_access_service)):
    from .._service._agent_readiness import resource_manifest
    record = await _business_agent(storage, user_id, agent_id)
    return await resource_manifest(storage, user_id, record, access=access)


@workforce_studio_router.get("/templates")
async def list_templates() -> list[dict]:
    return template_list()


@workforce_studio_router.get("/tools")
async def list_tools(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[dict]:
    return [
        {k: v for k, v in tool.items() if k != "input_schema"}
        for tool in (await tool_catalog(storage, user_id)).values()
    ]


@workforce_studio_router.get("/agents", response_model=list[AgentSummaryView])
async def list_agents(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[AgentSummaryView]:
    views = []
    for record in await storage.list_agents(user_id):
        if record.source != "user" or record.data.system_role != "business":
            continue
        if ensure_spec(record):
            await _save_agent(storage, user_id, record)
        views.append(_summary(record))
    return views


class AgentActivityView(BaseModel):
    """What one agent spent: replies and tokens over its sessions."""

    agent_id: str
    name: str
    role: str
    model_tier: str
    tickets: int = 0
    replies: int = 0
    """A reply may take several model calls; its usage covers them all."""
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    last_at: str | None = None


# Messages read per session; a ticket longer than this counts its latest part.
_ACTIVITY_MESSAGES = 2000


@workforce_studio_router.get("/activity", response_model=list[AgentActivityView])
async def agent_activity(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[AgentActivityView]:
    """Per agent (the Leader and every business agent): tickets it worked
    on, replies and tokens, from each reply's provider usage."""

    views = []
    for record in await storage.list_agents(user_id):
        role = record.data.system_role
        if record.source != "user" or role not in ("leader", "business"):
            continue
        spec = record.data.spec or {}
        view = AgentActivityView(
            agent_id=record.id,
            name=record.data.name,
            role=role,
            model_tier="strong" if role == "leader" else str(spec.get("model_tier") or "standard"),
        )
        for session in await storage.list_sessions(user_id, record.id):
            messages, _ = await storage.list_messages(user_id, session.id, limit=_ACTIVITY_MESSAGES)
            used = [m for m in messages if m.role == "assistant" and m.usage is not None]
            if not used:
                continue
            view.tickets += 1
            view.replies += len(used)
            view.input_tokens += sum(m.usage.input_tokens for m in used)
            view.cached_input_tokens += sum(m.usage.cache_input_tokens for m in used)
            view.output_tokens += sum(m.usage.output_tokens for m in used)
            view.last_at = max(view.last_at or "", *(m.created_at for m in used))
        views.append(view)
    return sorted(views, key=lambda item: item.input_tokens + item.output_tokens, reverse=True)


class CollaborationLink(BaseModel):
    """Two agents that worked in the same ticket room."""

    source: str
    target: str
    kind: Literal["leader", "peer"]
    """``leader``: the Leader brought the agent in; ``peer``: two members of one room."""
    tickets: int
    last_at: str


@workforce_studio_router.get("/collaboration", response_model=list[CollaborationLink])
async def collaboration(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[CollaborationLink]:
    """Who worked with whom: one count per room (ticket) in the last ``days``."""

    from datetime import timedelta

    since = datetime.now() - timedelta(days=days)
    links: dict[tuple[str, str, str], CollaborationLink] = {}

    def add(source: str, target: str, kind: str, at: str) -> None:
        key = (source, target, kind)
        link = links.get(key)
        if link is None:
            links[key] = CollaborationLink(source=source, target=target, kind=kind, tickets=1, last_at=at)
        else:
            link.tickets += 1
            link.last_at = max(link.last_at, at)

    for team in await storage.list_teams(user_id):
        if team.updated_at.replace(tzinfo=None) < since:
            continue
        at = team.updated_at.isoformat()
        members = sorted({member.agent_id for member in team.data.members} - {team.leader_agent_id})
        for member in members:
            if team.leader_agent_id:
                add(team.leader_agent_id, member, "leader", at)
        for index, first in enumerate(members):
            for second in members[index + 1:]:
                add(first, second, "peer", at)
    return sorted(links.values(), key=lambda link: link.tickets, reverse=True)


@workforce_studio_router.get("/quality")
async def ticket_quality(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Outcomes, message quality and cost of this manager's partner tickets."""

    quality = getattr(request.app.state, "partner_quality", None)
    if quality is None:
        raise HTTPException(status_code=404, detail="Chưa bật API đối tác (WORKFORCE_PARTNER_API).")
    return await quality(user_id, days)


@workforce_studio_router.get("/observability")
async def model_observability(request: Request, days: int = Query(default=30, ge=1, le=365),
                              user_id: str = Depends(get_current_user_id), storage: StorageBase = Depends(get_storage)):
    from .._model_ledger import observability
    result = await observability(storage, user_id, days)
    quality = getattr(request.app.state, "partner_quality", None)
    if quality is not None:
        ticket = await quality(user_id, days)
        result.update(successful_tickets=ticket["closed_confirmed"],
                      successful_ticket_cost_usd=ticket.get("successful_ticket_cost_usd"),
                      cost_per_successful_ticket_usd=ticket["cost_per_confirmed_usd"])
        result["backlog"].update(tickets_open=ticket["open"], tickets_need_attention=ticket["needs_attention"])
    return result


@workforce_studio_router.get("/model-calls")
async def model_call_evidence(since: str, until: str, offset: int = Query(default=0, ge=0),
                              limit: int = Query(default=200, ge=1, le=1000),
                              user_id: str = Depends(get_current_user_id), storage: StorageBase = Depends(get_storage)):
    from datetime import UTC, datetime
    try:
        start, end = datetime.fromisoformat(since), datetime.fromisoformat(until)
        if start.tzinfo is None or end.tzinfo is None or end < start:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(422, "Use an ordered, timezone-aware since/until window") from exc
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    rows = await storage.list_model_calls(user_id, since=start.isoformat(), until=end.isoformat(), offset=offset, limit=limit + 1)
    from .._model_ledger import costed
    return {"calls": costed(rows[:limit]), "next_offset": offset + limit if len(rows) > limit else None,
            "since": start.isoformat(), "until": end.isoformat(), "before_ledger_unknown": True}


@workforce_studio_router.post(
    "/agents",
    response_model=AgentDetailView,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    body: CreateAgentRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> AgentDetailView:
    if body.spec is not None:
        spec = body.spec
    elif body.template_id:
        template = TEMPLATES.get(body.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Không có mẫu này")
        spec = template["spec"].model_copy(deep=True)
    elif body.clone_from:
        source = await _business_agent(storage, user_id, body.clone_from)
        spec = draft_spec(source).model_copy(update={"name": draft_spec(source).name + " (bản sao)"})
    else:
        spec = AgentSpec(name="Agent mới")
    record = await _create_record(storage, workspace_manager, user_id, spec)
    return _detail(record)


@workforce_studio_router.post("/agents/compose", response_model=ComposeView)
async def compose_agent(
    body: ComposeRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> ComposeView:
    """Create draft agents from a plain-language description: one, or a team
    when ``allow_team`` and the work splits into specialities."""

    base = (
        TEMPLATES[body.template_id]["spec"].model_copy(deep=True)
        if body.template_id in TEMPLATES
        else AgentSpec(name="Agent mới")
    )
    _, copilot_model = await _models(storage, user_id, access)
    catalog = await tool_catalog(storage, user_id)
    knowledge = await knowledge_catalog(storage, user_id, access=access)
    skills = await skill_catalog(storage, user_id)
    plan = await plan_composition(
        model=copilot_model,
        description=body.description,
        catalog=catalog,
        knowledge=knowledge,
        skills=skills,
        allow_team=body.allow_team,
    )
    team = [agent.name for agent in plan.agents]
    created: list[AgentRecord] = []
    first: tuple[CopilotReply, list[dict]] | None = None
    for planned in plan.agents:
        message = "Tạo agent theo mô tả sau:\n" + planned.brief
        if len(team) > 1:
            message += (
                f"\n\nAgent này là {planned.name} ({planned.role}) trong nhóm: " + ", ".join(team)
                + ". Ghi các đồng đội vào collaborates."
            )
            base = base.model_copy(update={"name": planned.name})
        reply, spec, changes = await copilot_turn(
            model=copilot_model, spec=base, message=message,
            catalog=catalog, knowledge=knowledge, skills=skills,
        )
        if len(spec.tests) < MIN_TESTS_TO_PUBLISH:
            # Publishing needs tests; ask once for the missing ones.
            _, spec, _ = await copilot_turn(
                model=copilot_model, spec=spec,
                message=f"Thêm kịch bản kiểm thử cho đủ ít nhất {MIN_TESTS_TO_PUBLISH} kịch bản, mỗi kịch bản có kỳ vọng rõ.",
                catalog=catalog, knowledge=knowledge, skills=skills,
            )
            changes = [change.model_dump(mode="json") for change in diff_specs(base, spec)]
        created.append(await _create_record(storage, workspace_manager, user_id, spec))
        first = first or (reply, changes)
    reports: dict[str, dict] = {}
    if body.run_tests:
        for record in created:
            spec = draft_spec(record)
            if spec.tests:
                reports[record.id] = await _run_and_record(storage, user_id, access, record.id, spec)
        created = [await _business_agent(storage, user_id, record.id) for record in created]
    reply, changes = first
    if plan.mode == "team" and len(created) > 1:
        reply.assistant_message = (
            f"Tạo nhóm {len(created)} agent ({', '.join(team)}): {plan.reason} " + reply.assistant_message
        )
    details = [_detail(record) for record in created]
    return ComposeView(
        reply=reply, changes=changes, agent=details[0], plan=plan, agents=details, test_reports=reports,
    )


@workforce_studio_router.get("/agents/{agent_id}", response_model=AgentDetailView)
async def get_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> AgentDetailView:
    return _detail(await _business_agent(storage, user_id, agent_id))


@workforce_studio_router.put("/agents/{agent_id}/draft", response_model=AgentDetailView)
async def save_draft(
    agent_id: str,
    body: DraftRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        set_draft(record, body.spec, author="manager", note=body.note)
        await _save_agent(storage, user_id, record)
    return _detail(record)


@workforce_studio_router.delete("/agents/{agent_id}/draft", response_model=AgentDetailView)
async def discard_draft(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        if not record.data.published_version:
            raise HTTPException(status_code=409, detail="Agent chưa phát hành; không có bản để quay về.")
        record.data.draft_spec = None
        record.data.draft_meta = {}
        await _save_agent(storage, user_id, record)
    return _detail(record)


@workforce_studio_router.post("/agents/{agent_id}/copilot", response_model=CopilotView)
async def copilot(
    agent_id: str,
    body: CopilotRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> CopilotView:
    record = await _business_agent(storage, user_id, agent_id)
    _, copilot_model = await _models(storage, user_id, access)
    reply, spec, changes = await copilot_turn(
        model=copilot_model,
        spec=draft_spec(record),
        message=body.message,
        catalog=await tool_catalog(storage, user_id),
        knowledge=await knowledge_catalog(storage, user_id, access=access),
        skills=await skill_catalog(storage, user_id),
    )
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        if changes:
            set_draft(record, spec, author="builder", note=body.message[:300])
            await _save_agent(storage, user_id, record)
    return CopilotView(reply=reply, changes=changes, agent=_detail(record))


@workforce_studio_router.post("/agents/{agent_id}/tests/run")
async def run_tests(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> dict:
    record = await _business_agent(storage, user_id, agent_id)
    spec = draft_spec(record)
    if not spec.tests:
        raise HTTPException(status_code=409, detail="Agent chưa có kịch bản kiểm thử.")
    return await _run_and_record(storage, user_id, access, agent_id, spec)


@workforce_studio_router.get("/agents/{agent_id}/tests/progress")
async def test_progress(agent_id: str, user_id: str = Depends(get_current_user_id), storage: StorageBase = Depends(get_storage)):
    from .._service._eval_progress import EVAL_AGENT, progress_view
    await _business_agent(storage, user_id, agent_id)
    return progress_view(await storage.get_session(user_id, EVAL_AGENT, "eval-" + agent_id))


async def _run_and_record(storage, user_id, access, agent_id: str, spec: AgentSpec) -> dict:
    from .._service._eval_progress import EvalProgress
    model, judge_model = await _models(storage, user_id, access, spec)
    for selected in (model, judge_model):
        selected._usage_attributes = {"user_id": user_id, "agent_id": agent_id,
                                      "operation_id": spec_hash(spec), "purpose": "eval"}
    progress = await EvalProgress.for_agent(storage, user_id, agent_id, await _model_config(storage, user_id))
    await progress.stage("preparing")
    try:
        report = await run_spec_tests(spec=spec, model=model, judge_model=judge_model,
            discovered=await tool_catalog(storage, user_id), run_tool=tool_runner(storage, user_id, spec), on_progress=progress.event,
            sandbox=await eval_sandbox(storage, user_id, spec))
        await progress.report(report)
    except BaseException:
        await progress.fail()
        raise
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        if spec_hash(draft_spec(record)) != spec_hash(spec):
            await progress.stage("error", status="error", error="Bản nháp đã thay đổi trong khi kiểm thử; hãy chạy lại trên bản mới.")
            raise HTTPException(status_code=409, detail="Bản nháp đã thay đổi trong khi kiểm thử; hãy chạy lại.")
        if record.data.draft_spec is None:
            # Testing the published spec: keep the report on a draft copy so
            # the manager can publish an identical re-test if needed.
            set_draft(record, spec, author="manager", note="Kiểm thử bản đang phát hành")
        record_test_run(record, report)
        await _save_agent(storage, user_id, record)
    await progress.finish()
    return report


@workforce_studio_router.post("/agents/{agent_id}/publish", response_model=AgentDetailView)
async def publish(
    agent_id: str,
    body: PublishRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        spec = draft_spec(record)
        blocker = _publish_blocker(record, spec)
        if blocker:
            raise HTTPException(status_code=409, detail=blocker)
        report = last_test_for(record, spec) or record.data.evaluation
        author = (record.data.draft_meta or {}).get("author", "manager")
        previous = published_spec(record) if record.data.published_version else None
        record = record.model_copy(deep=True)
        record.data.resource_workspace_id = "published-" + _generate_id()
        materialize(record, spec, author=author, note=body.note, evaluation=report)
        await apply_bindings(
            storage, workspace_manager, user_id, record, spec,
            install_skill=_skill_installer(request, storage, user_id, agent_id), previous=previous, stage=True,
            access=access,
        )
        # CAS activates the version and its prepared resources together. A
        # failed/losing publication never mutates the active workspace.
        await _save_agent(storage, user_id, record)
    return _detail(record)


@workforce_studio_router.post("/agents/{agent_id}/rollback", response_model=AgentDetailView)
async def rollback(
    agent_id: str,
    body: RollbackRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        target = next((v for v in record.data.versions if v["version"] == body.version), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Không có phiên bản này")
        spec = AgentSpec.model_validate(target["spec"])
        report = target.get("evaluation")
        blocker = publish_blocker(spec, report)
        if blocker:
            # A historical unchecked version cannot bypass today's policy.
            set_draft(record, spec, author="manager", note=f"Kiểm thử lại phiên bản {body.version}")
            await _save_agent(storage, user_id, record)
            raise HTTPException(status_code=409, detail=blocker)
        previous = published_spec(record) if record.data.published_version else None
        record = record.model_copy(deep=True)
        record.data.resource_workspace_id = "published-" + _generate_id()
        materialize(
            record,
            spec,
            author="manager",
            note=body.note or f"Quay về phiên bản {body.version}",
            evaluation=report,
        )
        await apply_bindings(
            storage, workspace_manager, user_id, record, spec,
            install_skill=_skill_installer(request, storage, user_id, agent_id), previous=previous, stage=True,
            access=access,
        )
        await _save_agent(storage, user_id, record)
    return _detail(record)


@workforce_studio_router.post("/agents/{agent_id}/withdraw", response_model=AgentDetailView)
async def withdraw(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        record.data.lifecycle_state = "withdrawn"
        record.data.invite_config = InviteConfig(
            invitable=False,
            invite_description=record.data.invite_config.invite_description,
        )
        await _save_agent(storage, user_id, record)
    return _detail(record)


def _skill_installer(request: Request, storage: StorageBase, user_id: str, agent_id: str):
    """Put one library skill into the agent's workspace (re-fetched from its hub)."""

    async def install(workspace, skill_id: str) -> None:
        record = await resolve_catalog_resource(storage, user_id, "skill", skill_id)
        if record is None or not getattr(record, "enabled", True) or getattr(record, "review_status", "approved") != "approved":
            raise HTTPException(status_code=409, detail=f"Skill {skill_id} không còn trong thư viện.")
        present = {getattr(item, "name", item) for item in await workspace.list_skills(agent_id=agent_id)}
        if record.name in present:
            return
        from .._service._skill_packages import archive_bytes, byte_stream, cache_archive
        if getattr(record, "archive_base64", ""):
            await workspace.add_skill_archive(byte_stream(archive_bytes(record)), record.archive_format, record.name, agent_id=agent_id)
            return
        if not record.hub_id and record.markdown:
            # Locally authored library skills already have their reviewed
            # SKILL.md snapshot; they do not require a remote hub download.
            from ._workforce_console import _archive
            await workspace.add_skill_archive(_archive(record.name, record.markdown), "tar", record.name, agent_id=agent_id)
            return
        hub = (await get_skill_hubs(request)).get(record.hub_id or "")
        if hub is None:
            raise HTTPException(status_code=409, detail=f"Hub của skill {record.name} không còn đăng ký.")
        archive = await hub.download(user_id, record.card_id or record.name, record.version)
        service = await get_workspace_service(request)
        if hasattr(record, "archive_base64"):
            await cache_archive(record, archive.stream, archive.format)
            await service.install_skill(workspace, byte_stream(archive_bytes(record)), archive.format, record.name, agent_id=agent_id)
            # Cache only after the existing archive validator accepted it.
            if record.user_id == user_id:
                await storage.upsert_skill(user_id, record)
        else:
            await service.install_skill(workspace, archive.stream, archive.format, record.name, agent_id=agent_id)

    return install


@workforce_studio_router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    session_service=Depends(get_session_service),
) -> None:
    """Remove a business agent and its sessions.

    Refused while something still depends on it: each guard on
    ``app.state.agent_delete_guards`` (e.g. a partner route that uses the
    agent as its leader or member) returns why, or ``None``.
    """

    async with _locks[agent_id]:
        await _business_agent(storage, user_id, agent_id)
        for guard in getattr(request.app.state, "agent_delete_guards", None) or []:
            reason = await guard(user_id, agent_id)
            if reason:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
        await session_service.delete_agent(user_id, agent_id)


@workforce_studio_router.get("/agents/{agent_id}/memories")
async def list_memories(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    shared_storage: StorageBase = Depends(get_shared_context_storage),
) -> list[dict]:
    await _business_agent(storage, user_id, agent_id)
    try:
        memories = await shared_storage.list_agent_memories(user_id, agent_id, limit=300)
    except NotImplementedError:
        return []
    return [memory.model_dump(mode="json") for memory in memories]


@workforce_studio_router.post("/agents/{agent_id}/memories/{memory_id}/retire")
async def retire_memory(
    agent_id: str,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    shared_storage: StorageBase = Depends(get_shared_context_storage),
) -> dict:
    await _business_agent(storage, user_id, agent_id)
    memory = await AgentMemoryService(shared_storage).retire(user_id, agent_id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ký ức")
    return memory.model_dump(mode="json")


@workforce_studio_router.post("/preview")
async def preview_prompt(spec: AgentSpec) -> dict:
    """Render a spec without saving (live preview while editing the form)."""

    return {"authored": render_prompt(spec), "runtime": runtime_prompt(spec)}


__all__ = ["workforce_studio_router"]
