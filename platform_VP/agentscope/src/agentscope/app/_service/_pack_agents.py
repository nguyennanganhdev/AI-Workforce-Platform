"""Sample agents of a library pack, copied into the installing user's space.

A copy keeps the template's spec and its model evaluation unchanged, so the
publish gate holds without a new eval run. Copies have stable ids per
(user, pack, template): installing twice changes nothing.
"""

from uuid import NAMESPACE_URL, uuid5

from .._agent_spec import AgentSpec
from ..storage import AgentData, AgentRecord, InviteConfig, SessionConfig
from ._agent_studio import apply_bindings, materialize
from ._publish_gate import publish_blocker


def copy_id(user_id: str, pack_id: str, template_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"pack-agent:{user_id}:{pack_id}:{template_id}"))


async def install_templates(storage, workspaces, access, user_id, pack_id, owner_id, template_ids, model_config):
    """Publish one copy per template the pack owner still has published and evaluated."""
    from .._router._workforce_console import _FIXED_CONTEXT, _FIXED_REACT, _archive
    from .._router._workforce_studio import _skill_installer

    installed = []
    for template_id in template_ids:
        template = await storage.get_agent(owner_id, template_id)
        if (template is None or template.data.lifecycle_state != "published" or not template.data.spec
                or template.data.system_role != "business"):
            continue
        spec = AgentSpec.model_validate(template.data.spec)
        if publish_blocker(spec, template.data.evaluation):
            continue
        ident = copy_id(user_id, pack_id, template_id)
        current = await storage.get_agent(user_id, ident)
        if current is not None and current.data.lifecycle_state == "published":
            installed.append(ident)
            continue
        record = current or AgentRecord(id=ident, user_id=user_id, data=AgentData(
            name=template.data.name, context_config=_FIXED_CONTEXT.model_copy(deep=True),
            react_config=_FIXED_REACT.model_copy(deep=True), invite_config=InviteConfig(invitable=False),
            system_role="business", lifecycle_state="draft", build_description=template.data.build_description,
            spec=spec.model_dump(mode="json"), generated_skill=template.data.generated_skill))
        await storage.upsert_agent(user_id, record)
        workspace_id, session_id = "published-" + ident, "pack-primary-" + ident
        if await storage.get_session(user_id, ident, session_id) is None:
            await storage.upsert_session(user_id, ident, session_id=session_id, config=SessionConfig(
                workspace_id=workspace_id, name="Pack primary session", chat_model_config=model_config))
        record = record.model_copy(deep=True)
        record.data.resource_workspace_id = workspace_id
        materialize(record, spec, author="template", note=f"Gói {pack_id}", evaluation=template.data.evaluation)
        await apply_bindings(storage, workspaces, user_id, record, spec,
            install_skill=_skill_installer(None, storage, user_id, ident), stage=True, access=access)
        if (template.data.generated_skill or "").strip():
            workspace = await workspaces.get_workspace(user_id, ident, session_id, workspace_id)
            name = (spec.name or "pack-skill").lower().replace(" ", "-")[:64]
            await workspace.add_skill_archive(_archive(name, template.data.generated_skill), "tar", name, agent_id=ident)
        await storage.upsert_agent(user_id, record)
        installed.append(ident)
    return installed


async def withdraw_templates(storage, user_id, pack_id, template_ids):
    """Removing a pack takes its copies out of the team; the records stay for history."""
    for template_id in template_ids:
        record = await storage.get_agent(user_id, copy_id(user_id, pack_id, template_id))
        if record is None or record.data.lifecycle_state != "published":
            continue
        record = record.model_copy(deep=True)
        record.data.lifecycle_state = "withdrawn"
        record.data.invite_config = record.data.invite_config.model_copy(update={"invitable": False})
        await storage.upsert_agent(user_id, record)
