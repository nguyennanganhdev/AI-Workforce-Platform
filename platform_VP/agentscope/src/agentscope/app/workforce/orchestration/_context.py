"""Role context construction over the current runtime roster."""

from ._models import detached, require


def build_role_context(run, conversation, *, role, agent_id=None):
    require(role in {"leader", "planner", "worker"}, "ROLE_INVALID")
    require(run.conversation_id == conversation.conversation_id and run.scope == conversation.scope,
            "CONTEXT_BINDING_INVALID")
    members = {m["agent_id"]: m for m in run.members}
    require(role == "leader" or agent_id in members, "MEMBER_NOT_FOUND")
    instructions = {
        "leader": "Select published agents by capability; route work to the current roster. Never build agents or execute tools directly.",
        "planner": "Ask only missing user facts, delegate to current members via structured TeamSay, and summarize verified results. Require approval through Execution for side effects.",
        "worker": "Use your pinned capabilities and approved Execution toolkit. Report results with task_id and source references. Do not assume batch peers are members.",
    }
    return {"role": role, "instructions": instructions[role], "run_id": run.run_id,
            "group_id": run.group_id, "roster": [
                {k: m[k] for k in ("agent_id", "version_id", "session_id", "capabilities")}
                for m in run.members], "facts": detached(conversation.facts),
            "provenance": detached(conversation.provenance),
            "pending_questions": detached(conversation.pending_questions)}
