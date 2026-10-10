"""Manual/dynamic member intent; never clones an agent definition."""

from ._models import detached, new_id, require, scope_key, snapshot, stored_scope
from ._runs import RunService


class MemberService:
    def __init__(self, repository, identity, router, runtime):
        self.repository, self.identity, self.router, self.runtime = repository, identity, router, runtime

    async def add(self, scope, run_id, candidate, *, expected_revision, reason):
        require(isinstance(reason, str) and bool(reason.strip()), "SELECTION_REASON_REQUIRED")
        candidate = snapshot(candidate)
        candidate["scope"] = stored_scope(candidate["scope"])
        version = await self.router.validate_version(scope, candidate)
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            run = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(run is not None and run.status == "running", "RUN_UNAVAILABLE")
            require(run.revision == expected_revision, "REVISION_CONFLICT")
            existing = next((m for m in run.members if m["agent_id"] == candidate["agent_id"]), None)
            if existing:
                return detached(run)
            if run.pending_members:
                # Retry the persisted intent; never replace its session/version or operation ID.
                require(any(m["agent_id"] == candidate["agent_id"] and
                            m["version_id"] == candidate["version_id"] and
                            m["manifest_hash"] == candidate["manifest_hash"]
                            for m in run.pending_members), "MEMBERSHIP_UPDATE_PENDING")
            else:
                run.pending_members = [{**detached(candidate), "manifest": detached(version["manifest"]),
                                        "session_id": new_id(), "selection_reason": [reason]}]
                run.membership_operation_id = new_id()
                await self.repository.save("run", run, expected_revision, uow)
        return await RunService(self.repository, self.identity, self.router, self.runtime).resume_materialization(scope, run_id)
