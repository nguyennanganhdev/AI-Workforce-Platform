"""Agent Studio: create, copilot, test, publish, version and rollback."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentscope.app._router import _workforce_studio as studio
from agentscope.app._service import _agent_eval
from agentscope.app.deps import (
    get_current_user_id,
    get_resource_access_service,
    get_storage,
    get_workspace_manager,
)
from agentscope.app.storage import ChatModelConfig, SessionRecord
from agentscope.message import TextBlock, ToolCallBlock
from agentscope.model import ChatResponse


class _Workspace:
    def __init__(self) -> None:
        self.mcps: dict[tuple[str, str], list] = {}
        self.default_mcps: list = []

    async def list_mcps(self, *, agent_id=None, session_id=None):
        return list(self.mcps.get((agent_id, session_id), []))

    async def remove_mcp(self, name, *, agent_id=None, session_id=None):
        self.mcps[(agent_id, session_id)] = [
            c for c in self.mcps.get((agent_id, session_id), []) if c.name != name
        ]

    async def add_mcp(self, client, *, agent_id=None, session_id=None):
        self.mcps.setdefault((agent_id, session_id), []).append(client)
        return client

    skills: dict = {}

    async def list_skills(self, *, agent_id=None):
        return list(self.skills.get(agent_id, []))

    async def remove_skill(self, name, *, agent_id=None):
        self.skills[agent_id] = [s for s in self.skills.get(agent_id, []) if s != name]


class _WorkspaceManager:
    def __init__(self) -> None:
        self.workspace = _Workspace()

    async def assign_workspace_id(self, **_kwargs):
        return "ws-1"

    async def get_workspace(self, *_args):
        return self.workspace


class _Storage:
    def __init__(self) -> None:
        self.agents = {}
        self.sessions = {}
        from agentscope.app.storage import MCPRecord
        from agentscope.mcp import HttpMCPConfig, MCPClient

        self.mcp = MCPRecord(
            id="mcp-1",
            user_id="u",
            client=MCPClient(
                name="demo",
                is_stateful=False,
                mcp_config=HttpMCPConfig(url="http://127.0.0.1:8765/mcp"),
            ),
            discovered_tools=[
                {"name": "lookup_incident_type", "description": "Classify", "input_schema": {"type": "object"}, "read_only": True},
                {"name": "create_work_order", "description": "Create", "input_schema": {"type": "object"}, "read_only": False},
            ],
        )

    async def get_agent(self, _user, agent_id):
        record = self.agents.get(agent_id)
        return record.model_copy(deep=True) if record else None

    async def upsert_agent(self, _user, record):
        self.agents[record.id] = record.model_copy(deep=True)
        return record

    async def list_agents(self, _user):
        return [r.model_copy(deep=True) for r in self.agents.values()]

    async def upsert_session(self, user_id, agent_id, config, state=None, session_id=None, origin=None, **_):
        record = SessionRecord(
            id=session_id or f"session-{agent_id}",
            user_id=user_id,
            agent_id=agent_id,
            config=config,
        )
        self.sessions[record.id] = record
        return record

    async def list_sessions(self, _user, agent_id):
        return [s for s in self.sessions.values() if s.agent_id == agent_id]

    async def get_mcp(self, _user, mcp_id):
        return self.mcp if mcp_id == "mcp-1" else None

    async def list_mcps(self, _user):
        return [self.mcp]

    async def list_knowledge_bases(self, _user):
        return [SimpleNamespace(id="kb-1", data=SimpleNamespace(name="Quy trình kỹ thuật", description="SOP sửa chữa"))]

    async def get_skill(self, _user, skill_id):
        return SimpleNamespace(id="sk-1", name="photo-check", hub_id="hub", card_id="card", version="1") \
            if skill_id == "sk-1" else None

    async def list_skills(self, _user):
        return [SimpleNamespace(id="sk-1", name="photo-check", description="Đọc ảnh hiện trường", display_name=None,
                                enabled=True)]


class _Model:
    """Answers scenarios, passes judgements and proposes copilot patches."""

    def __init__(self) -> None:
        self.copilot_operations: list[dict] = []
        self.judge_pass = True
        self.plan: dict | None = None
        self.call_error: Exception | None = None

    async def __call__(self, messages, tools=None, tool_choice=None, **_):
        if self.call_error is not None:
            raise self.call_error
        return ChatResponse(content=[TextBlock(text="Hãy khoá van tổng trước.")], is_last=True)

    async def generate_structured_output(self, messages, structured_model, **_):
        if structured_model.__name__ == "_Judgement":
            return SimpleNamespace(content={"passed": self.judge_pass, "reason": "ok"})
        if structured_model.__name__ == "CompositionPlan":
            return SimpleNamespace(content=self.plan)
        return SimpleNamespace(
            content={
                "assistant_message": "Đã thêm luật.",
                "questions": [],
                "operations": self.copilot_operations,
            },
        )


@pytest.fixture()
def env(monkeypatch):
    storage = _Storage()
    model = _Model()
    manager = _WorkspaceManager()

    async def fake_models(*_args, **_kwargs):
        return model, model

    async def fake_config(*_args):
        return ChatModelConfig(type="openai_credential", credential_id="c", model="m", parameters={})

    monkeypatch.setattr(studio, "_models", fake_models)
    monkeypatch.setattr(studio, "_model_config", fake_config)
    app = FastAPI()
    app.include_router(studio.workforce_studio_router)
    from agentscope.app._router._workforce_console import workforce_console_router

    app.include_router(workforce_console_router)
    app.dependency_overrides[get_current_user_id] = lambda: "u"
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_workspace_manager] = lambda: manager
    app.dependency_overrides[get_resource_access_service] = lambda: None
    return TestClient(app), storage, model, manager


BASE = "/workforce/console/studio"


def test_template_agent_lifecycle_test_publish_copilot_rollback(env) -> None:
    client, storage, model, manager = env

    created = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"})
    assert created.status_code == 201, created.text
    agent = created.json()
    agent_id = agent["agent_id"]
    assert agent["lifecycle_state"] == "draft"
    assert agent["can_publish"] is False
    assert "chạy kiểm thử" in agent["publish_blocker"]

    # Attach a read tool and a write tool through the form.
    draft = agent["draft"]
    draft["tools"] = [
        {"tool_id": "mcp-1:lookup_incident_type", "mcp_id": "mcp-1", "tool_name": "lookup_incident_type", "read_only": True},
        {"tool_id": "mcp-1:create_work_order", "mcp_id": "mcp-1", "tool_name": "create_work_order", "requires_consent": True},
    ]
    saved = client.put(f"{BASE}/agents/{agent_id}/draft", json={"spec": draft, "note": "tools"})
    assert saved.status_code == 200

    report = client.post(f"{BASE}/agents/{agent_id}/tests/run").json()
    assert report["total"] == 3 and report["publishable"] is True

    published = client.post(f"{BASE}/agents/{agent_id}/publish", json={"note": "v1"})
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["published_version"] == 1 and body["lifecycle_state"] == "published"
    record = storage.agents[agent_id]
    assert record.data.invite_config.invitable is True
    assert {b["tool_name"] for b in record.data.tool_bindings} == {"lookup_incident_type", "create_work_order"}
    session_id = next(iter(storage.sessions))
    [mcp] = manager.workspace.mcps[(agent_id, session_id)]
    assert sorted(mcp.enable_tools) == ["create_work_order", "lookup_incident_type"]

    model.copilot_operations = [
        {"op": "add", "field": "rules", "value": {"text": "Không báo giá khi chưa có ảnh hiện trường", "level": "must"}},
    ]
    copilot = client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "thêm luật không báo giá khi chưa có ảnh"})
    assert copilot.status_code == 200, copilot.text
    assert copilot.json()["changes"][0]["action"] == "added"
    assert copilot.json()["agent"]["can_publish"] is False  # draft changed: test again

    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    v2 = client.post(f"{BASE}/agents/{agent_id}/publish", json={"note": "v2"}).json()
    assert v2["published_version"] == 2
    assert "Không báo giá khi chưa có ảnh" in storage.agents[agent_id].data.system_prompt

    rolled = client.post(f"{BASE}/agents/{agent_id}/rollback", json={"version": 1}).json()
    assert rolled["published_version"] == 3
    assert "Không báo giá khi chưa có ảnh" not in storage.agents[agent_id].data.system_prompt
    assert [v["version"] for v in rolled["versions"]] == [3, 2, 1]


def test_an_agent_is_removed_unless_something_still_uses_it(env) -> None:
    from agentscope.app.deps import get_session_service

    client, storage, _model, _manager = env
    removed = []

    class Sessions:
        async def delete_agent(self, user_id, agent_id):
            removed.append(agent_id)
            return storage.agents.pop(agent_id, None) is not None

    client.app.dependency_overrides[get_session_service] = lambda: Sessions()
    used = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()["agent_id"]
    free = client.post(f"{BASE}/agents", json={"template_id": "travel_cost"}).json()["agent_id"]

    async def partner_route(user_id, agent_id):
        return "Agent đang được tuyến đối tác dùng." if agent_id == used else None

    client.app.state.agent_delete_guards = [partner_route]
    refused = client.delete(f"{BASE}/agents/{used}")
    assert refused.status_code == 409 and "tuyến đối tác" in refused.json()["detail"]
    assert client.delete(f"{BASE}/agents/{free}").status_code == 204
    assert removed == [free]
    assert client.get(f"{BASE}/agents/{free}").status_code == 404
    assert client.delete(f"{BASE}/agents/{free}").status_code == 404


def test_copilot_attaches_only_listed_knowledge_and_skills(env) -> None:
    client, _storage, model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()["agent_id"]
    model.copilot_operations = [
        {"op": "add", "field": "knowledge", "value": {"kb_id": "kb-1", "use_for": "quy trình sửa"}},
        {"op": "add", "field": "skills", "value": {"skill_id": "sk-1", "use_when": "cư dân gửi ảnh"}},
        {"op": "add", "field": "skills", "value": {"skill_id": "sk-made-up"}},
    ]
    answer = client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "dùng quy trình và đọc ảnh"}).json()
    draft = answer["agent"]["draft"]
    assert [(k["kb_id"], k["name"]) for k in draft["knowledge"]] == [("kb-1", "Quy trình kỹ thuật")]
    assert [(s["skill_id"], s["name"]) for s in draft["skills"]] == [("sk-1", "photo-check")]
    assert "sk-made-up" in answer["reply"]["assistant_message"]


def test_a_description_can_become_a_tested_team(env) -> None:
    client, storage, model, _manager = env
    model.plan = {
        "mode": "team",
        "reason": "Tra cứu và tính phí là hai việc nối nhau.",
        "agents": [
            {"name": "TraCuu", "role": "tra cứu sự cố", "brief": "Phân loại sự cố bằng lookup_incident_type."},
            {"name": "TinhPhi", "role": "tính phí", "brief": "Tính phí từ kết quả tra cứu."},
        ],
    }
    model.copilot_operations = [
        {"op": "add", "field": "tests", "value": {"scenario": f"Tình huống {i}", "expected": "Làm đúng vai"}}
        for i in range(3)
    ]
    composed = client.post(
        f"{BASE}/agents/compose",
        json={"description": "Nhận báo sự cố, tra loại sự cố rồi tính phí", "allow_team": True, "run_tests": True},
    )
    assert composed.status_code == 200, composed.text
    body = composed.json()
    assert body["plan"]["mode"] == "team" and [a["draft"]["name"] for a in body["agents"]] == ["TraCuu", "TinhPhi"]
    assert len(storage.agents) == 2
    assert all(len(a["draft"]["tests"]) >= 3 for a in body["agents"])
    assert set(body["test_reports"]) == {a["agent_id"] for a in body["agents"]}
    assert all(a["can_publish"] for a in body["agents"])
    assert "nhóm 2 agent" in body["reply"]["assistant_message"]


def test_publishing_installs_the_spec_skills_and_removes_dropped_ones(env) -> None:
    client, _storage, model, manager = env
    workspace = manager.workspace
    workspace.skills = {}

    class Hub:
        async def download(self, user_id, card_id, version):
            return SimpleNamespace(stream=b"zip", format="zip")

    class Service:
        async def install_skill(self, ws, stream, fmt, name, agent_id=None):
            ws.skills.setdefault(agent_id, []).append(name)

    # Read lazily from app.state, only when a spec lists skills.
    client.app.state.skill_hubs = {"hub": Hub()}
    client.app.state.workspace_service = Service()
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()["agent_id"]
    model.copilot_operations = [{"op": "add", "field": "skills", "value": {"skill_id": "sk-1"}}]
    client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "đọc ảnh"})
    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    published = client.post(f"{BASE}/agents/{agent_id}/publish", json={})
    assert published.status_code == 200, published.text
    assert workspace.skills[agent_id] == ["photo-check"]
    model.copilot_operations = [{"op": "remove", "field": "skills", "item_id": "sk-1"}]
    client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "bỏ đọc ảnh"})
    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    assert client.post(f"{BASE}/agents/{agent_id}/publish", json={}).status_code == 200
    assert workspace.skills[agent_id] == []


def test_failed_tests_block_publishing(env) -> None:
    client, _storage, model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "travel_cost"}).json()["agent_id"]
    model.judge_pass = False

    report = client.post(f"{BASE}/agents/{agent_id}/tests/run").json()
    response = client.post(f"{BASE}/agents/{agent_id}/publish", json={})

    assert report["publishable"] is False
    assert response.status_code == 409


def test_a_model_without_credit_is_reported_not_scored(env) -> None:
    client, _storage, model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "travel_cost"}).json()["agent_id"]

    class OutOfCredit(Exception):
        status_code = 429
        code = "insufficient_quota"

    model.call_error = OutOfCredit("You exceeded your current quota")
    report = client.post(f"{BASE}/agents/{agent_id}/tests/run").json()
    detail = client.get(f"{BASE}/agents/{agent_id}").json()

    assert report["publishable"] is False
    assert report["errors"] == report["total"] == 3
    assert "hết credit" in report["model_error"]
    assert detail["publish_blocker"].startswith("Chưa kiểm thử được 3/3 kịch bản: Tài khoản model hết credit")


def test_copilot_cannot_add_a_tool_missing_from_the_catalog(env) -> None:
    client, _storage, model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={}).json()["agent_id"]
    model.copilot_operations = [{"op": "add", "field": "tools", "value": {"tool_id": "ghost:pay"}}]

    body = client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "cho thanh toán"}).json()

    assert body["changes"] == []
    assert "không có trong kho tool" in body["reply"]["assistant_message"]


def test_scenario_runs_read_tools_and_simulates_writes() -> None:
    asyncio.run(_scenario_runs_read_tools_and_simulates_writes())


async def _scenario_runs_read_tools_and_simulates_writes() -> None:
    from agentscope.app._agent_spec import AgentSpec, SpecTest, SpecTool

    class Model:
        def __init__(self):
            self.step = 0

        async def __call__(self, messages, tools=None, **_):
            self.step += 1
            if self.step == 1:
                return ChatResponse(
                    content=[
                        ToolCallBlock(id="c1", name="lookup", input='{"description": "vỡ ống"}'),
                        ToolCallBlock(id="c2", name="create_order", input="{}"),
                    ],
                    is_last=True,
                )
            return ChatResponse(content=[TextBlock(text="Khẩn cấp: khoá van tổng.")], is_last=True)

    ran = []

    async def run_tool(name, args):
        ran.append(name)
        return '{"priority": "khẩn cấp"}'

    spec = AgentSpec(
        name="Kỹ thuật",
        tools=[
            SpecTool(tool_id="m:lookup", mcp_id="m", tool_name="lookup", read_only=True),
            SpecTool(tool_id="m:create_order", mcp_id="m", tool_name="create_order"),
        ],
        tests=[SpecTest(scenario="Vỡ ống nước", expected="Hướng dẫn khoá van", must_include=["van"], expect_tool="lookup")],
    )
    report = await _agent_eval.run_spec_tests(
        spec=spec,
        model=Model(),
        judge_model=None,
        discovered={},
        run_tool=run_tool,
    )

    assert ran == ["lookup"]
    result = report["results"][0]
    assert result["passed"] is True
    assert {c["name"]: c["executed"] for c in result["tool_calls"]} == {"lookup": True, "create_order": False}


def test_legacy_toggle_only_reactivates_a_versioned_agent(env) -> None:
    client, _storage, _model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()["agent_id"]
    toggle = f"/workforce/console/agents/{agent_id}/lifecycle"

    assert client.post(toggle, json={"state": "published"}).status_code == 409

    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    assert client.post(f"{BASE}/agents/{agent_id}/publish", json={}).status_code == 200
    assert client.post(toggle, json={"state": "draft"}).status_code == 200
    reactivated = client.post(toggle, json={"state": "published"})
    assert reactivated.status_code == 200
    assert reactivated.json()["lifecycle_state"] == "published"


def test_running_ticket_keeps_the_version_it_was_invited_with(env) -> None:
    from agentscope.app._service._agent_studio import pinned_view

    client, storage, model, _manager = env
    agent_id = client.post(f"{BASE}/agents", json={"template_id": "resident_technical"}).json()["agent_id"]
    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    client.post(f"{BASE}/agents/{agent_id}/publish", json={})
    model.copilot_operations = [
        {"op": "add", "field": "rules", "value": {"text": "Luật mới của phiên bản 2", "level": "must"}},
    ]
    client.post(f"{BASE}/agents/{agent_id}/copilot", json={"message": "thêm luật"})
    client.post(f"{BASE}/agents/{agent_id}/tests/run")
    client.post(f"{BASE}/agents/{agent_id}/publish", json={})

    record = storage.agents[agent_id]
    assert record.data.published_version == 2
    assert "Luật mới của phiên bản 2" in record.data.system_prompt
    assert "Luật mới của phiên bản 2" not in pinned_view(record, 1).data.system_prompt
    assert pinned_view(record, 2) is record
    assert pinned_view(record, 99) is record
