"""Agent Studio API: manage business agents through forms, not only chat.

Every write goes through the Agent Spec draft. Publishing requires a test
run of that exact draft (hash-bound) that passes, then renders the prompt,
applies tool/knowledge bindings and records an immutable version.
"""

import asyncio
import os
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..._utils._common import _generate_id
from ...model import ChatModelBase
from .._agent_spec import AgentSpec, diff_specs, render_prompt
from .._agent_templates import TEMPLATES, template_list
from .._service import ResourceAccessService, get_model
from .._service._agent_eval import MIN_TESTS_TO_PUBLISH, PASS_THRESHOLD, run_spec_tests
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
    skill_catalog,
    runtime_prompt,
    set_draft,
    tool_catalog,
    tool_runner,
)
from .._agent_memory import AgentMemoryService
from ..deps import (
    get_current_user_id,
    get_resource_access_service,
    get_session_service,
    get_skill_hubs,
    get_workspace_service,
    get_shared_context_storage,
    get_storage,
    get_workspace_manager,
)
from ..storage import AgentData, AgentRecord, InviteConfig, SessionConfig, StorageBase
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
            return ""  # re-activate the last tested version
        if record.data.lifecycle_state == "published":
            return "Không có thay đổi nào cần phát hành."
    if len(spec.tests) < MIN_TESTS_TO_PUBLISH:
        return f"Cần ít nhất {MIN_TESTS_TO_PUBLISH} kịch bản kiểm thử."
    report = last_test_for(record, spec)
    if report is None:
        return "Hãy chạy kiểm thử cho bản nháp hiện tại trước khi phát hành."
    if report.get("errors"):
        return (
            f"Chưa kiểm thử được {report['errors']}/{report.get('total')} kịch bản: "
            f"{report.get('model_error')} Chạy lại kiểm thử sau khi sửa."
        )
    if not report.get("publishable"):
        return (
            f"Kiểm thử đạt {report.get('passed')}/{report.get('total')}; "
            f"cần tối thiểu {int(PASS_THRESHOLD * 100)}%."
        )
    return ""


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


async def _business_agent(storage: StorageBase, user_id: str, agent_id: str) -> AgentRecord:
    record = await storage.get_agent(user_id, agent_id)
    if record is None or record.data.system_role != "business" or record.source != "user":
        raise HTTPException(status_code=404, detail="Không tìm thấy agent")
    if ensure_spec(record):
        await storage.upsert_agent(user_id, record)
    return record


async def _models(
    storage: StorageBase,
    user_id: str,
    access: ResourceAccessService,
    spec: AgentSpec | None = None,
) -> tuple[ChatModelBase, ChatModelBase]:
    """The working model (spec tier) and the judge/copilot model."""

    config = await _model_config(storage, user_id)
    strong = os.getenv("WORKFORCE_LEADER_MODEL_NAME", "").strip()
    strong_config = config.model_copy(update={"model": strong}) if strong else config
    working = strong_config if spec is not None and spec.model_tier == "strong" else config
    return (
        await get_model(user_id, working, access),
        await get_model(user_id, strong_config, access),
    )


async def _create_record(
    storage: StorageBase,
    workspace_manager: WorkspaceManagerBase,
    user_id: str,
    spec: AgentSpec,
) -> AgentRecord:
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
    await storage.upsert_agent(user_id, record)
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
            chat_model_config=await _model_config(storage, user_id),
        ),
    )
    return record


# ---------------------------------------------------------------- routes


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
            await storage.upsert_agent(user_id, record)
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
    knowledge = await knowledge_catalog(storage, user_id)
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
        await storage.upsert_agent(user_id, record)
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
        await storage.upsert_agent(user_id, record)
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
        knowledge=await knowledge_catalog(storage, user_id),
        skills=await skill_catalog(storage, user_id),
    )
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        if changes:
            set_draft(record, spec, author="builder", note=body.message[:300])
            await storage.upsert_agent(user_id, record)
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


async def _run_and_record(storage, user_id, access, agent_id: str, spec: AgentSpec) -> dict:
    model, judge_model = await _models(storage, user_id, access, spec)
    report = await run_spec_tests(
        spec=spec,
        model=model,
        judge_model=judge_model,
        discovered=await tool_catalog(storage, user_id),
        run_tool=tool_runner(storage, user_id, spec),
    )
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        if record.data.draft_spec is None:
            # Testing the published spec: keep the report on a draft copy so
            # the manager can publish an identical re-test if needed.
            set_draft(record, spec, author="manager", note="Kiểm thử bản đang phát hành")
        record_test_run(record, report)
        await storage.upsert_agent(user_id, record)
    return report


@workforce_studio_router.post("/agents/{agent_id}/publish", response_model=AgentDetailView)
async def publish(
    agent_id: str,
    body: PublishRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        spec = draft_spec(record)
        blocker = _publish_blocker(record, spec)
        if blocker:
            raise HTTPException(status_code=409, detail=blocker)
        report = last_test_for(record, spec)
        author = (record.data.draft_meta or {}).get("author", "manager")
        previous = published_spec(record) if record.data.published_version else None
        materialize(record, spec, author=author, note=body.note, evaluation=report)
        await apply_bindings(
            storage, workspace_manager, user_id, record, spec,
            install_skill=_skill_installer(request, storage, user_id, agent_id), previous=previous,
        )
        await storage.upsert_agent(user_id, record)
    return _detail(record)


@workforce_studio_router.post("/agents/{agent_id}/rollback", response_model=AgentDetailView)
async def rollback(
    agent_id: str,
    body: RollbackRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
) -> AgentDetailView:
    async with _locks[agent_id]:
        record = await _business_agent(storage, user_id, agent_id)
        target = next((v for v in record.data.versions if v["version"] == body.version), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Không có phiên bản này")
        spec = AgentSpec.model_validate(target["spec"])
        previous = published_spec(record) if record.data.published_version else None
        materialize(
            record,
            spec,
            author="manager",
            note=body.note or f"Quay về phiên bản {body.version}",
            evaluation=None,
        )
        await apply_bindings(
            storage, workspace_manager, user_id, record, spec,
            install_skill=_skill_installer(request, storage, user_id, agent_id), previous=previous,
        )
        await storage.upsert_agent(user_id, record)
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
        await storage.upsert_agent(user_id, record)
    return _detail(record)


def _skill_installer(request: Request, storage: StorageBase, user_id: str, agent_id: str):
    """Put one library skill into the agent's workspace (re-fetched from its hub)."""

    async def install(workspace, skill_id: str) -> None:
        record = await storage.get_skill(user_id, skill_id)
        if record is None:
            raise HTTPException(status_code=409, detail=f"Skill {skill_id} không còn trong thư viện.")
        present = {getattr(item, "name", item) for item in await workspace.list_skills(agent_id=agent_id)}
        if record.name in present:
            return
        hub = (await get_skill_hubs(request)).get(record.hub_id or "")
        if hub is None:
            raise HTTPException(status_code=409, detail=f"Hub của skill {record.name} không còn đăng ký.")
        archive = await hub.download(user_id, record.card_id or record.name, record.version)
        service = await get_workspace_service(request)
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
