"""Agent Studio: drafts, versions, publishing and the Builder copilot.

One place owns the lifecycle of a business agent's :class:`AgentSpec`:

* a draft is edited by the form, the copilot or self-improvement;
* publishing renders the prompt from the spec, applies the tool and
  knowledge bindings, and appends an immutable version;
* rollback republishes an older version as a new version (history is never
  rewritten).
"""

from __future__ import annotations

from ...model._call_observer import usage_purpose

import copy
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..._logging import logger
from ...mcp import MCPClient
from ...message import UserMsg
from ...model import ChatModelBase
from .._agent_spec import (
    AgentSpec,
    SpecOperation,
    SpecPatchError,
    SpecSource,
    apply_operations,
    diff_specs,
    render_prompt,
    spec_from_legacy,
    spec_hash,
    tool_bindings,
)
from .._workforce_policy import BUSINESS_AGENT_EVIDENCE_POLICY, governed_system_prompt
from ..storage import AgentRecord, InviteConfig, StorageBase
from ._publish_gate import publication_blocker
from ._agent_eval import catalog_allows_read

def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- spec state


def ensure_spec(record: AgentRecord) -> bool:
    """Give an agent made before Agent Spec its spec and version 1.

    Returns ``True`` when the record changed and must be saved. The rendered
    prompt stays byte-identical (the authored prompt becomes the override).
    """

    if record.data.spec:
        return False
    spec = spec_from_legacy(
        name=record.data.name,
        description=record.data.build_description
        or record.data.invite_config.invite_description
        or "",
        system_prompt=record.data.system_prompt,
        bindings=record.data.tool_bindings,
        policy=BUSINESS_AGENT_EVIDENCE_POLICY,
    )
    record.data.spec = spec.model_dump(mode="json")
    if record.data.lifecycle_state == "published" and not record.data.versions:
        record.data.versions = [
            {
                "version": 1,
                "spec": record.data.spec,
                "system_prompt": record.data.system_prompt,
                "author": "legacy",
                "note": "Phiên bản có sẵn trước khi dùng Agent Spec",
                "created_at": _now(),
                "evaluation": record.data.evaluation or None,
            },
        ]
        record.data.published_version = 1
    return True


def published_spec(record: AgentRecord) -> AgentSpec:
    return AgentSpec.model_validate(record.data.spec)


def draft_spec(record: AgentRecord) -> AgentSpec:
    return AgentSpec.model_validate(record.data.draft_spec or record.data.spec)


def set_draft(
    record: AgentRecord,
    spec: AgentSpec,
    *,
    author: SpecSource,
    note: str = "",
) -> None:
    record.data.draft_spec = spec.model_dump(mode="json")
    meta = dict(record.data.draft_meta or {})
    if meta.get("spec_hash") != spec_hash(spec):
        meta.pop("last_test", None)
    meta.update(
        {
            "author": author,
            "note": note[:1000],
            "updated_at": _now(),
            "spec_hash": spec_hash(spec),
        },
    )
    record.data.draft_meta = meta


def record_test_run(record: AgentRecord, report: dict) -> None:
    # A slow test of an earlier draft must never replace the current evidence.
    if report.get("spec_hash") != spec_hash(draft_spec(record)):
        return
    meta = dict(record.data.draft_meta or {})
    meta["last_test"] = copy.deepcopy(report)
    record.data.draft_meta = meta


def last_test_for(record: AgentRecord, spec: AgentSpec) -> dict | None:
    report = (record.data.draft_meta or {}).get("last_test")
    if report and report.get("spec_hash") == spec_hash(spec):
        return report
    return None


def pinned_view(record: AgentRecord, version: int) -> AgentRecord:
    """The agent as it was published in ``version`` (for a running ticket).

    Unknown versions fail closed: silently serving the current publication
    would change an in-flight ticket's behavior.
    """

    stored = next((v for v in record.data.versions if v.get("version") == version), None)
    if stored is None:
        raise SpecPatchError(f"Pinned agent version {version} is unavailable")
    view = record.model_copy(deep=True)
    view.data.published_version = version
    view.data.system_prompt = stored["system_prompt"]
    view.data.evaluation = copy.deepcopy(stored.get("evaluation") or {})
    view.data.resource_workspace_id = stored.get("resource_workspace_id")
    if stored.get("spec"):
        view.data.spec = copy.deepcopy(stored["spec"])
        view.data.name = AgentSpec.model_validate(stored["spec"]).name
        view.data.tool_bindings = tool_bindings(AgentSpec.model_validate(stored["spec"]))
    return view


def runtime_prompt(spec: AgentSpec) -> str:
    return governed_system_prompt("business", render_prompt(spec))


def materialize(
    record: AgentRecord,
    spec: AgentSpec,
    *,
    author: SpecSource,
    note: str,
    evaluation: dict | None,
    trusted_provisioning: dict | None = None,
) -> int:
    """Make ``spec`` the served version of ``record``; return its number."""

    report = trusted_provisioning if trusted_provisioning is not None else evaluation
    blocker = publication_blocker(spec, report, allow_provisioning=trusted_provisioning is not None)
    if trusted_provisioning is not None and trusted_provisioning.get("source") == "system_leader" \
            and record.data.system_role != "leader":
        blocker = "System Leader provenance cannot publish a business agent"
    if blocker:
        raise SpecPatchError(blocker)
    version = (max((v["version"] for v in record.data.versions), default=0)) + 1
    prompt = runtime_prompt(spec)
    record.data.name = spec.name
    record.data.system_prompt = prompt
    record.data.build_description = spec.description or spec.goal
    record.data.tool_bindings = tool_bindings(spec)
    record.data.invite_config = InviteConfig(
        invitable=True,
        invite_description=(spec.description or spec.goal or spec.name)[:1000],
    )
    record.data.lifecycle_state = "published"
    record.data.spec = spec.model_dump(mode="json")
    record.data.draft_spec = None
    record.data.draft_meta = {}
    record.data.evaluation = copy.deepcopy(report)
    record.data.versions = [
        *record.data.versions,
        {
            "version": version,
            "spec": copy.deepcopy(record.data.spec),
            "system_prompt": prompt,
            "author": author,
            "note": note[:1000],
            "created_at": _now(),
            "evaluation": copy.deepcopy(record.data.evaluation),
            "resource_workspace_id": record.data.resource_workspace_id,
        },
    ]
    record.data.published_version = version
    return version


async def apply_bindings(
    storage: StorageBase,
    workspace_manager: Any,
    user_id: str,
    record: AgentRecord,
    spec: AgentSpec,
    install_skill: Any = None,
    previous: AgentSpec | None = None,
    stage: bool = False,
) -> None:
    """Point the agent's primary session at exactly the spec's tools/knowledge.

    Team sessions copy MCP declarations from the primary session when the
    agent is invited, so new tickets pick up the change; running tickets keep
    what they started with. Skills live in the agent's workspace (shared by
    its team sessions): ``install_skill(workspace, skill_id)`` adds one from
    the library; skills the previous version listed and this one does not are
    removed.
    """

    sessions = await storage.list_sessions(user_id, record.id)
    primary = next((session for session in sessions
                    if getattr(getattr(session, "origin", None), "type", "user") == "user"
                    and not getattr(session, "team_id", None)), None)
    if primary is None:
        raise SpecPatchError("Agent chưa có phiên chính để chuẩn bị tài nguyên.")
    if stage:
        primary = primary.model_copy(deep=True)
        primary.config.workspace_id = record.data.resource_workspace_id
    workspace = await workspace_manager.get_workspace(
        user_id,
        record.id,
        primary.id,
        primary.config.workspace_id,
    )
    partition = "" if stage else primary.id
    # Prepared publications start in a private directory. Never connect old
    # clients or remove the previous version's resources while staging.
    for client in ([] if stage else await workspace.list_mcps(agent_id=record.id, session_id=partition)):
        await workspace.remove_mcp(client.name, agent_id=record.id, session_id=partition)
    for default_mcp in ([] if stage else workspace.default_mcps):
        await workspace.remove_mcp(default_mcp.name, agent_id=record.id, session_id=partition)
    if stage:
        # Explicit empty declaration prevents unrelated default MCPs returning.
        await workspace.set_mcp_declarations([], agent_id=record.id)
    selected: dict[str, list[str]] = {}
    confirm: dict[str, list[str]] = {}
    for tool in spec.tools:
        if tool.mcp_id and tool.tool_name:
            selected.setdefault(tool.mcp_id, []).append(tool.tool_name)
            if tool.requires_consent:
                confirm.setdefault(tool.mcp_id, []).append(tool.tool_name)
    for mcp_id, names in selected.items():
        mcp_record = await storage.get_mcp(user_id, mcp_id)
        if mcp_record is None or not mcp_record.enabled:
            raise SpecPatchError(f"MCP {mcp_id} không còn khả dụng")
        client = MCPClient.model_validate(mcp_record.client.model_dump(mode="json"))
        client.enable_tools = list(dict.fromkeys(names))
        # Publishing cannot remove the server's consent requirement by editing
        # a draft flag. Unknown tools are also confirmation-only at runtime.
        metadata = {item.get("name"): item for item in mcp_record.discovered_tools}
        if stage and any(name not in metadata for name in names):
            raise SpecPatchError("Công cụ không còn trong catalog MCP; hãy đồng bộ và kiểm tra lại.")
        required = set(client.confirm_tools or []) | set(confirm.get(mcp_id) or [])
        required.update(name for name in names if not catalog_allows_read(metadata.get(name, {})))
        client.confirm_tools = sorted(required.intersection(names)) or None
        if stage:
            await workspace.set_mcp_declarations(
                [*workspace.declared_mcps(agent_id=record.id), client], agent_id=record.id,
            )
        else:
            await workspace.add_mcp(client, agent_id=record.id, session_id=primary.id)
    wanted = {item.skill_id: item for item in spec.skills}
    if install_skill is not None:
        for skill_id in wanted:
            await install_skill(workspace, skill_id)
    for item in previous.skills if previous is not None and not stage else []:
        if item.skill_id not in wanted and item.name:
            await workspace.remove_skill(item.name, agent_id=record.id)
    knowledge_ids = [item.kb_id for item in spec.knowledge]
    if knowledge_ids:
        available = {kb.id for kb in await storage.list_knowledge_bases(user_id)}
        if set(knowledge_ids) - available:
            raise SpecPatchError("Knowledge không còn trong thư viện của người quản lý.")
    config = primary.config
    if knowledge_ids:
        from ..storage._model._session import SessionKnowledgeConfig

        previous = config.knowledge_config.parameters if config.knowledge_config else {}
        config.knowledge_config = SessionKnowledgeConfig(
            knowledge_base_ids=knowledge_ids,
            parameters=previous,
        )
    else:
        config.knowledge_config = None
    # Pass state/origin explicitly: an update without them resets the state.
    if stage:
        return
    await storage.upsert_session(
        user_id=user_id,
        agent_id=record.id,
        config=config,
        state=primary.state,
        session_id=primary.id,
        origin=primary.origin,
    )


# ---------------------------------------------------------------- tool catalog


async def tool_catalog(storage: StorageBase, user_id: str) -> dict[str, dict]:
    """Every enabled MCP tool keyed by ``<mcp_id>:<tool_name>``."""

    catalog: dict[str, dict] = {}
    for record in await storage.list_mcps(user_id):
        if not record.enabled:
            continue
        for tool in record.discovered_tools:
            name = str(tool.get("name") or "").strip()
            if not name:
                continue
            read_only = tool.get("read_only") is True
            requires_consent = (
                tool.get("requires_consent", not read_only) is not False
                or name in (record.client.confirm_tools or [])
            )
            catalog[f"{record.id}:{name}"] = {
                "tool_id": f"{record.id}:{name}",
                "mcp_id": record.id,
                "mcp_name": record.client.name,
                "tool_name": name,
                "description": str(tool.get("description") or ""),
                "input_schema": tool.get("input_schema") or {},
                "read_only": read_only,
                "requires_consent": requires_consent,
            }
    return catalog


async def knowledge_catalog(storage: StorageBase, user_id: str) -> dict[str, dict]:
    """The manager's knowledge bases keyed by id (what the Builder may attach)."""

    return {
        record.id: {"kb_id": record.id, "name": record.data.name, "description": record.data.description}
        for record in await storage.list_knowledge_bases(user_id)
    }


async def skill_catalog(storage: StorageBase, user_id: str) -> dict[str, dict]:
    """The manager's enabled library skills keyed by id."""

    return {
        record.id: {
            "skill_id": record.id,
            "name": record.name,
            "description": record.description or record.display_name or "",
        }
        for record in await storage.list_skills(user_id)
        if getattr(record, "enabled", True) and getattr(record, "review_status", "approved") == "approved"
    }


def tool_runner(storage: StorageBase, user_id: str, spec: AgentSpec):
    """Run catalog-approved reads only, rechecking at the connector boundary."""

    by_name = {tool.tool_name: tool for tool in spec.tools}
    ambiguous = {name for name in by_name if sum(tool.tool_name == name for tool in spec.tools) != 1}

    async def run(name: str, arguments: dict) -> str:
        tool = by_name.get(name)
        if tool is None or name in ambiguous or tool.tool_id != f"{tool.mcp_id}:{name}":
            raise RuntimeError("Sandbox tool is not uniquely bound to the server catalog")
        mcp_record = await storage.get_mcp(user_id, tool.mcp_id)
        if mcp_record is None or not mcp_record.enabled:
            raise RuntimeError(f"MCP {tool.mcp_id} unavailable")
        # Fetch the current server record: the draft and the earlier eval
        # snapshot are not authority to execute an external tool.
        matches = [item for item in mcp_record.discovered_tools if item.get("name") == name]
        if (
            len(matches) != 1
            or not catalog_allows_read(matches[0])
            or tool.requires_consent
            or name in (mcp_record.client.confirm_tools or [])
        ):
            raise RuntimeError("Sandbox only executes server-classified read-only tools without consent")
        from ._eval_sandbox import call_tool

        client = MCPClient.model_validate(mcp_record.client.model_dump(mode="json"))
        return await call_tool(client, name, arguments, require_read_only=True)

    return run


# ---------------------------------------------------------------- copilot


class CopilotOperation(BaseModel):
    op: Literal["set", "add", "remove", "update"]
    field: str = Field(description="AgentSpec field name.")
    value: Any = Field(
        default=None,
        description=(
            "set: the new field value. add/update: the item. Items: rules "
            "{text, level: must|should}; escalation {when, to}; tools "
            "{tool_id, use_when, requires_consent}; knowledge {kb_id, use_for}; "
            "skills {skill_id, use_when}; "
            "collaborates {capability, ask_when}; examples {user, agent}; tests "
            "{scenario, expected, must_include[], must_not_include[], expect_tool}; "
            "scope_in/scope_out: a string."
        ),
    )
    item_id: str | None = Field(
        default=None,
        description="remove/update: the item's id (or its exact text for string lists).",
    )


class CopilotReply(BaseModel):
    assistant_message: str = Field(
        description="What you changed and why, in the manager's language; 1-4 sentences.",
    )
    questions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Only questions whose answer changes the agent's behaviour.",
    )
    operations: list[CopilotOperation] = Field(default_factory=list, max_length=40)


_COPILOT_INSTRUCTIONS = """You are the Agent Builder copilot of a business AI platform.
A manager (not a programmer) describes what they want from ONE business agent.
You edit that agent's specification (JSON below) by returning operations.

How to work:
- Translate each request into the smallest set of operations on the right
  fields: a behaviour the agent must always/never do is a rule (level must);
  a preference is a rule (level should); "hand over / call someone when..." is
  escalation; who it serves is audience; voice is tone; what it handles or not
  is scope_in / scope_out; "use tool X when..." is tools.
- Keep everything the manager did not ask to change. Never remove locked rules.
- Only use tool ids that exist in the TOOL CATALOG; never invent tools. If the
  needed capability is missing, say which tool must be added.
- Attach a KNOWLEDGE BASE when its content is what the agent must answer from
  (procedures, prices, policies), and a SKILL from the SKILL LIBRARY when it fits
  a task of the agent; say why in use_for / use_when. Only use listed ids.
- When creating an agent from a description, also fill name, description,
  goal, audience and tone, and keep at least 5 tests (scenario + expected behaviour)
  that cover the rules, an out-of-scope request and a case needing consent.
  Mark consent/privacy/safety cases safety_critical=true; at least one is required.
- When the manager asks to improve tests, add tests; do not weaken rules.
- Ask at most 3 questions, only when the answer changes behaviour (for example
  whether the agent may quote prices). Do not ask about things you can set to
  a sensible default; mention the default in assistant_message instead.
- Write rules, tests and messages in the manager's language.
"""


def _normalize_items(operations: list[CopilotOperation]) -> list[SpecOperation]:
    string_lists = {"scope_in", "scope_out"}
    normalized: list[SpecOperation] = []
    for item in operations:
        value = item.value
        if isinstance(value, str) and item.field not in string_lists and item.op in {"add", "update"}:
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                if item.field == "rules":
                    value = {"text": value}
                elif item.field == "tests":
                    value = {"scenario": value, "expected": value}
        normalized.append(
            SpecOperation(op=item.op, field=item.field, value=value, item_id=item.item_id),
        )
    return normalized


@usage_purpose("builder_copilot")
async def copilot_turn(
    *,
    model: ChatModelBase,
    spec: AgentSpec,
    message: str,
    catalog: dict[str, dict],
    knowledge: dict[str, dict] | None = None,
    skills: dict[str, dict] | None = None,
) -> tuple[CopilotReply, AgentSpec, list[dict]]:
    """Interpret one manager message as a patch on ``spec``.

    Returns the reply, the patched spec and the human-readable diff. When the
    model proposes an invalid patch, the operations that fail are dropped one
    by one and reported, rather than losing the whole turn.
    """

    tools = [
        {
            k: v for k, v in tool.items()
            if k in {"tool_id", "mcp_name", "tool_name", "description", "read_only", "requires_consent"}
        }
        for tool in catalog.values()
    ]
    context = (
        _COPILOT_INSTRUCTIONS
        + "\nCURRENT SPEC:\n"
        + json.dumps(spec.model_dump(mode="json"), ensure_ascii=False)
        + "\n\nTOOL CATALOG:\n"
        + json.dumps(tools, ensure_ascii=False)[:20000]
        + "\n\nKNOWLEDGE BASES:\n"
        + json.dumps(list((knowledge or {}).values()), ensure_ascii=False)[:6000]
        + "\n\nSKILL LIBRARY:\n"
        + json.dumps(list((skills or {}).values()), ensure_ascii=False)[:6000]
    )
    response = await model.generate_structured_output(
        messages=[
            UserMsg(name="system_context", content=context),
            UserMsg(name="manager", content=message),
        ],
        structured_model=CopilotReply,
    )
    reply = CopilotReply.model_validate(response.content)
    operations = _normalize_items(reply.operations)
    for operation in operations:
        if operation.field == "tools" and operation.op in {"add", "update"} and isinstance(operation.value, dict):
            meta = catalog.get(str(operation.value.get("tool_id") or ""))
            if meta is not None:
                operation.value = {
                    **operation.value,
                    "read_only": meta["read_only"] is True,
                    "requires_consent": (
                        meta.get("requires_consent", meta["read_only"] is not True) is not False
                        or operation.value.get("requires_consent") is True
                    ),
                    "mcp_id": meta["mcp_id"],
                    "mcp_name": meta["mcp_name"],
                    "tool_name": meta["tool_name"],
                }
        elif operation.field in {"knowledge", "skills"} and operation.op in {"add", "update"} and isinstance(
            operation.value, dict,
        ):
            key = "kb_id" if operation.field == "knowledge" else "skill_id"
            meta = ((knowledge if operation.field == "knowledge" else skills) or {}).get(
                str(operation.value.get(key) or ""),
            )
            if meta is not None:
                operation.value = {**operation.value, "name": meta["name"]}
    patched = spec
    rejected: list[str] = []
    for operation in operations:
        if operation.field == "tools" and operation.op == "add":
            tool_id = str((operation.value or {}).get("tool_id") or "")
            if tool_id not in catalog:
                rejected.append(f"tool {tool_id or '?'} không có trong kho tool")
                continue
        if operation.field in {"knowledge", "skills"} and operation.op == "add":
            key = "kb_id" if operation.field == "knowledge" else "skill_id"
            listed = (knowledge if operation.field == "knowledge" else skills) or {}
            item_id = str((operation.value or {}).get(key) or "")
            if item_id not in listed:
                where = "kho kiến thức" if operation.field == "knowledge" else "thư viện skill"
                rejected.append(f"{item_id or '?'} không có trong {where}")
                continue
        try:
            patched = apply_operations(patched, [operation], author="builder")
        except SpecPatchError as exc:
            logger.info("Copilot operation rejected: %s", exc)
            rejected.append(str(exc))
    if rejected:
        reply.assistant_message += " (Bỏ qua: " + "; ".join(rejected[:5]) + ")"
    # A model can also replace the whole tools list. Normalize every binding,
    # so that path cannot bypass the catalog checks for add/update operations.
    patched = patched.model_copy(deep=True)
    for tool in patched.tools:
        meta = catalog.get(tool.tool_id, {})
        tool.read_only = meta.get("read_only") is True
        tool.requires_consent = (
            tool.requires_consent
            or meta.get("requires_consent", not tool.read_only) is not False
        )
        if meta:
            tool.mcp_id = meta["mcp_id"]
            tool.mcp_name = meta["mcp_name"]
            tool.tool_name = meta["tool_name"]
    changes = [change.model_dump(mode="json") for change in diff_specs(spec, patched)]
    return reply, patched, changes


class PlannedAgent(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(description="What this agent does in the team, one sentence.")
    brief: str = Field(description="The description the copilot builds this agent from.")


class CompositionPlan(BaseModel):
    mode: Literal["single", "team"]
    reason: str = Field(description="Why one agent or a team, in the manager's language; 1-2 sentences.")
    agents: list[PlannedAgent] = Field(min_length=1, max_length=5)


_PLAN_INSTRUCTIONS = """You plan the agents a manager needs on a business AI platform.
Ticket handling works like this: a fixed Leader receives each request, invites
the published business agents it needs into the ticket's room, and they report
back. Decide from the manager's description, the tools, knowledge bases and
skills available:
- "single" when one agent with one coherent job and toolset is enough.
- "team" (2-5 agents) only when the work splits into specialities that need
  different tools or knowledge, or one agent's result is another's input (for
  example: lookup, then calculation). Do not split for its own sake.
Give each agent a short name, its role and a brief that says what it does,
which tools / knowledge / skills it should use, and which teammate it hands to.
Write in the manager's language."""


@usage_purpose("builder_plan")
async def plan_composition(
    *,
    model: ChatModelBase,
    description: str,
    catalog: dict[str, dict],
    knowledge: dict[str, dict],
    skills: dict[str, dict],
    allow_team: bool,
) -> CompositionPlan:
    """One agent, or a team of agents, for a plain-language description."""

    if not allow_team:
        return CompositionPlan(
            mode="single", reason="", agents=[PlannedAgent(name="Agent mới", role="", brief=description)],
        )
    tools = [
        {
            k: v for k, v in tool.items()
            if k in {"tool_id", "tool_name", "description", "read_only", "requires_consent"}
        }
        for tool in catalog.values()
    ]
    context = (
        _PLAN_INSTRUCTIONS
        + "\n\nTOOL CATALOG:\n" + json.dumps(tools, ensure_ascii=False)[:12000]
        + "\n\nKNOWLEDGE BASES:\n" + json.dumps(list(knowledge.values()), ensure_ascii=False)[:4000]
        + "\n\nSKILL LIBRARY:\n" + json.dumps(list(skills.values()), ensure_ascii=False)[:4000]
    )
    response = await model.generate_structured_output(
        messages=[UserMsg(name="system_context", content=context), UserMsg(name="manager", content=description)],
        structured_model=CompositionPlan,
    )
    plan = CompositionPlan.model_validate(response.content)
    if plan.mode == "single":
        plan.agents = plan.agents[:1]
    return plan


__all__ = [
    "CompositionPlan",
    "CopilotReply",
    "apply_bindings",
    "copilot_turn",
    "draft_spec",
    "ensure_spec",
    "knowledge_catalog",
    "plan_composition",
    "skill_catalog",
    "last_test_for",
    "materialize",
    "published_spec",
    "record_test_run",
    "runtime_prompt",
    "set_draft",
    "tool_catalog",
    "tool_runner",
]
