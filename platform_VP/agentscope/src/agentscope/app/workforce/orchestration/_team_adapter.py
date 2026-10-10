"""Adapter boundary for AgentScope TeamRecord/Session/TeamSay, not a new runtime.

The supplied hook must upsert by persisted group/session IDs, use invited
members, apply each immutable manifest, revalidate authority and return the
exact binding. Current AgentInvite inherits model/workspace from existing
sessions and is insufficient for immutable Workforce version pinning.
Foundation must supply the pinned adapter, not call that tool blindly.
"""

from ._models import detached, require, scope_key


class TeamRuntimeAdapter:
    def __init__(self, *, identity, provision_pinned_group, send_team_task):
        self.identity = identity
        self.provision = provision_pinned_group
        self.send = send_team_task

    async def materialize(self, scope, run):
        await self.identity.check_scope_active(scope)
        require(run.scope == scope_key(scope), "RESOURCE_NOT_FOUND")
        # Task ACK/completion may change the run revision during provisioning.
        # The persisted membership operation, not that revision, identifies retries.
        provision_key = (f"{run.group_id}:{run.membership_operation_id}"
                         if run.membership_operation_id else run.group_id)
        desired = detached(run)
        desired.members.extend(desired.pending_members)
        binding = await self.provision(scope, desired, idempotency_key=provision_key)
        require(binding["group_id"] == run.group_id and binding["leader_session_id"] == run.leader_session_id,
                "RUNTIME_BINDING_INVALID")
        require(sorted(binding["members"], key=lambda x: x["agent_id"]) == sorted([
            {k: m[k] for k in ("agent_id", "version_id", "session_id", "manifest_hash")}
            for m in run.members + run.pending_members
        ], key=lambda x: x["agent_id"]), "RUNTIME_BINDING_INVALID")
        return binding

    async def deliver(self, scope, run, task):
        await self.identity.check_scope_active(scope)
        require(run.scope == scope_key(scope) and run.status == "running", "RUN_UNAVAILABLE")
        members = {m["agent_id"]: m for m in run.members}
        require(task["recipient_agent_id"] in members, "MEMBER_NOT_FOUND")
        return await self.send(scope, run.group_id, members[task["recipient_agent_id"]]["session_id"],
                               detached(task), idempotency_key=task["task_id"])
