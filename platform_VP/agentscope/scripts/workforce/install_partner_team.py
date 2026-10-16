"""Install an explicitly reviewed, model-evaluated partner team.

Run with the application's environment after a consistent backup. This script
never restores presets. OP2 records retain their IDs; other owners receive
independent records. Reports, scope, ownership and concurrent changes are
checked before publication. A private before-state file supports recovery.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import asyncpg

from agentscope.app._agent_spec import AgentSpec, spec_hash
from agentscope.app._router._workforce_console import _model_config
from agentscope.app._service._agent_studio import apply_bindings, materialize
from agentscope.app._service._publish_gate import publish_blocker
from agentscope.app.storage import AgentRecord, RedisStorage, SessionConfig
from agentscope.app.workforce.integrations.unified._readiness import bindable_members, route_readiness
from agentscope.app.workspace_manager import LocalWorkspaceManager


def unpack(row):
    data = dict(row)
    for key in ("config", "tools"):
        if isinstance(data[key], str):
            data[key] = json.loads(data[key])
    return data


async def install(bundle: dict, snapshot: Path) -> dict:
    if bundle.get("ready") is not True or len(bundle.get("teams", [])) != 3:
        raise ValueError("All three reviewed teams must pass evaluation")
    storage = RedisStorage(host=os.environ["REDIS_HOST"], port=int(os.getenv("REDIS_PORT", "6379")),
                           db=int(os.getenv("REDIS_DB", "0")), password=os.getenv("REDIS_PASSWORD") or None)
    await storage.__aenter__()
    db = await asyncpg.connect(os.environ["AGENTSCOPE_SQL_URL"].replace("postgresql+asyncpg://", "postgresql://"))
    workspaces = LocalWorkspaceManager(basedir="/app/examples/agent_service/workspaces")
    workspaces.bind_storage(storage)
    before, routes, originals, protected = {}, {}, {}, {}
    try:
        for team in bundle["teams"]:
            if len(team["agents"]) != 4 or {a["role"] for a in team["agents"]} != {"coordinator", "technical", "cleaning", "security"}:
                raise ValueError("Exactly the four approved business roles are required")
            row = await db.fetchrow("select r.*,g.status,g.domain_id,g.area_id from wf_unified_routes r join wf_partner_manager_routes g on g.id=r.route_id where r.route_id=$1", team["route_id"])
            route = unpack(row) if row else None
            if (route is None or route["status"] != "active" or any(str(route[k]) != str(team[k])
                    for k in ("manager_account_id", "domain_id", "area_id"))):
                raise ValueError("Route scope or approval changed")
            expected_ids = {a["agent_id"] for a in team["agents"]}
            current_ids = set((route["config"] or {}).get("member_agents") or {})
            if current_ids and current_ids != expected_ids:
                raise ValueError("Route already has a different team; refusing to replace it")
            routes[team["route_id"]] = route
            owner = team["manager_account_id"]
            records = await storage.list_agents(owner)
            before[owner] = [a.model_dump(mode="json") for a in records]
            protected[owner] = {a.id: a.model_dump(mode="json") for a in records
                                if a.data.system_role == "business" and a.id not in expected_ids}
            for agent in team["agents"]:
                spec = AgentSpec.model_validate(agent["spec"])
                if agent.get("blocker") or publish_blocker(spec, agent["report"]):
                    raise ValueError("Evaluation evidence is invalid")
                source = await storage.get_agent(bundle["source_manager_id"], agent["source_agent_id"])
                if source is None or source.user_id != bundle["source_manager_id"] or source.data.system_role != "business":
                    raise ValueError("Source agent missing or not owned")
                source_current_hash = spec_hash(AgentSpec.model_validate(source.data.spec))
                op2 = next(t for t in bundle["teams"] if t["manager_account_id"] == bundle["source_manager_id"])
                approved_source = next(a for a in op2["agents"] if a["role"] == agent["role"])
                if source_current_hash not in {agent["source_spec_hash"], spec_hash(AgentSpec.model_validate(approved_source["spec"]))}:
                    raise ValueError("Source agent changed since evaluation")
                expected = source.id if owner == bundle["source_manager_id"] else uuid5(NAMESPACE_URL, "p0-team:" + team["route_id"] + ":" + source.id).hex
                if agent["agent_id"] != expected:
                    raise ValueError("Unexpected agent identity")
                existing = await storage.get_agent(owner, expected)
                if existing and owner != bundle["source_manager_id"] and (
                    existing.user_id != owner or existing.source != "user"
                    or spec_hash(AgentSpec.model_validate(existing.data.spec)) != spec_hash(spec)
                ):
                    raise ValueError("Target identity has unrelated changes")
                originals[(owner, expected)] = existing or source
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open("x", encoding="utf-8") as handle:
            os.chmod(snapshot, 0o600)
            json.dump({"created_at": datetime.now(UTC).isoformat(), "agents": before,
                       "routes": list(routes.values())}, handle, default=str, ensure_ascii=False, indent=2)
        for team in bundle["teams"]:
            owner = team["manager_account_id"]
            for agent in team["agents"]:
                spec = AgentSpec.model_validate(agent["spec"])
                existing = await storage.get_agent(owner, agent["agent_id"])
                if existing and existing.data.lifecycle_state == "published" and existing.data.evaluation == agent["report"]:
                    continue
                record = existing
                if record is None:
                    data = originals[(owner, agent["agent_id"])].data.model_copy(deep=True)
                    data.versions, data.published_version, data.evaluation = [], 0, {}
                    data.id = agent["agent_id"]
                    data.generated_skill = ""
                    data.draft_spec, data.draft_meta = None, {}
                    data.lifecycle_state = "draft"
                    record = AgentRecord(id=agent["agent_id"], user_id=owner, source="user", data=data)
                    await storage.upsert_agent(owner, record)
                if not await storage.list_sessions(owner, record.id):
                    await storage.upsert_session(user_id=owner, agent_id=record.id,
                        config=SessionConfig(name="Agent Studio primary session",
                            workspace_id=await workspaces.assign_workspace_id(user_id=owner, agent_id=record.id, session_id="primary"),
                            chat_model_config=await _model_config(storage, owner)))
                draft, meta = copy.deepcopy(record.data.draft_spec), copy.deepcopy(record.data.draft_meta)
                previous = AgentSpec.model_validate(record.data.spec) if record.data.spec else None
                materialize(record, spec, author="manager", note="P0: approved existing OP2 team, isolated model eval, scoped route binding",
                            evaluation=agent["report"])
                record.data.draft_spec, record.data.draft_meta = draft, meta
                await apply_bindings(storage, workspaces, owner, record, spec, previous=previous)
                await storage.upsert_agent(owner, record)
        results = []
        async with db.transaction():
            for team in bundle["teams"]:
                route = routes[team["route_id"]]
                current = await db.fetchrow("select r.updated_at,g.status from wf_unified_routes r join wf_partner_manager_routes g on g.id=r.route_id where r.route_id=$1 for update of r,g", team["route_id"])
                if current["updated_at"] != route["updated_at"] or current["status"] != "active":
                    raise ValueError("Route changed during publication; no bindings committed")
                ids = [a["agent_id"] for a in team["agents"]]
                coordinator = next(a["agent_id"] for a in team["agents"] if a["role"] == "coordinator")
                members = await bindable_members(storage, route, ids, coordinator)
                route["config"] = {**route["config"], "member_agents": members}
                readiness = await route_readiness(storage, route)
                if not readiness["ready"]:
                    raise ValueError(json.dumps(readiness["issues"]))
                await db.execute("update wf_unified_routes set config=$2::jsonb,updated_at=now() where route_id=$1", team["route_id"], json.dumps(route["config"]))
                results.append(readiness)
        for owner, records in protected.items():
            for agent_id, data in records.items():
                if (await storage.get_agent(owner, agent_id)).model_dump(mode="json") != data:
                    raise ValueError("Unrelated business agent changed during installation")
        return {"ready": all(r["ready"] for r in results), "routes": results,
                "unrelated_business_agents_unchanged": True}
    finally:
        await workspaces.close_all()
        await db.close()
        await storage.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()
    result = asyncio.run(install(json.loads(Path(args.reports).read_text(encoding="utf-8")), Path(args.snapshot)))
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
