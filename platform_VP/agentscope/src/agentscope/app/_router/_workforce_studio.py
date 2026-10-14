"""Agent Studio API: manage business agents through forms, not only chat.

Every write goes through the Agent Spec draft. Publishing requires a test
run of that exact draft (hash-bound) that passes, then renders the prompt,
applies tool/knowledge bindings and records an immutable version.
"""

import asyncio
import os
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..._utils._common import _generate_id
from ...model import ChatModelBase
from .._agent_spec import AgentSpec, diff_specs, render_prompt
from .._agent_templates import TEMPLATES, template_list
from .._service import ResourceAccessService, get_model
from .._service._agent_eval import MIN_TESTS_TO_PUBLISH, PASS_THRESHOLD, run_spec_tests
from .._service._agent_studio import (
    CopilotReply,
    apply_bindings,
    copilot_turn,
    draft_spec,
    ensure_spec,
    last_test_for,
    materialize,
    record_test_run,
    runtime_prompt,
    set_draft,
    tool_catalog,
    tool_runner,
)
from .._agent_memory import AgentMemoryService
from ..deps import (
    get_current_user_id,
    get_resource_access_service,
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


class DraftRequest(BaseModel):
    spec: AgentSpec
    note: str = ""


class CopilotRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class CopilotView(BaseModel):
    reply: CopilotReply
    changes: list[dict]
    agent: AgentDetailView


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
            for k in ("pass_rate", "passed", "total", "ran_at", "publishable")
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


@workforce_studio_router.post("/agents/compose", response_model=CopilotView)
async def compose_agent(
    body: ComposeRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> CopilotView:
    """Create a draft agent from a plain-language description."""

    base = (
        TEMPLATES[body.template_id]["spec"].model_copy(deep=True)
        if body.template_id in TEMPLATES
        else AgentSpec(name="Agent mới")
    )
    _, copilot_model = await _models(storage, user_id, access)
    catalog = await tool_catalog(storage, user_id)
    reply, spec, changes = await copilot_turn(
        model=copilot_model,
        spec=base,
        message="Tạo agent theo mô tả sau:\n" + body.description,
        catalog=catalog,
    )
    record = await _create_record(storage, workspace_manager, user_id, spec)
    return CopilotView(reply=reply, changes=changes, agent=_detail(record))


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
        materialize(record, spec, author=author, note=body.note, evaluation=report)
        await apply_bindings(storage, workspace_manager, user_id, record, spec)
        await storage.upsert_agent(user_id, record)
    return _detail(record)


@workforce_studio_router.post("/agents/{agent_id}/rollback", response_model=AgentDetailView)
async def rollback(
    agent_id: str,
    body: RollbackRequest,
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
        materialize(
            record,
            spec,
            author="manager",
            note=body.note or f"Quay về phiên bản {body.version}",
            evaluation=None,
        )
        await apply_bindings(storage, workspace_manager, user_id, record, spec)
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
