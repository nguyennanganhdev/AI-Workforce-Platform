"""Personal groups persist without delegation and cannot cross user/room scope."""
import tempfile
import json
import os
import time
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app import create_app
from agentscope.app._personal_chat import context_key
from agentscope.app._tool import TeamCreate
from agentscope.app._tool._personal_team_say import PersonalTeamSay as TeamSay
from agentscope.app._shared_context import SharedContextService
from agentscope.app._team_turn import start_team_turn
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import (
    AgentData, AgentRecord, AsyncSQLAlchemyStorage, ChatModelConfig, RedisStorage,
)
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.event import (
    ReplyStartEvent, ReplyEndEvent, TextBlockStartEvent,
    TextBlockDeltaEvent, TextBlockEndEvent,
)
from agentscope.message import UserMsg


@pytest.fixture(params=["redis", "sql"])
def personal_app(request):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class TestRedis(RedisStorage):
        async def __aenter__(self):
            self._client = redis
            return self

        async def aclose(self):
            self._client = None

    with tempfile.TemporaryDirectory() as directory:
        # Concurrent real-agent runs need a database shared by connections.
        storage = (TestRedis() if request.param == "redis" else
                   AsyncSQLAlchemyStorage(os.getenv("GROUP_TEST_POSTGRES_URL") or f"sqlite+aiosqlite:///{directory}/test.sqlite", create_tables=True))
        app = create_app(
            storage=storage, message_bus=InMemoryMessageBus(),
            workspace_manager=LocalWorkspaceManager(directory), enable_index_worker=False,
        )
        with TestClient(app) as client:
            for id_, owner in [("alice-a", "alice"), ("alice-b", "alice"), ("bob-a", "bob")]:
                record = AgentRecord(
                    id=id_, user_id=owner,
                    data=AgentData(
                        name=id_, system_prompt="Only answer sanitation questions.",
                        context_config=ContextConfig(), react_config=ReActConfig(),
                    ),
                )
                client.portal.call(storage.upsert_agent, owner, record)
            client.headers["X-User-ID"] = "alice"
            yield app, client, storage


def make_group(client, name="Personal work"):
    response = client.post("/sessions/personal/groups", json={
        "name": name, "goal": "Plan my own work", "agent_ids": ["alice-a", "alice-b"],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_manual_groups_bind_real_team_with_independent_working_context(personal_app):
    _, client, storage = personal_app
    before = client.portal.call(storage.get_agent, "alice", "alice-b")
    group = make_group(client)
    assert client.get("/sessions/personal/groups").json() == [group]
    assert len(group["members"]) == 2
    assert len({m["session_id"] for m in group["members"]}) == 2
    for member in group["members"]:
        session = client.portal.call(storage.get_session, "alice", member["agent_id"], member["session_id"])
        assert session.team_id == group["teamId"]
        assert session.config.personal_chat.root_session_id == group["sessionId"]
        assert not session.state.context
    after = client.portal.call(storage.get_agent, "alice", "alice-b")
    assert before.data == after.data  # No invitability, role or permission mutations.
    assert len(client.portal.call(storage.list_teams, "alice")) == 1
    # Browser state/cookies are irrelevant to the persisted group directory.
    client.cookies.clear()
    assert client.get("/sessions/personal/groups").json() == [group]


def test_context_is_scoped_to_owner_group_and_agent(personal_app):
    _, client, _ = personal_app
    first, second = make_group(client, "First"), make_group(client, "Second")
    member = first["members"][1]
    endpoint = f"/sessions/personal/{member['session_id']}/context"
    response = client.patch(endpoint, params={"agent_id": member["agent_id"]}, json={"note": "Only group one knows this"})
    assert response.status_code == 200, response.text
    own = client.get(endpoint, params={"agent_id": member["agent_id"]}).json()
    assert own["collaborative"] is True
    assert client.patch(endpoint, params={"agent_id": member["agent_id"]}, json={"context_mode": "isolated"}).status_code == 400
    root = client.get(f"/sessions/personal/{first['sessionId']}/context", params={"agent_id": first["agentId"]}).json()
    assert "Only group one knows this" in root["events"][0]["content"]
    other = client.get(f"/sessions/personal/{second['sessionId']}/context", params={"agent_id": second["agentId"]}).json()
    assert other["events"] == []
    assert client.get(endpoint, params={"agent_id": "alice-a"}).status_code == 404
    assert client.get(endpoint, params={"agent_id": member["agent_id"]}, headers={"X-User-ID": "bob"}).status_code == 404
    assert client.get("/sessions/personal/groups", headers={"X-User-ID": "bob"}).json() == []


def test_group_creation_checks_all_grants_before_writing(personal_app):
    _, client, _ = personal_app
    response = client.post("/sessions/personal/groups", json={"name": "Blocked", "agent_ids": ["alice-a", "bob-a"]})
    assert response.status_code == 404
    assert client.get("/sessions/personal/groups").json() == []
    for ids in [["alice-a"], ["alice-a", "alice-a"]]:
        assert client.post("/sessions/personal/groups", json={"name": "Invalid", "agent_ids": ids}).status_code == 422


def test_deleting_group_keeps_agents_and_other_private_chats(personal_app):
    _, client, storage = personal_app
    direct = client.post("/sessions/", json={"agent_id": "alice-a", "personal": True}).json()["session_id"]
    group = make_group(client)
    member = group["members"][1]
    assert client.delete(f"/sessions/{member['session_id']}", params={"agent_id": member["agent_id"]}).status_code == 409
    endpoint = f"/sessions/personal/{group['sessionId']}/context"
    assert client.patch(endpoint, params={"agent_id": group["agentId"]}, json={"note": "shared"}).status_code == 200
    response = client.delete(f"/sessions/personal/groups/{group['sessionId']}", params={"agent_id": group["agentId"]})
    assert response.status_code == 204, response.text
    assert client.get("/sessions/personal/groups").json() == []
    assert client.portal.call(storage.get_session, "alice", "alice-a", direct) is not None
    assert client.portal.call(storage.get_agent, "alice", "alice-b") is not None
    assert client.portal.call(storage.get_team_shared_context, "alice", context_key("alice", group["sessionId"])) is None


def test_team_create_cannot_attach_personal_session(personal_app):
    app, client, storage = personal_app
    group = make_group(client)
    tool = TeamCreate(storage=storage, message_bus=app.state.message_bus,
                      workspace_manager=app.state.workspace_manager,
                      user_id="alice", agent_id=group["agentId"], session_id=group["sessionId"])
    chunk = client.portal.call(tool, "Forbidden", "Delegate")
    assert chunk.state.value == "error"
    assert len(client.portal.call(storage.list_teams, "alice")) == 1


def test_direct_chat_rejects_leader_task_routing(personal_app):
    _, client, _ = personal_app
    direct = client.post("/sessions/", json={"agent_id": "alice-a", "personal": True}).json()["session_id"]
    response = client.post("/chat/", json={
        "agent_id": "alice-a", "session_id": direct,
        "target_agent_id": "alice-b", "input": None,
    })
    assert response.status_code == 400, response.text


def test_group_target_routing_is_limited_to_its_roster(personal_app):
    app, client, _ = personal_app
    app.state.chat_service._run_impl = AsyncMock()
    group = make_group(client)
    body = {"agent_id": group["agentId"], "session_id": group["sessionId"], "input": None}
    response = client.post("/chat/", json={**body, "target_agent_id": "bob-a"})
    assert response.status_code == 400, response.text
    response = client.post("/chat/", json={**body, "target_agent_id": "alice-b"})
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == group["members"][1]["session_id"]


def test_direct_runtime_retains_scope_without_delegation(personal_app):
    app, client, storage = personal_app
    direct = client.post("/sessions/", json={"agent_id": "alice-b", "personal": True}).json()["session_id"]
    member = {"agent_id": "alice-b", "session_id": direct}
    captured = []

    class Model:
        context_size = 100_000

        async def count_tokens(self, messages, tools):
            return sum(len(m.get_text_content() or "") for m in messages)

    class ProbeAgent:
        def __init__(self, **kwargs):
            captured.append(kwargs)
            self.state, self.name = kwargs["state"], kwargs["name"]

        async def reply_stream(self, inputs, **kwargs):
            self.state.context.append(inputs)
            self.state.reply_id = "reply-" + inputs.id
            args = {"reply_id": self.state.reply_id}
            yield ReplyStartEvent(**args, session_id=self.state.session_id, name=self.name)
            yield TextBlockStartEvent(**args, block_id="answer")
            yield TextBlockDeltaEvent(**args, block_id="answer", delta="Scoped personal answer")
            yield TextBlockEndEvent(**args, block_id="answer")
            yield ReplyEndEvent(**args, session_id=self.state.session_id)

    session = client.portal.call(storage.get_session, "alice", member["agent_id"], member["session_id"])
    config = session.config.model_copy(update={"chat_model_config": ChatModelConfig(type="test", credential_id="fake", model="fake", parameters={})})
    client.portal.call(storage.upsert_session, "alice", member["agent_id"], config, None, member["session_id"])

    async def get_model(*args, **kwargs):
        return Model()

    app.state.chat_service._agent_cls = ProbeAgent
    with patch("agentscope.app._service._chat.get_model", new=get_model):
        client.portal.call(app.state.chat_service._run_impl, "alice", member["session_id"], member["agent_id"], UserMsg(name="user", content="Help with my own cleaning plan"))
        assert captured, "The selected member must run independently"
        equipped = captured[-1]
        assert "Only answer sanitation questions" in equipped["system_prompt"]
        assert "PERSONAL WORKSPACE POLICY" in equipped["system_prompt"]
        assert "only customer-facing speaker" not in equipped["system_prompt"]
        tools = client.portal.call(equipped["toolkit"].get_tool_schemas)
        assert not {"TeamCreate", "TeamSay", "AgentInvite", "TeamDelete", "Bash", "Write"} & {t["function"]["name"] for t in tools}
        assert not equipped["context_config"].compression_fallback_to_truncation
        assert client.portal.call(storage.list_teams, "alice") == []


def test_group_coordinator_peer_exchange_review_and_isolation(personal_app):
    app, client, storage = personal_app
    app.state.chat_service._run_impl = AsyncMock()
    # Three selected participants: coordinator plus two peers.
    third = client.portal.call(storage.get_agent, "alice", "alice-b").model_copy(deep=True)
    third.id = "alice-c"
    third.storage_revision = 0
    third.data.name = "alice-c"
    client.portal.call(storage.upsert_agent, "alice", third)
    response = client.post("/sessions/personal/groups", json={
        "name": "BQL plan", "agent_ids": ["alice-b", "alice-a", "alice-c"],
        "coordinator_agent_id": "alice-a",
    })
    assert response.status_code == 201, response.text
    group = response.json()
    assert group["agentId"] == "alice-a"
    members = {m["agent_id"]: m for m in group["members"]}
    unrelated = make_group(client, "Other room")
    service = SharedContextService(storage, app.state.message_bus)

    async def exercise():
        event = await service.append_event(user_id="alice", team_id=group["teamId"],
                                           kind="customer_message", content="Prepare a proposed cleaning plan")
        await start_team_turn(app.state.message_bus, group["teamId"],
                              reply_owner_session_id=group["sessionId"], reply_owner_agent_id=group["agentId"],
                              customer_session_id=group["sessionId"], mode="leader", task_id=event.task_id,
                              storage=storage, user_id="alice")
        def tool(id_):
            return TeamSay(storage=storage, message_bus=app.state.message_bus,
                           workspace_manager=app.state.workspace_manager, user_id="alice",
                           agent_id=id_, session_id=members[id_]["session_id"],
                           shared_context_service=service, role="leader" if id_ == "alice-a" else "worker")
        async def send(id_, **kwargs):
            if kwargs.get("to") in {"alice-b", "alice-c"}:
                kwargs["to"] += "@" + kwargs["to"]
            chunk = await tool(id_)(**kwargs)
            assert chunk.state.value != "error", chunk
        await send("alice-a", kind="handoff", to="alice-b", content="Prepare the cleaning proposal", done_when="Include access dependencies")
        await send("alice-b", kind="question", to="alice-c", content="What access constraint should the proposed plan consider?")
        await send("alice-c", kind="answer", content="Proposal: arrange access before moving equipment.", report_type="analysis")
        record = await storage.get_team_shared_context("alice", group["teamId"])
        branch = record.state.tasks[event.task_id].collaboration[members["alice-b"]["session_id"]]
        assert not branch.waiting_for
        await send("alice-b", kind="result", content="Proposal: arrange access first, then clean shared areas; confirm staffing with BQL.", report_type="analysis")
        await send("alice-a", kind="review", to="alice-b", decision="accept", content="Accept the proposal; operational assumptions remain unverified")
        record = await storage.get_team_shared_context("alice", group["teamId"])
        events = record.state.events
        assert {"handoff", "question", "answer", "result"} <= {e.kind for e in events}
        proposal = next(e for e in events if e.kind == "result")
        assert proposal.report_type == "analysis"
        assert proposal.id not in service._trusted_event_ids({e.id: e for e in events})
        assert record.state.tasks[event.task_id].collaboration[members["alice-b"]["session_id"]].status == "completed"
        assert not (await storage.get_team_shared_context("alice", unrelated["teamId"])).state.events
    client.portal.call(exercise)
    page = client.get(f"/sessions/personal/groups/{group['sessionId']}/messages", params={"agent_id": group["agentId"], "limit": 2}).json()
    assert len(page["events"]) == 2 and page["has_more"]
    older = client.get(f"/sessions/personal/groups/{group['sessionId']}/messages", params={"agent_id": group["agentId"], "before_revision": page["before_revision"]}).json()
    assert {e["id"] for e in page["events"]}.isdisjoint(e["id"] for e in older["events"])


def test_old_group_activation_preserves_private_history_and_shared_notes(personal_app):
    app, client, storage = personal_app
    group = make_group(client)
    # Reconstruct the previous release's teamless group without erasing notes.
    client.portal.call(storage.delete_team, "alice", group["teamId"])
    for m in group["members"]:
        record = client.portal.call(storage.get_session, "alice", m["agent_id"], m["session_id"])
        if record is None:
            from agentscope.app.storage import SessionConfig
            from agentscope.app.storage._model._session import PersonalChatConfig, PersonalChatMember
            config = SessionConfig(workspace_id=m["session_id"], name="Old group", personal_chat=PersonalChatConfig(kind="group", root_session_id=group["sessionId"], members=[PersonalChatMember(**x) for x in group["members"]]))
            client.portal.call(storage.upsert_session, "alice", m["agent_id"], config, None, m["session_id"])
        client.portal.call(storage.upsert_message, "alice", m["session_id"], UserMsg(name="user", content="Old private history"))
    response = client.post(f"/sessions/personal/groups/{group['sessionId']}/activate", params={"agent_id": group["agentId"]})
    assert response.status_code == 200, response.text
    assert response.json()["sessionId"] == group["sessionId"]
    assert client.post(f"/sessions/personal/groups/{group['sessionId']}/activate", params={"agent_id": group["agentId"]}).status_code == 200
    context = client.portal.call(storage.get_team_shared_context, "alice", group["teamId"])
    assert context.state.customer_history_bootstrapped and not context.state.events


def test_group_runs_real_agents_and_dispatcher_with_deterministic_provider(personal_app):
    """Exercise the actual runtime/middlewares/inbox, replacing only model I/O."""
    from utils import MockModel
    from agentscope.model import ChatResponse
    from agentscope.message import TextBlock, ToolCallBlock

    app, client, storage = personal_app
    if isinstance(storage, AsyncSQLAlchemyStorage) and not os.getenv("GROUP_TEST_POSTGRES_URL"):
        pytest.skip("Concurrent runtime is tested separately on PostgreSQL; SQLite coverage is for persistence/API")
    third = client.portal.call(storage.get_agent, "alice", "alice-b").model_copy(deep=True)
    third.id, third.storage_revision, third.data.name = "alice-c", 0, "alice-c"
    client.portal.call(storage.upsert_agent, "alice", third)
    calls = {name: 0 for name in ["alice-a", "alice-b", "alice-c"]}
    scripts = {
        "alice-a": [
            [{"kind": "handoff", "to": "alice-b@alice-b", "content": "Prepare a cleaning proposal and ask the access peer", "done_when": "Include the access dependency"}],
            "Waiting for the proposal.",
            [{"kind": "review", "to": "alice-b@alice-b", "decision": "accept", "content": "Accept proposal as unverified advice"},
             {"kind": "review", "to": "alice-c@alice-c", "decision": "accept", "content": "Accept access suggestion as unverified advice"}],
            "Proposed plan: arrange access first, then clean shared areas. Confirm staffing with BQL. This is advice, not verified operational status.",
        ],
        "alice-b": [
            [{"kind": "question", "to": "alice-c@alice-c", "content": "What access dependency should the cleaning proposal consider?"}],
            [{"kind": "result", "report_type": "analysis", "content": "Proposed plan: arrange access first, then clean shared areas. Confirm staffing with BQL."}],
            "Reported.",
        ],
        "alice-c": [
            [{"kind": "answer", "report_type": "analysis", "content": "Proposal: arrange access first, before cleaning shared areas."}],
            "Answered.",
        ],
    }

    class Provider(MockModel):
        def __init__(self):
            super().__init__(stream=False, context_size=100_000)

        async def count_tokens(self, messages, tools=None):
            return sum(len(m.get_text_content() or "") // 4 + 1 for m in messages) + 200

        async def _call_api(self, *args, **kwargs):
            name = self._usage_attributes["agent_id"]
            index = calls[name]
            calls[name] += 1
            assert calls[name] <= 10, "Runtime did not settle within its bounded script"
            payload = scripts[name][min(index, len(scripts[name]) - 1)]
            blocks = ([TextBlock(text=payload)] if isinstance(payload, str) else
                      [ToolCallBlock(id=f"{name}-{index}-{i}", name="TeamSay", input=json.dumps(p)) for i, p in enumerate(payload)])
            return ChatResponse(content=blocks, is_last=True, usage=None)

    async def model(*args, **kwargs):
        return Provider()

    group = client.post("/sessions/personal/groups", json={
        "name": "Runtime collaboration", "agent_ids": ["alice-a", "alice-b", "alice-c"],
        "coordinator_agent_id": "alice-a",
    })
    # Credential ownership is checked before writes; install a model config
    # directly on test sessions rather than invent a runtime credential grant.
    assert group.status_code == 201, group.text
    group = group.json()
    for member in group["members"][:1]:
        record = client.portal.call(storage.get_session, "alice", member["agent_id"], member["session_id"])
        config = record.config.model_copy(update={"chat_model_config": ChatModelConfig(type="test", credential_id="fake", model="fake", parameters={})})
        client.portal.call(storage.upsert_session, "alice", member["agent_id"], config, None, member["session_id"])
    with patch("agentscope.app._service._chat.get_model", new=model):
        response = client.post("/chat/", json={"agent_id": group["agentId"], "session_id": group["sessionId"], "input": UserMsg(name="BQL", content="Prepare a proposed cleaning and access plan").model_dump(mode="json")})
        assert response.status_code == 200, response.text
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            record = client.portal.call(storage.get_team_shared_context, "alice", group["teamId"])
            if any(e.kind == "customer_reply" and "arrange access first" in e.content for e in record.state.events):
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"No collaborative synthesis: calls={calls}; events={[(e.kind,e.content[:180]) for e in record.state.events]}")
    assert calls["alice-b"] >= 2 and calls["alice-c"] >= 1
    assert {"handoff", "question", "answer", "result", "customer_reply"} <= {e.kind for e in record.state.events}
