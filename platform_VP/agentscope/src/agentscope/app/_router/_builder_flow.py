"""Builder review, draft reservation, evaluation and versioned publication."""

from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager

from fastapi import HTTPException
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ..._utils._common import _generate_id
from ...message import AssistantMsg
from .._agent_spec import (
    AgentSpec,
    SpecCollaborator,
    SpecKnowledge,
    SpecSkill,
    SpecTest,
    SpecTool,
    diff_specs,
    render_prompt,
    spec_hash,
)
from .._service._agent_studio import (
    apply_bindings,
    draft_spec,
    ensure_spec,
    materialize,
    record_test_run,
    set_draft,
)
from .._service._builder_decisions import (
    BuilderClassifier,
    BuilderScope,
    ClassifierStatus,
    catalog_hash,
    decide_identities,
    digest,
    failure_reason,
    scoped_agents,
    select_resources,
)
from .._service._publish_gate import publish_blocker
from ..storage import AgentData, AgentRecord, InviteConfig


def resources(tools, knowledge, skills):
    return {
        "tools": {t.id: t.model_dump(mode="json") for t in tools},
        "knowledge": knowledge,
        "skills": skills,
    }


def _shared_read(tool) -> bool:
    """Sharing read context does not duplicate ownership of an operation."""
    return tool.read_only is True and tool.requires_consent is False


def _combine_updates(plans, decisions, records):
    """One reviewed update per existing ID, preserving every requested need."""
    grouped = {}
    combined, choices = [], []
    for plan, decision in zip(plans, decisions):
        target = decision.agent_id if decision.action in ("reuse", "resume", "revise") else None
        if not target or target not in grouped:
            if target:
                grouped[target] = len(combined)
            combined.append(plan.model_copy(deep=True))
            choices.append(decision.model_copy(deep=True))
            continue
        index = grouped[target]
        base = combined[index]
        payload = base.model_dump()
        record = next(r for r in records if r.id == target)
        payload["name"] = record.data.name
        payload["objective"] = "\n\n".join(dict.fromkeys([base.objective, plan.objective]))
        for field in ("suggested_tool_ids", "tool_requirements", "knowledge_requirements"):
            payload[field] = list(dict.fromkeys([*getattr(base, field), *getattr(plan, field)]))
        payload["knowledge_required"] = base.knowledge_required or plan.knowledge_required
        try:
            combined[index] = type(base).model_validate(payload)
        except ValidationError:
            # Never truncate a business constraint to fit the merged plan.
            choices[index].action = "clarify"
            choices[index].reason = "Yêu cầu gộp vượt giới hạn mô tả; cần rút gọn nội dung nhưng giữ đủ nghiệp vụ."
            combined.append(plan.model_copy(deep=True))
            choices.append(decision.model_copy(deep=True))
            continue
        choice = choices[index]
        if choice.action != "clarify":
            if choice.action != "reuse" or decision.action != "reuse":
                choice.action = "resume" if record.data.draft_spec or record.data.lifecycle_state == "draft" else "revise"
            choice.reason = "Gộp các phần việc đã xác nhận cùng nghiệp vụ vào một agent; giữ đầy đủ yêu cầu, không tạo bản sao."
    return combined, choices


def _delegate_owned_operations(views, records):
    """Keep existing write ownership; route a new need through its specialist."""
    from ._workforce_console import BuilderDelegation

    inherited = {}
    for record in records:
        spec = record.data.draft_spec or record.data.spec or {}
        inherited[record.id] = {t["tool_id"] for t in spec.get("tools", [])}
    for tool_id in {t.id for v in views for t in v.suggested_tools if not _shared_read(t)}:
        users = [v for v in views if any(t.id == tool_id for t in v.suggested_tools)]
        owners = [v for v in users if tool_id in inherited.get(v.decision.agent_id, set())]
        if len(users) < 2 or len(owners) != 1:
            continue
        owner = owners[0]
        for view in users:
            if view is owner:
                continue
            tool = next(t for t in view.suggested_tools if t.id == tool_id)
            view.suggested_tools = [t for t in view.suggested_tools if t.id != tool_id]
            view.delegated_tools.append(BuilderDelegation(
                agent_id=owner.decision.agent_id, agent_name=owner.name,
                tool_id=tool.id, tool_name=tool.tool_name,
            ))


@asynccontextmanager
async def catalog_guard(storage, user_id):
    token = _generate_id()
    try:
        acquired = await storage.acquire_builder_catalog(user_id, token)
    except (NotImplementedError, AttributeError) as exc:
        raise HTTPException(
            503, "Storage chưa hỗ trợ giữ catalog an toàn; chưa ghi agent."
        ) from exc
    if acquired is not True:
        raise HTTPException(
            409,
            "Catalog đang được cập nhật. Hãy tải lại; nếu worker bị dừng cần kiểm tra reservation.",
        )
    try:
        yield
    finally:
        await storage.release_builder_catalog(user_id, token)


async def plan_proposal(
    outline,
    transcript,
    tools,
    knowledge,
    skills,
    model,
    access,
    storage,
    user_id,
    conversation_id,
    config,
    scope,
    revision,
    checkpoint=None,
):
    from . import _workforce_console as c

    scope = scope or BuilderScope(owner_id=user_id)
    records = scoped_agents(await storage.list_agents(user_id), scope)
    catalog = resources(tools, knowledge, skills)
    classifier = BuilderClassifier(access, storage, scope, conversation_id)
    if checkpoint:
        snapshot = digest(
            {
                "agents": catalog_hash(records, scope),
                "resources": catalog,
                "scope": scope.model_dump(),
            }
        )
        if checkpoint.value.get("snapshot") != snapshot:
            checkpoint.value.update(snapshot=snapshot, batches={}, splits=[])
        classifier.checkpoint = checkpoint
        classifier.status = ClassifierStatus.model_validate(
            checkpoint.value.get("classifier_status", {})
        )
        classifier.status.model = os.getenv("WORKFORCE_JEV_MODEL", "jev-1.13.0").strip()
        classifier.status.run_id = checkpoint.value["run_id"]
        classifier.status.state = "not_needed"
        classifier.status.reason = ""
        await checkpoint.save()
    try:
        decisions = await decide_identities(
            outline.agents, records, classifier, transcript
        )
        plans, decisions = _combine_updates(outline.agents, decisions, records)
        views = []
        claimed = set()
        pending = []
        for i, (plan, decision) in enumerate(zip(plans, decisions)):
            view = c.PlannedAgentView(
                name=plan.name,
                objective=plan.objective,
                decision=decision,
                tool_requirements=plan.tool_requirements,
                knowledge_requirements=plan.knowledge_requirements,
                knowledge_required=plan.knowledge_required,
            )
            views.append(view)
            if decision.action == "reuse":
                record = next(r for r in records if r.id == decision.agent_id)
                spec = AgentSpec.model_validate(record.data.spec)
                ids = [t.tool_id for t in spec.tools]
                if (
                    not set(ids) <= catalog["tools"].keys()
                    or claimed.intersection(t.tool_id for t in spec.tools if not _shared_read(t))
                    or not {k.kb_id for k in spec.knowledge} <= knowledge.keys()
                    or not {s.skill_id for s in spec.skills} <= skills.keys()
                ):
                    decision.action = "repair"
                    decision.reason = "Tài nguyên của agent dùng lại không còn khả dụng hoặc bị trùng trong plan."
                else:
                    if any(
                        t.requires_consent
                        != catalog["tools"][t.tool_id]["requires_consent"]
                        or t.read_only != catalog["tools"][t.tool_id]["read_only"]
                        for t in spec.tools
                    ):
                        decision.action = "revise"
                        decision.reason = (
                            "Chính sách tool đã đổi; kiểm thử phiên bản mới cùng agent."
                        )
                        pending.append((i, plan))
                        continue
                    claimed.update(t.tool_id for t in spec.tools if not _shared_read(t))
                    view.suggested_tools = [
                        c.BuilderTool.model_validate(catalog["tools"][rid])
                        for rid in ids
                    ]
                    view.knowledge = [knowledge[k.kb_id] for k in spec.knowledge]
                    view.library_skills = [skills[s.skill_id] for s in spec.skills]
            elif decision.action in ("create", "resume", "revise"):
                pending.append((i, plan))
        source = "none"
        if pending:
            available = {
                **catalog,
                "tools": {
                    rid: t for rid, t in catalog["tools"].items() if rid not in claimed
                },
            }
            try:
                selection = await select_resources(
                    [p for _, p in pending], available, classifier
                )
                source = "jev" if classifier.status.calls else "none"
            except Exception as exc:  # noqa: BLE001 - keep the verified identity, pause resource selection
                classifier.status.state = "unavailable"
                classifier.status.reason = failure_reason(
                    exc, classifier.status.http_status
                )
                classifier.status.stages.setdefault("builder_resources", {}).update(
                    state="error", reason=classifier.status.reason
                )
                source = "none"
                selection = [
                    {
                        "tools": [],
                        "knowledge": [],
                        "skills": [],
                        "missing_tools": list(p.tool_requirements),
                        "missing_knowledge": list(p.knowledge_requirements),
                    }
                    for _, p in pending
                ]
            for (i, _), selected in zip(pending, selection):
                view = views[i]
                view.suggested_tools = [
                    c.BuilderTool.model_validate(catalog["tools"][rid])
                    for rid in selected["tools"]
                ]
                view.knowledge = [knowledge[rid] for rid in selected["knowledge"]]
                view.library_skills = [skills[rid] for rid in selected["skills"]]
                view.missing_tools, view.missing_knowledge = (
                    selected["missing_tools"],
                    selected["missing_knowledge"],
                )
                # An upgrade must retain the existing tool/knowledge/skill contract.
                if view.decision.agent_id:
                    record = next(r for r in records if r.id == view.decision.agent_id)
                    base = (
                        AgentSpec.model_validate(
                            record.data.draft_spec or record.data.spec
                        )
                        if (record.data.draft_spec or record.data.spec)
                        else None
                    )
                    if base:
                        for kind, ids in (
                            ("tools", [t.tool_id for t in base.tools]),
                            ("knowledge", [k.kb_id for k in base.knowledge]),
                            ("skills", [s.skill_id for s in base.skills]),
                        ):
                            if not set(ids) <= catalog[kind].keys():
                                view.decision.action = "repair"
                                view.decision.reason = "Tài nguyên cũ bị thu hồi; sửa agent hiện có trước khi nâng cấp."
                                continue
                            attr = {
                                "tools": "suggested_tools",
                                "knowledge": "knowledge",
                                "skills": "library_skills",
                            }[kind]
                            current = getattr(view, attr)
                            id_key = {"knowledge": "kb_id", "skills": "skill_id"}.get(
                                kind
                            )
                            present = (
                                {t.id for t in current}
                                if kind == "tools"
                                else {t[id_key] for t in current}
                            )
                            current.extend(
                                c.BuilderTool.model_validate(catalog[kind][rid])
                                if kind == "tools"
                                else catalog[kind][rid]
                                for rid in ids
                                if rid not in present
                            )
        _delegate_owned_operations(views, records)
        all_tools = [t.id for view in views for t in view.suggested_tools if not _shared_read(t)]
        targets = [v.decision.agent_id for v in views if v.decision.agent_id]
        if len(all_tools) != len(set(all_tools)) or len(targets) != len(set(targets)):
            for view in views:
                view.decision.action = "clarify"
                view.decision.reason = "Các vai trò còn dùng chung tool hoặc trỏ cùng agent; hãy gộp/làm rõ ranh giới nghiệp vụ."
        blocked = classifier.status.state == "unavailable" or any(
            v.decision.action in ("clarify", "repair")
            or v.missing_tools
            or (v.knowledge_required and v.missing_knowledge)
            for v in views
        )
        return c.ProposalView(
            conversation_id=conversation_id,
            proposal_id=checkpoint.value["run_id"] if checkpoint else _generate_id(),
            revision=revision,
            status="needs_input",
            assistant_message=(
                f"Đã gộp {len(outline.agents)} phần việc thành {len(plans)} agent theo nghiệp vụ đã có; giữ đầy đủ yêu cầu và cùng ID. Hãy xem phương án trước khi duyệt."
                if len(plans) < len(outline.agents)
                else outline.assistant_message
                or "Hãy xem phương án dùng lại, cập nhật và tài nguyên trước khi chốt."
            ),
            clarification_question=(
                "Đây là lỗi kiểm tra hệ thống JEV; hãy giữ nguyên mô tả và chọn Thử lại bước kiểm tra sau khi khắc phục."
                if classifier.status.state == "unavailable"
                else "Hãy bổ sung hoặc làm rõ các mục đang bị chặn rồi lập lại phương án."
            )
            if blocked
            else None,
            planned_agents=views,
            chat_model_config=config,
            fixed_config=c._fixed_config(),
            scope=scope,
            agent_catalog_hash=catalog_hash(records, scope),
            resource_catalog=catalog,
            classifier_status=classifier.status,
            resource_selection=source,
        )
    finally:
        if checkpoint:
            await checkpoint.status(classifier.status)
        await classifier.close()


async def check_plan(
    proposal, revision, tools, knowledge, skills, storage, user_id, scope
):
    if (
        proposal is None
        or proposal.scope != scope
        or proposal.scope.owner_id != user_id
        or proposal.revision != revision
        or not proposal.planned_agents
        or proposal.classifier_status.state == "unavailable"
        or not proposal.agent_catalog_hash
    ):
        raise HTTPException(
            409,
            "Phương án đã thay đổi hoặc chưa kiểm tra trùng; hãy tải lại và lập phương án.",
        )
    if digest(resources(tools, knowledge, skills)) != digest(proposal.resource_catalog):
        raise HTTPException(
            409, "Catalog tool/KB/skill đã thay đổi; hãy lập và duyệt lại phương án."
        )
    if (
        catalog_hash(await storage.list_agents(user_id), scope)
        != proposal.agent_catalog_hash
    ):
        raise HTTPException(
            409, "Catalog agent đã thay đổi; kiểm tra trùng lại trước khi tiếp tục."
        )
    claimed = set()
    for plan in proposal.planned_agents:
        if (
            plan.decision.action in ("clarify", "repair")
            or plan.missing_tools
            or (plan.knowledge_required and plan.missing_knowledge)
        ):
            raise HTTPException(
                409,
                plan.decision.reason + " Phương án còn thiếu năng lực hoặc cần làm rõ.",
            )
        for tool in plan.suggested_tools:
            if (tool.id in claimed and not _shared_read(tool)) or proposal.resource_catalog["tools"].get(
                tool.id
            ) != tool.model_dump(mode="json"):
                raise HTTPException(409, "Tool bị trùng hoặc không còn đúng catalog.")
            try:
                Draft202012Validator.check_schema(tool.input_schema)
            except Exception as exc:
                raise HTTPException(409, "Tool có schema không hợp lệ.") from exc
            if not _shared_read(tool):
                claimed.add(tool.id)
        for delegation in plan.delegated_tools:
            owner = next((p for p in proposal.planned_agents if p.decision.agent_id == delegation.agent_id), None)
            if owner is None or owner is plan or not any(
                t.id == delegation.tool_id and t.tool_name == delegation.tool_name
                for t in owner.suggested_tools
            ):
                raise HTTPException(409, "Agent nhận thao tác phối hợp không còn sở hữu tool; kiểm tra lại phương án.")


async def generate_proposal(
    previous, body, transcript, tools, knowledge, skills, model, storage, user_id, scope
):
    import json

    from . import _workforce_console as c

    if (
        previous is None
        or not body.expected_proposal_id
        or body.expected_proposal_id != previous.proposal_id
    ):
        raise HTTPException(
            409, "Phương án đã được thay thế; hãy tải lại trước khi duyệt."
        )
    if previous is not None and (previous.status != "needs_input" or previous.agents):
        raise HTTPException(
            409,
            "Cấu hình đã được sinh; hãy đánh giá bản hiện tại hoặc lập phương án mới.",
        )
    await check_plan(
        previous,
        body.expected_revision,
        tools,
        knowledge,
        skills,
        storage,
        user_id,
        scope,
    )
    new = [p for p in previous.planned_agents if p.decision.action != "reuse"]
    bases = {}
    for plan in new:
        if plan.decision.agent_id:
            record = await storage.get_agent(user_id, plan.decision.agent_id)
            ensure_spec(record)
            bases[plan.name] = draft_spec(record)
    generation = c.BuilderGeneration()
    if new:
        approved = [p.model_dump() for p in new]
        generation, _, _ = await c._generate(
            transcript,
            tools,
            model,
            body.chat_model_config,
            c._response_language(transcript),
            "\nAUTHORITATIVE APPROVED PLAN: "
            + json.dumps(approved, ensure_ascii=False)
            + "\nEXISTING SPECS TO PRESERVE: "
            + json.dumps(
                {n: s.model_dump() for n, s in bases.items()}, ensure_ascii=False
            )
            + "\nReturn exactly these names. Resources are locked: copy tool/knowledge/skill IDs from the approved plan. "
            "Do not generate a skill when library_skills covers the workflow. Preserve all existing constraints and rules. "
            "Missing optional knowledge must be requested from the user when needed; never invent its facts or policies. "
            "Generate at least three tests including a mandatory safety/consent test.",
        )
        if len(generation.agents) != len(new) or {
            a.name for a in generation.agents
        } != {p.name for p in new}:
            raise HTTPException(502, "Model đã đổi ranh giới agent; chưa lưu bản nháp.")
    by_name = {a.name: a for a in generation.agents}
    items = []
    for plan in previous.planned_agents:
        decision = plan.decision
        if decision.action == "reuse":
            record = await storage.get_agent(user_id, decision.agent_id)
            spec = AgentSpec.model_validate(record.data.spec)
            items.append(
                c.ProposedAgentView(
                    name=record.data.name,
                    objective=plan.objective,
                    system_prompt=record.data.system_prompt,
                    selected_tools=plan.suggested_tools,
                    skill_name="",
                    skill_markdown=record.data.generated_skill,
                    knowledge=plan.knowledge,
                    library_skills=plan.library_skills,
                    spec=record.data.spec,
                    evaluation={
                        "passed": True,
                        "checks": {"published_spec": True},
                        "model_report": record.data.evaluation,
                    },
                    reuse_agent_id=record.id,
                    reuse_agent_name=record.data.name,
                    action="reuse",
                    target_agent_id=record.id,
                    target_revision=record.storage_revision,
                )
            )
            continue
        generated = by_name[plan.name]
        # Resources and execution mode are assigned by code, never by generation.
        generated.selected_tool_ids = [t.id for t in plan.suggested_tools]
        generated.knowledge_ids = [k["kb_id"] for k in plan.knowledge]
        generated.library_skill_ids = [s["skill_id"] for s in plan.library_skills]
        generated.needs_tools = bool(plan.tool_requirements)
        if plan.library_skills:
            generated.skill_name = generated.skill_markdown = ""
        skill = (
            c._normalise_skill(generated) if generated.skill_markdown.strip() else ""
        )
        base = bases.get(plan.name)
        spec = base.model_copy(deep=True) if base else AgentSpec(name=plan.name)
        spec.goal, spec.description = plan.objective, plan.objective[:1000]
        spec.prompt_override = generated.system_prompt
        for delegation in plan.delegated_tools:
            spec.collaborates.append(SpecCollaborator(
                capability=f"{delegation.agent_name}: {delegation.tool_name}",
                ask_when=f"Cần thao tác {delegation.tool_name}; nhờ Leader/chuyên viên qua TeamSay. Giữ nguyên quyền/đồng ý của tool, chỉ báo hoàn tất khi có kết quả xác minh.",
            ))
            spec.prompt_override += (
                f"\nThao tác {delegation.tool_name} do chuyên viên {delegation.agent_name} sở hữu. "
                "Phối hợp qua TeamSay/Leader khi cần; không tự gọi tool này hoặc khẳng định đã thực hiện nếu chưa có kết quả xác minh."
            )
        spec.tools = [
            SpecTool(
                tool_id=t.id,
                mcp_id=t.mcp_id,
                mcp_name=t.mcp_name,
                tool_name=t.tool_name,
                requires_consent=t.requires_consent,
                read_only=t.read_only,
            )
            for t in plan.suggested_tools
        ]
        spec.knowledge = [
            SpecKnowledge(kb_id=k["kb_id"], name=k["name"]) for k in plan.knowledge
        ]
        spec.skills = [
            SpecSkill(skill_id=s["skill_id"], name=s["name"])
            for s in plan.library_skills
        ]
        # Pin the library SKILL.md bodies into the evaluated artifact. The
        # evaluator has no workspace skill loader; names alone are insufficient.
        old_extra = re.sub(
            r"\n\nBUILDER_LIBRARY_SNAPSHOTS\n[^\n]*\nEND_BUILDER_LIBRARY_SNAPSHOTS",
            "",
            base.extra_instructions if base else "",
        )
        spec.extra_instructions = "\n\n".join(
            dict.fromkeys(value for value in (old_extra, skill) if value)
        )
        if plan.library_skills:
            snapshot = json.dumps(
                plan.library_skills, ensure_ascii=False, sort_keys=True
            )
            spec.extra_instructions += (
                "\n\nBUILDER_LIBRARY_SNAPSHOTS\n"
                + snapshot
                + "\nEND_BUILDER_LIBRARY_SNAPSHOTS"
            )
        if base:
            # A prompt override must not hide structured audience/scope/rules,
            # escalation or examples retained from the existing AgentSpec.
            binding_spec = spec.model_copy(
                update={"prompt_override": None, "extra_instructions": ""}
            )
            spec.prompt_override += "\n\nBinding AgentSpec:\n" + render_prompt(
                binding_spec
            )
        if spec.extra_instructions:
            spec.prompt_override += "\n\n" + spec.extra_instructions
        # Keep previous regression cases when extending the same identity.
        spec.tests = list(spec.tests) + [
            SpecTest(**t.model_dump()) for t in generated.tests
        ]
        try:
            spec = AgentSpec.model_validate(spec.model_dump())
        except ValueError as exc:
            raise HTTPException(
                409,
                "Cấu hình nâng cấp vượt giới hạn AgentSpec; hãy thu hẹp thay đổi hoặc chỉnh bản nháp.",
            ) from exc
        checks = c._agent_checks(
            generated, plan.suggested_tools, [], [], plan.library_skills, []
        )
        items.append(
            c.ProposedAgentView(
                name=spec.name,
                objective=plan.objective,
                system_prompt=generated.system_prompt,
                selected_tools=plan.suggested_tools,
                skill_name=c._slug(generated.skill_name) if skill else "",
                skill_markdown=skill,
                knowledge=plan.knowledge,
                library_skills=plan.library_skills,
                tests=[t.model_dump() for t in spec.tests],
                evaluation={
                    "passed": False,
                    "checks": checks,
                    "publish_blocker": "Xem khác biệt, lưu nháp và chạy eval trước khi phát hành.",
                },
                spec=spec.model_dump(mode="json"),
                action=decision.action,
                target_agent_id=decision.agent_id,
                target_revision=decision.expected_revision,
                diff=[
                    d.model_dump(mode="json")
                    for d in diff_specs(base or AgentSpec(name=spec.name), spec)
                ],
            )
        )
    return previous.model_copy(
        update={
            "proposal_id": _generate_id(),
            "revision": previous.revision + 1,
            "agents": items,
            "status": "ready" if not new else "needs_input",
            "assistant_message": "Hãy xem khác biệt trước khi lưu nháp và chạy eval."
            if new
            else "Dùng lại các agent đã kiểm thử; không tạo agent mới.",
        }
    )


async def current_resources(storage, user_id):
    from . import _workforce_console as c

    tools = await c._catalog(storage, user_id)
    knowledge, skills = await c._library(storage, user_id)
    return tools, knowledge, skills


async def save_drafts(proposal, storage, user_id):
    from . import _workforce_console as c

    await check_plan(
        proposal,
        proposal.revision,
        *await current_resources(storage, user_id),
        storage,
        user_id,
        proposal.scope,
    )
    for item in proposal.agents:
        if item.action == "reuse":
            continue
        record = (
            await storage.get_agent(user_id, item.target_agent_id)
            if item.target_agent_id
            else None
        )
        if record is None:
            record = AgentRecord(
                user_id=user_id,
                data=AgentData(
                    name=item.name,
                    context_config=c._FIXED_CONTEXT.model_copy(deep=True),
                    react_config=c._FIXED_REACT.model_copy(deep=True),
                    system_role="business",
                    lifecycle_state="draft",
                    builder_scope=proposal.scope.model_dump(),
                    invite_config=InviteConfig(invitable=False),
                    build_description=item.objective,
                ),
            )
        elif record.storage_revision != item.target_revision:
            raise HTTPException(409, "Bản nháp đã được sửa ở nơi khác; hãy tải lại.")
        record.data.builder_scope = proposal.scope.model_dump()
        set_draft(
            record,
            AgentSpec.model_validate(item.spec),
            author="builder",
            note="Approved Builder diff",
        )
        await c._save_agent(storage, user_id, record)
        item.target_agent_id, item.target_revision = record.id, record.storage_revision
    proposal.agent_catalog_hash = catalog_hash(
        await storage.list_agents(user_id), proposal.scope
    )


async def evaluate_proposal(proposal, storage, user_id, model, progress):
    from . import _workforce_console as c

    if not proposal.agents:
        raise HTTPException(409, "Chưa có cấu hình để kiểm thử.")
    async with catalog_guard(storage, user_id):
        await save_drafts(proposal, storage, user_id)
        for item in proposal.agents:
            if item.action != "reuse":
                await c._evaluate_proposed_agent(
                    item, storage, user_id, model, progress
                )
                record = await storage.get_agent(user_id, item.target_agent_id)
                if record.storage_revision != item.target_revision or spec_hash(
                    draft_spec(record)
                ) != spec_hash(AgentSpec.model_validate(item.spec)):
                    raise HTTPException(
                        409,
                        "Agent thay đổi trong lúc eval; kết quả không được áp lên bản nháp mới.",
                    )
                record_test_run(record, item.evaluation["model_report"])
                await c._save_agent(storage, user_id, record)
                item.target_revision = record.storage_revision
        proposal.agent_catalog_hash = catalog_hash(
            await storage.list_agents(user_id), proposal.scope
        )
        proposal.status = (
            "ready"
            if all(i.evaluation["passed"] for i in proposal.agents)
            else "blocked"
        )


async def publish_proposal(body, request, user_id, storage, workspace_manager, scope):
    from . import _workforce_console as c
    from ._workforce_studio import _skill_installer

    async with c._proposal_locks[user_id]:
        session = await storage.get_session(
            user_id, c._BUILDER_AGENT_ID, body.conversation_id
        )
        if session is None:
            raise HTTPException(404, "Builder proposal not found")
        proposal = c._stored_proposal(
            await c._list_all_builder_messages(storage, user_id, body.conversation_id)
        )
        if proposal is None or proposal.proposal_id != body.proposal_id:
            raise HTTPException(404, "Builder proposal not found")
        # Validate reports before doing writes, including old proposals.
        for item in proposal.agents:
            blocker = (
                publish_blocker(
                    AgentSpec.model_validate(item.spec),
                    item.evaluation.get("model_report"),
                )
                if item.spec
                else "Chưa có spec được kiểm thử."
            )
            if blocker or not all(item.evaluation.get("checks", {}).values()):
                raise HTTPException(409, blocker or "Cấu hình chưa đạt.")
        async with catalog_guard(storage, user_id):
            await check_plan(
                proposal,
                body.expected_revision,
                *await current_resources(storage, user_id),
                storage,
                user_id,
                scope,
            )
            if proposal.status != "ready":
                raise HTTPException(409, "Proposal chưa đạt điều kiện phát hành.")
            records = {}
            for item in proposal.agents:
                record = (
                    await storage.get_agent(user_id, item.target_agent_id)
                    if item.target_agent_id
                    else None
                )
                if record is None or record.storage_revision != item.target_revision:
                    raise HTTPException(409, "Agent đã thay đổi hoặc chưa lưu nháp.")
                actual = (
                    record.data.spec
                    if item.action == "reuse"
                    else record.data.draft_spec
                )
                if not actual or spec_hash(
                    AgentSpec.model_validate(actual)
                ) != spec_hash(AgentSpec.model_validate(item.spec)):
                    raise HTTPException(409, "Spec không còn khớp bản đã kiểm thử.")
                if item.action == "reuse" and (
                    record.data.lifecycle_state != "published"
                    or not record.data.invite_config.invitable
                    or publish_blocker(
                        AgentSpec.model_validate(actual), record.data.evaluation
                    )
                ):
                    raise HTTPException(409, "Agent dùng lại không còn hợp lệ.")
                records[record.id] = record
            result = []
            prepared = []
            for item in proposal.agents:
                record = records[item.target_agent_id]
                if item.action == "reuse":
                    result.append(
                        c.PublishedAgent(
                            agent_id=record.id, name=record.data.name, reused=True
                        )
                    )
                    continue
                spec = AgentSpec.model_validate(item.spec)
                previous = (
                    AgentSpec.model_validate(record.data.spec)
                    if record.data.spec
                    else None
                )
                session = await c._primary_session(
                    storage, workspace_manager, user_id, record.id,
                    proposal.chat_model_config, "Builder primary session",
                )
                record = record.model_copy(deep=True)
                record.data.resource_workspace_id = "published-" + _generate_id()
                record.data.generated_skill = item.skill_markdown
                materialize(
                    record,
                    spec,
                    author="builder",
                    note="Builder reviewed diff and model evaluation",
                    evaluation=item.evaluation["model_report"],
                )
                await apply_bindings(
                    storage,
                    workspace_manager,
                    user_id,
                    record,
                    spec,
                    install_skill=_skill_installer(
                        request, storage, user_id, record.id
                    ),
                    previous=previous,
                    stage=True,
                )
                workspace = await workspace_manager.get_workspace(
                    user_id, record.id, session.id, record.data.resource_workspace_id
                )
                if item.skill_markdown.strip():
                    await workspace.add_skill_archive(
                        c._archive(item.skill_name, item.skill_markdown),
                        "tar",
                        item.skill_name,
                        agent_id=record.id,
                    )
                    from ..storage import SkillRecord
                    from hashlib import sha256
                    digest = sha256(item.skill_markdown.encode()).hexdigest()
                    candidate_name = c._slug(item.skill_name)[:50] + "-" + digest[:12]
                    if await storage.get_skill_by_name(user_id, candidate_name) is None:
                        await storage.upsert_skill(user_id, SkillRecord(
                            name=candidate_name, user_id=user_id, markdown=item.skill_markdown,
                            description=spec.description or spec.goal or spec.name,
                            version=digest[:16], review_status="candidate", enabled=False,
                            source_agent_id=record.id, source_version=record.data.published_version,
                            tags=["builder", "candidate"],
                        ))
                prepared.append(record)
                result.append(
                    c.PublishedAgent(
                        agent_id=record.id, session_id=session.id, name=record.data.name
                    )
                )
            # Prepare all resources before the durable one-shot claim. A hub
            # failure leaves every active version intact and can be retried.
            try:
                claimed = await storage.claim_builder_publish(user_id, body.conversation_id, body.proposal_id)
            except (AttributeError, NotImplementedError) as exc:
                raise HTTPException(503, "Storage chưa hỗ trợ phát hành an toàn.") from exc
            if not claimed:
                raise HTTPException(409, "Proposal đã được giữ để phát hành; kiểm tra kết quả trước khi thử lại.")
            for record in prepared:
                await c._save_agent(storage, user_id, record)
            proposal.status = "published"
            await storage.upsert_message(
                user_id,
                body.conversation_id,
                AssistantMsg(
                    name="agent_builder",
                    content="Đã phát hành phiên bản đã kiểm thử; các agent dùng lại giữ nguyên ID.",
                    structured_output={
                        "workforce_builder_proposal": proposal.model_dump(mode="json")
                    },
                ),
            )
            return c.PublishResponse(agents=result)
