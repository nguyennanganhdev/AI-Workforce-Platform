"""Agent Spec: the single structured definition of a business agent.

The management page edits it as a form, the Builder copilot edits it with
patches proposed from natural language, the self-improvement loop appends
learned rules to it, and the runtime prompt is rendered from it. Keeping one
structured source avoids the "free-text prompt blob" problem: a request such
as "never quote a price before seeing a photo" becomes one rule that can be
shown, diffed, tested, rolled back and protected from automatic edits.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from .._utils._common import _generate_id

SpecSource = Literal["manager", "builder", "agent", "template", "legacy"]


class SpecRule(BaseModel):
    id: str = Field(default_factory=_generate_id)
    text: str = Field(min_length=1, max_length=2000)
    level: Literal["must", "should"] = "must"
    source: SpecSource = "manager"
    locked: bool = False
    """A locked rule can only be changed by a person, never by the agent."""
    learned_from: str = Field(default="", max_length=500)
    """For ``source="agent"``: the ticket/evidence the lesson came from."""


class SpecEscalation(BaseModel):
    id: str = Field(default_factory=_generate_id)
    when: str = Field(min_length=1, max_length=1000)
    to: str = Field(min_length=1, max_length=300)


class SpecTool(BaseModel):
    tool_id: str = Field(min_length=1, max_length=400)
    """``<mcp_id>:<tool_name>`` as listed by the tool catalog."""
    mcp_id: str = ""
    mcp_name: str = ""
    tool_name: str = ""
    use_when: str = Field(default="", max_length=1000)
    requires_consent: bool = False
    read_only: bool = False


class SpecKnowledge(BaseModel):
    kb_id: str = Field(min_length=1, max_length=200)
    name: str = ""
    use_for: str = Field(default="", max_length=1000)


class SpecSkill(BaseModel):
    skill_id: str = Field(min_length=1, max_length=200)
    """The id of a skill in the manager's skill library."""
    name: str = ""
    use_when: str = Field(default="", max_length=1000)


class SpecCollaborator(BaseModel):
    id: str = Field(default_factory=_generate_id)
    capability: str = Field(min_length=1, max_length=300)
    ask_when: str = Field(default="", max_length=1000)


class SpecExample(BaseModel):
    id: str = Field(default_factory=_generate_id)
    user: str = Field(min_length=1, max_length=2000)
    agent: str = Field(min_length=1, max_length=4000)


class SpecTest(BaseModel):
    id: str = Field(default_factory=_generate_id)
    scenario: str = Field(min_length=1, max_length=2000)
    """What the customer says."""
    expected: str = Field(min_length=1, max_length=2000)
    """The behaviour a reviewer should see (judged by a model)."""
    must_include: list[str] = Field(default_factory=list, max_length=10)
    must_not_include: list[str] = Field(default_factory=list, max_length=10)
    expect_tool: str = Field(default="", max_length=200)
    """Tool name the agent should call for this scenario, if any."""
    safety_critical: bool = False
    """A failed consent, privacy or safety scenario always blocks publication."""


class AgentSpec(BaseModel):
    """Everything a manager decides about one business agent."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    """One or two sentences; also what the Leader reads to pick the agent."""
    audience: str = Field(default="", max_length=500)
    language: Literal["auto", "vi", "en"] = "auto"
    tone: str = Field(default="", max_length=300)
    goal: str = Field(default="", max_length=4000)
    scope_in: list[str] = Field(default_factory=list, max_length=30)
    scope_out: list[str] = Field(default_factory=list, max_length=30)
    rules: list[SpecRule] = Field(default_factory=list, max_length=80)
    escalation: list[SpecEscalation] = Field(default_factory=list, max_length=30)
    tools: list[SpecTool] = Field(default_factory=list, max_length=60)
    knowledge: list[SpecKnowledge] = Field(default_factory=list, max_length=20)
    skills: list[SpecSkill] = Field(default_factory=list, max_length=20)
    collaborates: list[SpecCollaborator] = Field(default_factory=list, max_length=20)
    examples: list[SpecExample] = Field(default_factory=list, max_length=20)
    tests: list[SpecTest] = Field(default_factory=list, max_length=30)
    extra_instructions: str = Field(default="", max_length=20000)
    """Free text a manager adds below the structured sections."""
    prompt_override: str | None = Field(default=None, max_length=30000)
    """When set, replaces the rendered sections (manager edits the prompt
    directly). Learned rules are still appended so self-improvement keeps
    working; the platform evidence policy is always appended by the runtime."""
    model_tier: Literal["standard", "strong"] = "standard"
    memory_enabled: bool = True
    self_improve: bool = True


# ---------------------------------------------------------------- rendering


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item.strip())


def render_prompt(spec: AgentSpec) -> str:
    """Render the authored part of the runtime system prompt from a spec."""

    learned = [rule for rule in spec.rules if rule.source == "agent"]
    if spec.prompt_override and spec.prompt_override.strip():
        body = spec.prompt_override.strip()
    else:
        sections: list[str] = [f"You are {spec.name}."]
        if spec.description:
            sections[0] += " " + spec.description.strip()
        profile = []
        if spec.audience:
            profile.append(f"You serve: {spec.audience.strip()}.")
        language = {
            "auto": "the language of the latest message",
            "vi": "Vietnamese unless the latest message is in another language",
            "en": "English unless the latest message is in another language",
        }[spec.language]
        profile.append(f"Answer in {language}.")
        if spec.tone:
            profile.append(f"Tone: {spec.tone.strip()}.")
        sections.append(" ".join(profile))
        if spec.goal:
            sections.append("GOAL\n" + spec.goal.strip())
        if spec.scope_in:
            sections.append("IN SCOPE\n" + _bullets(spec.scope_in))
        if spec.scope_out:
            sections.append(
                "OUT OF SCOPE (say so politely and point to the right channel)\n"
                + _bullets(spec.scope_out),
            )
        manual = [rule for rule in spec.rules if rule.source != "agent"]
        must = [rule.text for rule in manual if rule.level == "must"]
        should = [rule.text for rule in manual if rule.level == "should"]
        if must:
            sections.append("RULES YOU MUST FOLLOW\n" + _bullets(must))
        if should:
            sections.append("PREFERRED PRACTICES\n" + _bullets(should))
        if spec.escalation:
            sections.append(
                "ESCALATE\n"
                + _bullets([f"When {item.when}: hand over to {item.to}." for item in spec.escalation]),
            )
        if spec.tools:
            lines = []
            for tool in spec.tools:
                line = tool.tool_name or tool.tool_id
                if tool.use_when:
                    line += f": use when {tool.use_when}"
                if tool.requires_consent:
                    line += " (only after the customer explicitly agrees to this exact action)"
                lines.append(line)
            sections.append("TOOLS\n" + _bullets(lines))
        if spec.knowledge:
            sections.append(
                "KNOWLEDGE\n"
                + _bullets(
                    [
                        f"{item.name or item.kb_id}"
                        + (f": use for {item.use_for}" if item.use_for else "")
                        for item in spec.knowledge
                    ],
                ),
            )
        if spec.skills:
            sections.append(
                "SKILLS\n"
                + _bullets(
                    [
                        f"{item.name or item.skill_id}"
                        + (f": use when {item.use_when}" if item.use_when else "")
                        for item in spec.skills
                    ],
                ),
            )
        if spec.collaborates:
            sections.append(
                "TEAMMATES TO ASK\n"
                + _bullets(
                    [
                        f"the {item.capability} specialist"
                        + (f" when {item.ask_when}" if item.ask_when else "")
                        for item in spec.collaborates
                    ],
                ),
            )
        if spec.examples:
            sections.append(
                "EXAMPLES\n"
                + "\n".join(
                    f"Customer: {item.user}\nYou: {item.agent}" for item in spec.examples
                ),
            )
        if spec.extra_instructions.strip():
            sections.append(spec.extra_instructions.strip())
        body = "\n\n".join(sections)
    if learned:
        body += (
            "\n\nLESSONS FROM PAST VERIFIED CASES (follow unless a rule above "
            "says otherwise)\n" + _bullets([rule.text for rule in learned])
        )
    return body


def tool_bindings(spec: AgentSpec) -> list[dict[str, Any]]:
    """Runtime tool bindings (the shape Builder already stores)."""

    return [
        {
            "id": tool.tool_id,
            "mcp_id": tool.mcp_id,
            "mcp_name": tool.mcp_name,
            "tool_name": tool.tool_name,
            "description": tool.use_when,
            "requires_consent": tool.requires_consent,
        }
        for tool in spec.tools
    ]


def spec_from_legacy(
    *,
    name: str,
    description: str,
    system_prompt: str,
    bindings: list[dict],
    policy: str,
) -> AgentSpec:
    """Wrap an agent created before Agent Spec without changing its behaviour.

    The authored prompt becomes ``prompt_override`` so the rendered prompt is
    identical; the runtime policy suffix is stripped (it is re-appended).
    """

    authored = system_prompt
    if policy and policy in authored:
        authored = authored.replace(policy, "").rstrip()
    return AgentSpec(
        name=name[:100] or "Agent",
        description=description[:1000],
        prompt_override=authored or None,
        tools=[
            SpecTool(
                tool_id=str(binding.get("id") or f"{binding.get('mcp_id')}:{binding.get('tool_name')}"),
                mcp_id=str(binding.get("mcp_id") or ""),
                mcp_name=str(binding.get("mcp_name") or ""),
                tool_name=str(binding.get("tool_name") or ""),
                use_when=str(binding.get("description") or "")[:1000],
                requires_consent=bool(binding.get("requires_consent", False)),
            )
            for binding in bindings
        ],
    )


# ---------------------------------------------------------------- diff / patch

_LIST_FIELDS = {
    "scope_in",
    "scope_out",
    "rules",
    "escalation",
    "tools",
    "knowledge",
    "skills",
    "collaborates",
    "examples",
    "tests",
}


class SpecChange(BaseModel):
    field: str
    action: Literal["changed", "added", "removed"]
    before: Any = None
    after: Any = None


def _item_key(field: str, item: Any) -> str:
    if isinstance(item, dict):
        for key in ("id", "tool_id", "kb_id", "skill_id"):
            if item.get(key):
                return str(item[key])
        return json.dumps(item, sort_keys=True, ensure_ascii=False)
    return str(item)


def diff_specs(before: AgentSpec | None, after: AgentSpec) -> list[SpecChange]:
    """Field-level differences, list items matched by id."""

    old = before.model_dump(mode="json") if before else {}
    new = after.model_dump(mode="json")
    changes: list[SpecChange] = []
    for field, value in new.items():
        previous = old.get(field)
        if field in _LIST_FIELDS:
            before_items = {_item_key(field, item): item for item in previous or []}
            after_items = {_item_key(field, item): item for item in value or []}
            for key, item in after_items.items():
                if key not in before_items:
                    changes.append(SpecChange(field=field, action="added", after=item))
                elif before_items[key] != item:
                    changes.append(
                        SpecChange(field=field, action="changed", before=before_items[key], after=item),
                    )
            for key, item in before_items.items():
                if key not in after_items:
                    changes.append(SpecChange(field=field, action="removed", before=item))
        elif previous != value and not (previous in (None, "") and value in (None, "")):
            changes.append(SpecChange(field=field, action="changed", before=previous, after=value))
    return changes


class SpecOperation(BaseModel):
    """One edit proposed by the copilot (or sent by the form)."""

    op: Literal["set", "add", "remove", "update"]
    field: str
    value: Any = None
    """set: new field value. add: the new item. update: the replacement item."""
    item_id: str | None = None
    """remove/update: the id (or text for string lists) of the item."""


class SpecPatchError(ValueError):
    """A patch could not be applied; nothing was changed."""


def apply_operations(
    spec: AgentSpec,
    operations: list[SpecOperation],
    *,
    author: SpecSource,
) -> AgentSpec:
    """Apply operations atomically; locked rules are protected from agents."""

    data = spec.model_dump(mode="json")
    for operation in operations:
        if operation.field not in AgentSpec.model_fields:
            raise SpecPatchError(f"Unknown field {operation.field!r}")
        if operation.op == "set":
            if operation.field in _LIST_FIELDS and not isinstance(operation.value, list):
                raise SpecPatchError(f"{operation.field} needs a list")
            data[operation.field] = operation.value
            continue
        if operation.field not in _LIST_FIELDS:
            raise SpecPatchError(f"{operation.op} works only on list fields")
        items = list(data.get(operation.field) or [])
        if operation.op == "add":
            value = operation.value
            if isinstance(value, dict) and operation.field == "rules":
                value = {**value, "source": value.get("source") or author}
            items.append(value)
        else:
            index = next(
                (
                    i
                    for i, item in enumerate(items)
                    if _item_key(operation.field, item) == operation.item_id
                    or (isinstance(item, str) and item == operation.item_id)
                    or (isinstance(item, dict) and item.get("text") == operation.item_id)
                ),
                None,
            )
            if index is None:
                raise SpecPatchError(f"No {operation.field} item {operation.item_id!r}")
            target = items[index]
            if (
                operation.field == "rules"
                and author == "agent"
                and isinstance(target, dict)
                and (target.get("locked") or target.get("source") != "agent")
            ):
                raise SpecPatchError("Agents may only change rules they learned")
            if operation.op == "remove":
                items.pop(index)
            else:
                replacement = operation.value
                if isinstance(target, dict) and isinstance(replacement, dict):
                    replacement = {**target, **replacement}
                items[index] = replacement
        data[operation.field] = items
    try:
        return AgentSpec.model_validate(data)
    except ValidationError as exc:
        raise SpecPatchError(str(exc)) from exc


def spec_hash(spec: AgentSpec) -> str:
    """Stable hash of a spec, used to tie a test run to the exact draft."""

    import hashlib

    canonical = json.dumps(spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "AgentSpec",
    "SpecChange",
    "SpecCollaborator",
    "SpecEscalation",
    "SpecExample",
    "SpecKnowledge",
    "SpecOperation",
    "SpecPatchError",
    "SpecRule",
    "SpecSkill",
    "SpecTest",
    "SpecTool",
    "apply_operations",
    "diff_specs",
    "render_prompt",
    "spec_from_legacy",
    "spec_hash",
    "tool_bindings",
]
