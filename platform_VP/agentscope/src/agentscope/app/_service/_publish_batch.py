"""Durable customer Builder publication: private staging, atomic activation, repair."""

import hashlib
import json
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException

from ._agent_studio import apply_bindings, materialize
from ._catalog_resources import resolve_catalog_resource
from ._personal_jobs import personal_context
from ._publish_gate import publish_blocker
from .._agent_spec import AgentSpec, spec_hash
from ..storage import AgentData, AgentRecord, InviteConfig, SessionConfig
from ..vin_platform import PlatformError
from ...message import AssistantMsg

_guard = ContextVar("vin_builder_publication_guard", default=None)


def stable_id(*parts):
    return str(uuid5(NAMESPACE_URL, ":".join(parts)))


@asynccontextmanager
async def builder_guard(storage, user_id, conversation_id):
    scope = await personal_context(storage, user_id)
    if scope is None or _guard.get() == (user_id, conversation_id):
        yield
        return
    authority, context = scope
    ident = stable_id("builder-guard", context.tenant_id, user_id, conversation_id)
    try:
        await authority.automation_put(context, ident, "derived", {"type": "builder-guard", "state": "idle"})
    except PlatformError as exc:
        if exc.code != "REVISION_CONFLICT":
            raise
    try:
        lease = await authority.claim(context, ident, seconds=300)
    except PlatformError as exc:
        raise HTTPException(409, "Builder publication is in progress; reload before editing.") from exc
    token = _guard.set((user_id, conversation_id))
    try:
        yield
    finally:
        _guard.reset(token)
        await authority.complete_claim(context, ident, lease, {"type": "builder-guard", "state": "idle"})


async def proposal_for(storage, user_id, body):
    from .._router._workforce_console import _BUILDER_AGENT_ID, _list_all_builder_messages, _stored_proposal
    if await storage.get_session(user_id, _BUILDER_AGENT_ID, body["conversation_id"]) is None:
        raise PlatformError("BUILDER_PROPOSAL_NOT_FOUND", 404)
    proposal = _stored_proposal(await _list_all_builder_messages(storage, user_id, body["conversation_id"]))
    if proposal is None or proposal.proposal_id != body["proposal_id"] or proposal.revision != body["expected_revision"]:
        raise PlatformError("BUILDER_HEAD_CHANGED", 409)
    if proposal.status not in {"ready", "published"} or not proposal.agents:
        raise PlatformError("PUBLICATION_NOT_READY", 409)
    tools = []
    for item in proposal.agents:
        spec = AgentSpec.model_validate(item.spec)
        if publish_blocker(spec, item.evaluation.get("model_report")) or not all(item.evaluation.get("checks", {}).values()):
            raise PlatformError("PUBLICATION_EVALUATION_REQUIRED", 409)
        if item.reuse_agent_id:
            current = await storage.get_agent(user_id, item.reuse_agent_id)
            if (current is None or current.data.lifecycle_state != "published" or not current.data.invite_config.invitable
                    or not current.data.spec or spec_hash(AgentSpec.model_validate(current.data.spec)) != spec_hash(spec)
                    or publish_blocker(spec, current.data.evaluation)):
                raise PlatformError("REUSED_AGENT_CHANGED", 409)
        tools.extend(tool.tool_id for tool in spec.tools)
    if len(tools) != len(set(tools)):
        raise PlatformError("DUPLICATE_BATCH_TOOLS", 409)
    return proposal


async def enqueue(storage, user_id, body, *, previous=None):
    authority, context = await personal_context(storage, user_id)
    proposal = await proposal_for(storage, user_id, body)
    base = stable_id("builder-batch", context.tenant_id, user_id, body["conversation_id"], body["proposal_id"], str(body["expected_revision"]))
    key = base if previous is None else base + ":repair:" + previous.job_id
    payload = {**body, "base_id": base}
    if previous is not None:
        if previous.status not in {"failed", "succeeded"}:
            raise PlatformError("PUBLICATION_STILL_RUNNING", 409)
        payload["resume"] = previous.result or {}
    job = await authority.jobs.enqueue(context, kind="publish-batch", key=key, payload=payload)
    return view(job, proposal)


def view(job, proposal=None):
    result = job.result or {}
    phase = result.get("phase", "queued")
    published = job.status == "succeeded" and phase == "published"
    return {"job_id": job.job_id, "status": "published" if published else "failed" if job.status == "failed" else "queued",
        "phase": phase, "cursor": result.get("cursor", 0), "total": len(proposal.agents) if proposal else result.get("total", 0),
        "agents": result.get("agents", []) if published else [], "error": (job.error or {}).get("code"),
        "can_repair": job.status == "failed"}


async def find_job(storage, user_id, job_id):
    scope = await personal_context(storage, user_id)
    if scope is None:
        raise PlatformError("PERSONAL_WORKSPACE_REQUIRED", 403)
    authority, context = scope
    try:
        return await authority.jobs.get(context, "publish-batch", job_id)
    except PlatformError as exc:
        if exc.code == "JOB_NOT_FOUND":
            raise PlatformError("PUBLICATION_NOT_FOUND", 404) from exc
        raise


async def resource_pins(storage, access, user_id, proposal):
    pins = {}
    for item in proposal.agents:
        spec = AgentSpec.model_validate(item.spec)
        for kind, ids in (("mcp", {tool.mcp_id or tool.tool_id.split(":", 1)[0] for tool in spec.tools}),
                          ("skill", {skill.skill_id for skill in spec.skills})):
            for ident in ids:
                record = await resolve_catalog_resource(storage, user_id, kind, ident)
                if record is None or not record.enabled or (kind == "skill" and record.review_status != "approved"):
                    raise PlatformError("PUBLICATION_RESOURCE_REVOKED", 409)
                snapshot = record.model_dump(mode="json")
                pins[kind + ":" + ident] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
                if kind == "skill" and not (record.archive_base64 or (not record.hub_id and record.markdown)):
                    raise PlatformError("SKILL_PACKAGE_NOT_CACHED", 409)
        for knowledge in spec.knowledge:
            record = await access.resolve_knowledge_base(user_id, knowledge.kb_id)
            pins["kb:" + knowledge.kb_id] = record.updated_at.isoformat()
    return pins


async def run(worker, authority, context, job):
    """Each repair continues the saved manifest; activation is a single CAS."""
    from .._router._workforce_console import _archive, _FIXED_CONTEXT, _FIXED_REACT
    from .._router._workforce_studio import _skill_installer
    user_id, storage = context.initiator_user_id, worker.storage
    body = job.payload["body"]
    async with builder_guard(storage, user_id, body["conversation_id"]):
        proposal = await proposal_for(storage, user_id, body)
        pins = await resource_pins(storage, worker.chat._access, user_id, proposal)
        manifest = dict(body.get("resume") or {})
        if manifest.get("resource_pins", pins) != pins:
            raise PlatformError("PUBLICATION_RESOURCES_CHANGED", 409)
        manifest.update(total=len(proposal.agents), resource_pins=pins)
        manifest.setdefault("records", [])
        manifest.setdefault("agents", [])
        manifest.setdefault("cursor", 0)
        manifest["phase"] = "staging"
        await authority.jobs.checkpoint(job, worker.worker_id, manifest)
        for index, item in enumerate(proposal.agents):
            if index < manifest["cursor"]:
                continue
            if item.reuse_agent_id:
                manifest["agents"].append({"agent_id": item.reuse_agent_id, "name": item.reuse_agent_name or item.name,
                    "session_id": None, "reused": True})
            else:
                ident = stable_id(body["base_id"], str(index))
                workspace_id = "published-" + ident
                session_id = "builder-primary-" + ident
                spec = AgentSpec.model_validate(item.spec)
                record = await storage.get_agent(user_id, ident)
                if record is not None and record.data.lifecycle_state == "published":
                    if (record.data.resource_workspace_id != workspace_id or not record.data.spec
                            or spec_hash(AgentSpec.model_validate(record.data.spec)) != spec_hash(spec)
                            or record.data.evaluation != item.evaluation["model_report"]):
                        raise PlatformError("PUBLISHED_BATCH_CHANGED", 409)
                else:
                    if record is None:
                        record = AgentRecord(id=ident, user_id=user_id, data=AgentData(name=item.name,
                            context_config=_FIXED_CONTEXT.model_copy(deep=True), react_config=_FIXED_REACT.model_copy(deep=True),
                            invite_config=InviteConfig(invitable=False), system_role="business", lifecycle_state="draft",
                            spec=spec.model_dump(mode="json"), generated_skill=item.skill_markdown))
                        await storage.upsert_agent(user_id, record)
                    if record.data.published_version:
                        raise PlatformError("PUBLISHED_BATCH_CHANGED", 409)
                    if await storage.get_session(user_id, ident, session_id) is None:
                        await storage.upsert_session(user_id, ident, session_id=session_id,
                            config=SessionConfig(workspace_id=workspace_id, name="Builder primary session", chat_model_config=proposal.chat_model_config))
                    record = record.model_copy(deep=True)
                    record.data.resource_workspace_id = workspace_id
                    materialize(record, spec, author="builder", note="Durable Builder batch", evaluation=item.evaluation["model_report"])
                    # C02 packages were cached/approved at preflight. The
                    # existing installer checks them again, before decode.
                    await apply_bindings(storage, worker.workspaces, user_id, record, spec,
                        install_skill=_skill_installer(None, storage, user_id, ident), stage=True, access=worker.chat._access)
                    if item.skill_markdown.strip():
                        workspace = await worker.workspaces.get_workspace(user_id, ident, session_id, workspace_id)
                        await workspace.add_skill_archive(_archive(item.skill_name, item.skill_markdown), "tar", item.skill_name, agent_id=ident)
                manifest["records"].append(record.model_dump(mode="json"))
                manifest["agents"].append({"agent_id": ident, "session_id": session_id, "name": item.name, "reused": False})
            manifest["cursor"] = index + 1
            await authority.jobs.checkpoint(job, worker.worker_id, manifest)
        await proposal_for(storage, user_id, body)
        if await resource_pins(storage, worker.chat._access, user_id, proposal) != pins:
            raise PlatformError("PUBLICATION_RESOURCES_CHANGED", 409)
        records = [AgentRecord.model_validate(row) for row in manifest["records"]]
        current = [await storage.get_agent(user_id, record.id) for record in records]
        activated = bool(records) and all(actual is not None and actual.data == expected.data for actual, expected in zip(current, records))
        manifest["phase"] = "activating"
        await authority.jobs.checkpoint(job, worker.worker_id, manifest)
        if records and not activated:
            await storage.activate_agents_batch(user_id, records)
        manifest["phase"] = "activated"
        await authority.jobs.checkpoint(job, worker.worker_id, manifest)
        proposal.status = "published"
        await storage.upsert_message(user_id, body["conversation_id"], AssistantMsg(
            id=stable_id(body["base_id"], "receipt"), name="agent_builder", content="Đã phát hành toàn bộ agent trong đề xuất.",
            structured_output={"workforce_builder_proposal": proposal.model_dump(mode="json")}))
        manifest["phase"] = "published"
        return manifest
