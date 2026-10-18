"""The ticket metrics endpoint reports provider usage and collaboration."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentscope.app._router._workforce_insights import workforce_insights_router
from agentscope.app.deps import (
    get_current_user_id,
    get_shared_context_storage,
    get_storage,
)
from agentscope.app.storage import (
    ProviderUsage,
    SharedContextEvent,
    SharedTaskState,
    TeamSharedContextRecord,
)
from agentscope.app.storage._model._team_context import CollaborationBranch


class _Storage:
    def __init__(self, record=None) -> None:
        self.record = record

    async def get_session(self, user_id, agent_id, session_id):
        if session_id == "leader-session":
            return SimpleNamespace(team_id="team-1")
        if session_id == "solo-session":
            return SimpleNamespace(team_id=None)
        return None

    async def get_team(self, user_id, team_id):
        return None

    async def get_team_shared_context(self, user_id, team_id):
        return self.record


def _client(record) -> TestClient:
    app = FastAPI()
    app.include_router(workforce_insights_router)
    app.dependency_overrides[get_current_user_id] = lambda: "u"
    app.dependency_overrides[get_storage] = lambda: _Storage()
    app.dependency_overrides[get_shared_context_storage] = lambda: _Storage(record)
    return TestClient(app)


def _record() -> TeamSharedContextRecord:
    record = TeamSharedContextRecord(user_id="u", team_id="team-1")
    task = SharedTaskState(id="task-1", objective="Plan a trip")
    task.collaboration["worker-session"] = CollaborationBranch(
        status="completed",
        exchanges=3,
        model_calls=2,
        measured_tokens=4000,
    )
    record.state.tasks["task-1"] = task
    record.state.active_task_id = "task-1"
    record.state.events.append(
        SharedContextEvent(revision=1, task_id="task-1", kind="customer_message", content="hi"),
    )
    record.state.events.append(
        SharedContextEvent(revision=2, task_id="task-1", kind="result", content="done"),
    )
    record.state.metrics.provider_usage["leader"] = ProviderUsage(
        agent_name="Workforce Leader",
        model="gpt-strong",
        calls=2,
        calls_with_usage=2,
        input_tokens=6000,
        cached_input_tokens=3000,
        output_tokens=300,
    )
    record.state.metrics.provider_usage["hotel"] = ProviderUsage(
        agent_name="Hotel",
        model="gpt-mini",
        calls=1,
        calls_with_usage=1,
        input_tokens=2000,
        cached_input_tokens=0,
        output_tokens=100,
    )
    return record


def test_metrics_total_cache_ratio_branches_and_events() -> None:
    response = _client(_record()).get("/workforce/console/tickets/leader-session/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total"]["input_tokens"] == 8000
    assert body["total"]["cached_input_tokens"] == 3000
    assert body["total"]["cache_hit_ratio"] == 0.375
    leader = next(item for item in body["by_agent"] if item["agent_id"] == "leader")
    assert leader["cache_hit_ratio"] == 0.5
    assert body["branches"][0]["exchanges"] == 3
    # The core does not count evidence rejections per branch.
    assert body["branches"][0]["evidence_rejections"] == 0
    assert body["event_counts"] == {"customer_message": 1, "result": 1}


def test_ticket_without_team_returns_empty_metrics() -> None:
    response = _client(None).get("/workforce/console/tickets/solo-session/metrics")

    assert response.status_code == 200
    assert response.json()["by_agent"] == []


def test_unknown_ticket_is_404() -> None:
    response = _client(None).get("/workforce/console/tickets/missing/metrics")

    assert response.status_code == 404
