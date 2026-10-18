"""The agent map's links: Leader-to-member and member-to-member, one count per room."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentscope.app._router._workforce_studio import workforce_studio_router
from agentscope.app.deps import get_current_user_id, get_storage


def team(leader, members, age_days=1):
    return SimpleNamespace(leader_agent_id=leader, updated_at=datetime.now() - timedelta(days=age_days),
                           data=SimpleNamespace(members=[SimpleNamespace(agent_id=m) for m in members]))


def test_rooms_become_links_and_old_rooms_are_left_out():
    class Storage:
        async def list_teams(self, user_id):
            assert user_id == "u"
            return [team("leader", ["tech", "coord"]), team("leader", ["coord"]), team("leader", ["guard"], age_days=90)]

    app = FastAPI(); app.include_router(workforce_studio_router)
    app.dependency_overrides[get_current_user_id] = lambda: "u"
    app.dependency_overrides[get_storage] = lambda: Storage()
    with TestClient(app) as client:
        links = client.get("/workforce/console/studio/collaboration").json()
    pairs = {(link["source"], link["target"], link["kind"]): link["tickets"] for link in links}
    assert pairs == {("leader", "coord", "leader"): 2, ("leader", "tech", "leader"): 1, ("coord", "tech", "peer"): 1}
