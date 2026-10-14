"""Agent Studio: drafts, versions, publishing and the Builder copilot.

One place owns the lifecycle of a business agent's :class:`AgentSpec`:

* a draft is edited by the form, the copilot or self-improvement;
* publishing renders the prompt from the spec, applies the tool and
  knowledge bindings, and appends an immutable version;
* rollback republishes an older version as a new version (history is never
  rewritten).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..._logging import logger
from ...mcp import MCPClient
from ...message import TextBlock, UserMsg
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

MAX_VERSIONS = 50


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
    meta = dict(record.data.draft_meta or {})
    meta["last_test"] = report
    record.data.draft_meta = meta


def last_test_for(record: AgentRecord, spec: AgentSpec) -> dict | None:
    report = (record.data.draft_meta or {}).get("last_test")
    if report and report.get("spec_hash") == spec_hash(spec):
        return report
    return None


def pinned_view(record: AgentRecord, version: int) -> AgentRecord:
    """The agent as it was published in ``version`` (for a running ticket).

    Returns the record unchanged when that version is unknown (e.g. trimmed
    from history), so a ticket never fails because of pinning.
    """

    stored = next((v for v in record.data.versions if v.get("version") == version), None)
    if stored is None or version == record.data.published_version:
        return record
    view = record.model_copy(deep=True)
    view.data.system_prompt = stored.get("system_prompt") or view.data.system_prompt
    if stored.get("spec"):
        view.data.spec = stored["spec"]
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
) -> int:
    """Make ``spec`` the served version of ``record``; return its number."""

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
    if evaluation is not None:
        record.data.evaluation = {
            "passed": evaluation.get("publishable", False),
            "score": evaluation.get("pass_rate", 0.0),
            "total": evaluation.get("total", 0),
            "spec_hash": evaluation.get("spec_hash"),
        }
    record.data.versions = [
        *record.data.versions,
        {
            "version": version,
            "spec": record.data.spec,
            "system_prompt": prompt,
            "author": author,
            "note": note[:1000],
            "created_at": _now(),
            "evaluation": record.data.evaluation or None,
        },
    ][-MAX_VERSIONS:]
    record.data.published_version = version
    return version


async def apply_bindings(
    storage: StorageBase,
    workspace_manager: Any,
    user_id: str,
    record: AgentRecord,
    spec: AgentSpec,
) -> None:
    """Point the agent's primary session at exactly the spec's tools/knowledge.

    Team sessions copy MCP declarations from the primary session when the
    agent is invited, so new tickets pick up the change; running tickets keep
    what they started with.
    """

    sessions = await storage.list_sessions(user_id, record.id)
    if not sessions:
        return
    primary = sessions[0]
    workspace = await workspace_manager.get_workspace(
        user_id,
        record.id,
        primary.id,
        primary.config.workspace_id,
    )
    for client in await workspace.list_mcps(agent_id=record.id, session_id=primary.id):
        await workspace.remove_mcp(client.name, agent_id=record.id, session_id=primary.id)
    for default_mcp in workspace.default_mcps:
        await workspace.remove_mcp(default_mcp.name, agent_id=record.id, session_id=primary.id)
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
        client.confirm_tools = confirm.get(mcp_id) or None
        await workspace.add_mcp(client, agent_id=record.id, session_id=primary.id)
    knowledge_ids = [item.kb_id for item in spec.knowledge]
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
            catalog[f"{record.id}:{name}"] = {
                "tool_id": f"{record.id}:{name}",
                "mcp_id": record.id,
                "mcp_name": record.client.name,
                "tool_name": name,
                "description": str(tool.get("description") or ""),
                "input_schema": tool.get("input_schema") or {},
                "read_only": bool(tool.get("read_only", False)),
            }
    return catalog


def tool_runner(storage: StorageBase, user_id: str, spec: AgentSpec):
    """Return an async callable that runs one of the spec's tools by name."""

    by_name = {tool.tool_name: tool for tool in spec.tools}

    async def run(name: str, arguments: dict) -> str:
        tool = by_name[name]
        mcp_record = await storage.get_mcp(user_id, tool.mcp_id)
        if mcp_record is None or not mcp_record.enabled:
            raise RuntimeError(f"MCP {tool.mcp_id} unavailable")
        client = MCPClient.model_validate(mcp_record.client.model_dump(mode="json"))
        try:
            if client.is_stateful:
                await client.connect()
            mcp_tool = await client.get_tool(name)
            result = await mcp_tool(**arguments)
            content = getattr(result, "content", result)
            if isinstance(content, list):
                return "\n".join(
                    block.text if isinstance(block, TextBlock) else json.dumps(
                        getattr(block, "model_dump", lambda **_: str(block))(mode="json"),
                        ensure_ascii=False,
                    )
                    for block in content
                )
            return str(content)
        finally:
            if client.is_stateful and client.is_connected:
                await client.close()

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
- When creating an agent from a description, also fill name, description,
  goal, audience and tone, and add 3-5 tests (scenario + expected behaviour)
  that cover the rules, an out-of-scope request and a case needing consent.
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


async def copilot_turn(
    *,
    model: ChatModelBase,
    spec: AgentSpec,
    message: str,
    catalog: dict[str, dict],
    knowledge: list[dict] | None = None,
) -> tuple[CopilotReply, AgentSpec, list[dict]]:
    """Interpret one manager message as a patch on ``spec``.

    Returns the reply, the patched spec and the human-readable diff. When the
    model proposes an invalid patch, the operations that fail are dropped one
    by one and reported, rather than losing the whole turn.
    """

    tools = [
        {k: v for k, v in tool.items() if k in {"tool_id", "mcp_name", "tool_name", "description", "read_only"}}
        for tool in catalog.values()
    ]
    context = (
        _COPILOT_INSTRUCTIONS
        + "\nCURRENT SPEC:\n"
        + json.dumps(spec.model_dump(mode="json"), ensure_ascii=False)
        + "\n\nTOOL CATALOG:\n"
        + json.dumps(tools, ensure_ascii=False)[:20000]
        + "\n\nKNOWLEDGE BASES:\n"
        + json.dumps(knowledge or [], ensure_ascii=False)[:4000]
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
                    "read_only": meta["read_only"],
                    **operation.value,
                    "mcp_id": meta["mcp_id"],
                    "mcp_name": meta["mcp_name"],
                    "tool_name": meta["tool_name"],
                }
    patched = spec
    rejected: list[str] = []
    for operation in operations:
        if operation.field == "tools" and operation.op == "add":
            tool_id = str((operation.value or {}).get("tool_id") or "")
            if tool_id not in catalog:
                rejected.append(f"tool {tool_id or '?'} không có trong kho tool")
                continue
        try:
            patched = apply_operations(patched, [operation], author="builder")
        except SpecPatchError as exc:
            logger.info("Copilot operation rejected: %s", exc)
            rejected.append(str(exc))
    if rejected:
        reply.assistant_message += " (Bỏ qua: " + "; ".join(rejected[:5]) + ")"
    changes = [change.model_dump(mode="json") for change in diff_specs(spec, patched)]
    return reply, patched, changes


__all__ = [
    "CopilotReply",
    "apply_bindings",
    "copilot_turn",
    "draft_spec",
    "ensure_spec",
    "last_test_for",
    "materialize",
    "published_spec",
    "record_test_run",
    "runtime_prompt",
    "set_draft",
    "tool_catalog",
    "tool_runner",
]
