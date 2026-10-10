"""Durable run intent before runtime provisioning; network calls outside UOW."""

from ._models import StoredRun, detached, new_id, require, scope_key


class RunService:
    def __init__(self, repository, identity, router, runtime):
        self.repository, self.identity = repository, identity
        self.router, self.runtime = router, runtime

    async def start(self, scope, conversation_id, requirements, *, expected_revision):
        selected, catalog_revision = await self.router.select(scope, requirements)
        members = [{**candidate, "session_id": new_id()} for candidate in selected]
        run = StoredRun(new_id(), scope_key(scope), conversation_id, new_id(), new_id(),
                        members, catalog_revision, tuple(requirements))
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            conversation = await self.repository.get("conversation", run.scope, conversation_id, uow)
            require(conversation is not None, "RESOURCE_NOT_FOUND")
            require(conversation.state_revision == expected_revision, "REVISION_CONFLICT")
            require(conversation.active_run_id is None, "RUN_ALREADY_ACTIVE")
            if conversation.mode == "direct":
                require(len(selected) == 1 and selected[0]["agent_id"] == conversation.direct_agent_id,
                        "DIRECT_TARGET_INVALID")
            await self.repository.insert("run", run, uow)
            conversation.active_run_id = run.run_id
            await self.repository.save("conversation", conversation, expected_revision, uow)
        # On timeout, leave the durable materializing intent; resume with the same IDs.
        return await self.resume_materialization(scope, run.run_id)

    async def resume_materialization(self, scope, run_id):
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            run = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(run is not None, "RESOURCE_NOT_FOUND")
            if run.status == "running" and not run.pending_members:
                return detached(run)
            require(run.status in {"running", "materializing"}, "RUN_NOT_MATERIALIZING")
            require(not run.pending_members or bool(run.membership_operation_id), "MEMBERSHIP_BINDING_INVALID")
        await self.runtime.materialize(scope, detached(run))
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            current = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(current is not None, "RESOURCE_NOT_FOUND")
            require(current.status in {"running", "materializing"}, "RUN_NOT_MATERIALIZING")
            if run.pending_members:
                if current.membership_operation_id != run.membership_operation_id:
                    # Another recovery may already have committed this exact membership.
                    fields = ("agent_id", "version_id", "session_id", "manifest_hash")
                    ready = {tuple(m[k] for k in fields) for m in current.members}
                    require(all(tuple(m[k] for k in fields) in ready for m in run.pending_members),
                            "MEMBERSHIP_BINDING_INVALID")
                    return detached(current)
                require(current.pending_members == run.pending_members, "MEMBERSHIP_BINDING_INVALID")
                current.members.extend(current.pending_members)
                current.pending_members = []
                current.membership_operation_id = None
                return detached(await self.repository.save("run", current, current.revision, uow))
            if current.status == "running":
                return detached(current)
            require(current.status == "materializing", "RUN_NOT_MATERIALIZING")
            current.status = "running"
            return detached(await self.repository.save("run", current, current.revision, uow))
