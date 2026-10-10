"""Persist handoff intent; delivered/acknowledged are not completed."""

from ._models import detached, new_id, require, scope_key


TERMINAL = {"completed", "failed", "cancelled", "timed_out"}


class HandoffService:
    def __init__(self, repository, identity, runtime, *, clock):
        self.repository, self.identity, self.runtime = repository, identity, runtime
        self.clock = clock

    async def create(self, scope, run_id, sender_session_id, recipient_agent_id,
                     content, context_refs, *, timeout_seconds=60, in_reply_to=None):
        require(isinstance(content, str) and bool(content.strip()) and len(content) <= 32_000, "TASK_CONTENT_INVALID")
        require(type(timeout_seconds) in (int, float) and 0 < timeout_seconds <= 86400, "TASK_TIMEOUT_INVALID")
        require(isinstance(context_refs, list) and all(isinstance(x, str) for x in context_refs), "CONTEXT_REFS_INVALID")
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            run = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(run is not None, "RESOURCE_NOT_FOUND")
            require(run.status == "running", "RUN_UNAVAILABLE")
            members = {m["agent_id"]: m for m in run.members}
            valid_senders = {run.leader_session_id} | {m["session_id"] for m in run.members}
            require(sender_session_id in valid_senders, "SENDER_NOT_MEMBER")
            require(recipient_agent_id in members, "MEMBER_NOT_FOUND")
            require(sender_session_id != members[recipient_agent_id]["session_id"], "HANDOFF_SELF_LOOP")
            require(len(run.handoffs) < run.max_handoffs, "HANDOFF_LIMIT")
            for previous in run.handoffs.values():
                if previous["status"] not in TERMINAL and previous["deadline"] <= self.clock():
                    previous["status"] = "timed_out"
            active = [t for t in run.handoffs.values() if t["status"] not in TERMINAL]
            require(len(active) < run.max_concurrent, "CONCURRENCY_LIMIT")
            require(not any(t["sender_session_id"] == sender_session_id and
                            t["recipient_agent_id"] == recipient_agent_id and
                            t["content"] == content for t in active), "HANDOFF_LOOP")
            require(run.used_tokens < run.token_limit and run.used_cost_minor < run.cost_limit_minor, "RUN_BUDGET_EXHAUSTED")
            if in_reply_to is not None:
                require(in_reply_to in run.handoffs, "TASK_REFERENCE_INVALID")
            task = {"task_id": new_id(), "sender_session_id": sender_session_id,
                    "recipient_agent_id": recipient_agent_id, "content": content,
                    "context_refs": list(context_refs), "in_reply_to": in_reply_to,
                    "status": "created", "deadline": self.clock() + timeout_seconds}
            run.handoffs[task["task_id"]] = task
            await self.repository.save("run", run, run.revision, uow)
        return await self.dispatch(scope, run_id, task["task_id"])

    async def dispatch(self, scope, run_id, task_id):
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            run = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(run is not None and task_id in run.handoffs, "RESOURCE_NOT_FOUND")
            task = run.handoffs[task_id]
            require(task["deadline"] > self.clock() and task["status"] not in TERMINAL, "TASK_NOT_ACTIVE")
            if task["status"] != "created":
                return detached(task)
        await self.runtime.deliver(scope, run, task)
        return await self.transition(scope, run_id, task_id, "delivered", session_id=run.leader_session_id)

    async def transition(self, scope, run_id, task_id, status, *, session_id, result=None,
                         tokens=0, cost_minor=0):
        require(type(tokens) is int and tokens >= 0 and type(cost_minor) is int and cost_minor >= 0, "USAGE_INVALID")
        require(status in {"delivered", "acknowledged", "completed", "failed", "cancelled", "timed_out"}, "TASK_STATE_INVALID")
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            run = await self.repository.get("run", scope_key(scope), run_id, uow)
            require(run is not None and task_id in run.handoffs, "RESOURCE_NOT_FOUND")
            task = run.handoffs[task_id]
            recipient = next(m for m in run.members if m["agent_id"] == task["recipient_agent_id"])
            allowed = {recipient["session_id"]} if status in {"acknowledged", "completed", "failed"} else {run.leader_session_id, task["sender_session_id"]}
            require(session_id in allowed, "TASK_ACTOR_INVALID")
            if status == "delivered" and task["status"] in TERMINAL:
                # The worker can finish before the sender persists delivery ACK.
                return detached(task)
            if task["status"] in TERMINAL:
                require(task["status"] == status and task.get("result") == result, "TASK_TERMINAL")
                return detached(task)
            require(run.status == "running" or status in {"cancelled", "timed_out"}, "RUN_UNAVAILABLE")
            # ACK may race delivery completion. Never regress acknowledged to delivered.
            if status == "delivered" and task["status"] == "acknowledged":
                return detached(task)
            if task["deadline"] <= self.clock() and status not in {"timed_out", "cancelled"}:
                task["status"] = "timed_out"
            else:
                require(status != "timed_out" or task["deadline"] <= self.clock(), "TASK_DEADLINE_NOT_REACHED")
                require(status != "acknowledged" or task["status"] in {"created", "delivered", "acknowledged"}, "TASK_STATE_INVALID")
                require(status != "delivered" or task["status"] == "created", "TASK_STATE_INVALID")
                if status == "completed":
                    require(result is not None, "TASK_RESULT_REQUIRED")
                task["status"] = status
                if status in {"completed", "failed"}:
                    task["result"] = detached(result)
                    run.used_tokens += tokens
                    run.used_cost_minor += cost_minor
            await self.repository.save("run", run, run.revision, uow)
            return detached(task)
