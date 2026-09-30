"""Checks over the actual DEV-2 Task Board and budget, never a second counter."""
from .models import AuthorityView, SupervisorState, TaskSpec, require


def validate_tasks(state: SupervisorState, tasks: list[TaskSpec], view: AuthorityView) -> None:
    require(state.room is not None, "room_required")
    ids = [t.task_id for t in tasks]
    require(len(ids) == len(set(ids)), "duplicate_task")
    require(not set(ids) & set(state.tasks), "task_id_requires_new_version")
    members = {p.agent_version_id for p in state.room.participants}
    graph = {k: m.dependencies for k, m in state.tasks.items() if m.plan_version == state.revision}
    graph.update({t.task_id: t.dependencies for t in tasks})
    for t in tasks:
        entry = view.catalog.get(t.assignee_agent_version_id)
        require(t.assignee_agent_version_id in members and entry is not None, "agent_not_allowed")
        require(t.assignee_agent_version_id in entry.task_readers and
                set(entry.task_readers) <= members, "task_acl_denied")
    visiting, visited = set(), set()

    def visit(key):
        require(key in graph, "missing_dependency")
        require(key not in visiting, "dependency_cycle")
        if key in visited:
            return
        visiting.add(key)
        for dep in graph[key]:
            visit(dep)
        visiting.remove(key)
        visited.add(key)
    for key in graph:
        visit(key)


def runnable(state: SupervisorState, task_id: str, agent: str):
    require(state.phase in ("planning", "waiting_result_validation"), "analysis_phase_required")
    room = state.room
    require(room is not None, "room_required")
    require(room.room_state == "idle", room.pause_reason or "room_busy")
    require(room.turns_remaining > 0, "max_turns")
    require(not (room.speaker_agent_version_id == agent and
                 room.consecutive_turns >= state.turn_policy.max_consecutive_turns), "consecutive_limit")
    require(agent in {p.agent_version_id for p in room.participants}, "agent_not_member")
    tasks = {t.task_id: t for t in room.tasks}
    task, meta = tasks.get(task_id), state.tasks.get(task_id)
    require(task is not None and meta is not None, "task_missing")
    require(meta.plan_version == state.revision, "stale_task")
    require(task.assignee_agent_version_id == agent and
            (not task.reader_agent_version_ids or agent in task.reader_agent_version_ids), "task_acl_denied")
    require(task.status != "completed", "task_already_completed")
    require(all(d in tasks and tasks[d].status == "completed" and
                state.tasks[d].plan_version == state.revision for d in meta.dependencies), "dependency_incomplete")
    return task


def result_references(state: SupervisorState) -> set[str]:
    # Only proven Supervisor terminal successes. Mention replies are not work proof.
    return {m.message_id for r in state.terminal_results.values() if r.turn_status == "success"
            for m in r.messages if m.task_id == r.task_id and m.sender == r.speaker_agent_version_id}
