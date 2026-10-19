"""Exercise real invitation/storage/workspace bindings with an isolated bus.

No model runs or business connectors are invoked. Temporary team sessions are
removed in finally; source agents and their primary sessions are retained.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from agentscope.app._tool import AgentInvite, TeamCreate, TeamDelete
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.message import ToolResultState


async def probe(bundle):
    storage = RedisStorage(host=os.environ["REDIS_HOST"], port=int(os.getenv("REDIS_PORT", "6379")),
                           db=int(os.getenv("REDIS_DB", "0")), password=os.getenv("REDIS_PASSWORD") or None)
    await storage.__aenter__()
    workspaces = LocalWorkspaceManager(basedir="/app/examples/agent_service/workspaces")
    workspaces.bind_storage(storage)
    results = []
    try:
        for team in bundle["teams"]:
            owner = team["manager_account_id"]
            leader = next(a for a in await storage.list_agents(owner) if a.data.system_role == "leader")
            primary = (await storage.list_sessions(owner, leader.id))[0]
            config = primary.config.model_copy(deep=True)
            config.name = "P0 isolated invitation probe"
            session = await storage.upsert_session(user_id=owner, agent_id=leader.id, config=config)
            bus = InMemoryMessageBus()
            common = dict(storage=storage, message_bus=bus, workspace_manager=workspaces,
                          user_id=owner, agent_id=leader.id, session_id=session.id)
            try:
                created = await TeamCreate(**common)(name="P0 invite probe", description="Isolated transport; no business execution")
                assert created.state != ToolResultState.ERROR, created.model_dump()
                pool = [await storage.get_agent(owner, a["agent_id"]) for a in team["agents"]]
                targets = [f"{a.data.name}@{a.id[:8]}" for a in pool]
                task = "Isolation probe only: report your assigned capability; do not invoke a business connector."
                answer = await AgentInvite(**common, invitable_pool=pool)(target=targets[0], prompt=task,
                    additional_assignments=[{"target": target, "prompt": task} for target in targets[1:]])
                assert answer.state != ToolResultState.ERROR, answer.model_dump()
                lead_session = await storage.get_session(owner, leader.id, session.id)
                stored_team = await storage.get_team(owner, lead_session.team_id)
                assert {m.agent_id for m in stored_team.data.members} == {a.id for a in pool}
                assert len(stored_team.data.members) == 4
                bindings = []
                for member in stored_team.data.members:
                    assert member.owner_id == owner and member.role == "invited"
                    borrowed = await storage.get_session(owner, member.agent_id, member.session_id)
                    original = next(a for a in pool if a.id == member.agent_id)
                    assert borrowed.state.middle_context["agent_version"] == original.data.published_version
                    inbox = await bus.inbox_drain(member.session_id, max_count=10)
                    assert len(inbox) == 1
                    workspace = await workspaces.get_workspace(owner, original.id, borrowed.id, borrowed.config.workspace_id)
                    clients = await workspace.list_mcps(agent_id=original.id, session_id=borrowed.id)
                    tools = sorted(name for client in clients for name in client.enable_tools or [])
                    expected = sorted(t["tool_name"] for t in original.data.spec["tools"])
                    assert tools == expected, (original.id, tools, expected)
                    bindings.append({"agent_id": original.id, "version": borrowed.state.middle_context["agent_version"],
                                     "tools": tools, "inbox_delivered": True})
                wakeups = await bus.dequeue_wakeups(max_count=10)
                assert len(wakeups) == 4
                results.append({"route_id": team["route_id"], "invited": 4, "bindings": bindings,
                                "bus": "isolated_in_memory", "business_side_effects": False})
            finally:
                current = await storage.get_session(owner, leader.id, session.id)
                if current and current.team_id:
                    deleted = await TeamDelete(**common)()
                    assert deleted.state != ToolResultState.ERROR, deleted.model_dump()
                await storage.delete_session(owner, leader.id, session.id)
            for original in pool:
                assert await storage.get_agent(owner, original.id) is not None
        return {"routes": results, "total_invited": sum(r["invited"] for r in results), "temporary_sessions_cleaned": True}
    finally:
        await workspaces.close_all()
        await storage.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(probe(json.loads(Path(args.reports).read_text(encoding="utf-8")))), ensure_ascii=True))
