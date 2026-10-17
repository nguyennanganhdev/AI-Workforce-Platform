"""Personal groups persist without delegation and cannot cross user/room scope."""
import tempfile
from unittest.mock import patch

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app import create_app
from agentscope.app._personal_chat import context_key
from agentscope.app._tool import TeamCreate
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

    storage = (TestRedis() if request.param == "redis" else
               AsyncSQLAlchemyStorage("sqlite+aiosqlite:///:memory:", create_tables=True))
    with tempfile.TemporaryDirectory() as directory:
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


def test_manual_groups_are_durable_independent_sessions(personal_app):
    _, client, storage = personal_app
    before = client.portal.call(storage.get_agent, "alice", "alice-b")
    group = make_group(client)
    assert client.get("/sessions/personal/groups").json() == [group]
    assert len(group["members"]) == 2
    assert len({m["session_id"] for m in group["members"]}) == 2
    for member in group["members"]:
        session = client.portal.call(storage.get_session, "alice", member["agent_id"], member["session_id"])
        assert session.team_id is None
        assert session.config.personal_chat.root_session_id == group["sessionId"]
        assert not session.state.context
    after = client.portal.call(storage.get_agent, "alice", "alice-b")
    assert before.data == after.data  # No invitability, role or permission mutations.
    assert client.portal.call(storage.list_teams, "alice") == []
    # Browser state/cookies are irrelevant to the persisted group directory.
    client.cookies.clear()
    assert client.get("/sessions/personal/groups").json() == [group]


def test_context_is_scoped_to_owner_group_and_agent(personal_app):
    _, client, _ = personal_app
    first, second = make_group(client, "First"), make_group(client, "Second")
    member = first["members"][1]
    endpoint = f"/sessions/personal/{member['session_id']}/context"
    response = client.patch(endpoint, params={"agent_id": member["agent_id"]}, json={"note": "Only group one knows this", "context_mode": "isolated"})
    assert response.status_code == 200, response.text
    own = client.get(endpoint, params={"agent_id": member["agent_id"]}).json()
    assert own["context_mode"] == "isolated"
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
    assert client.portal.call(storage.list_teams, "alice") == []


def test_personal_chat_rejects_leader_task_routing(personal_app):
    _, client, _ = personal_app
    group = make_group(client)
    response = client.post("/chat/", json={
        "agent_id": group["agentId"], "session_id": group["sessionId"],
        "target_agent_id": "alice-b", "input": None,
    })
    assert response.status_code == 400, response.text


def test_runtime_retains_scope_and_only_shares_selected_group_turns(personal_app):
    app, client, storage = personal_app
    first, second = make_group(client, "Runtime"), make_group(client, "Unrelated")
    member = first["members"][1]
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
        context = client.get(f"/sessions/personal/{first['sessionId']}/context", params={"agent_id": first["agentId"]}).json()
        assert len(context["events"]) == 2, context
        assert "Scoped personal answer" in context["events"][-1]["content"]
        assert client.get(f"/sessions/personal/{second['sessionId']}/context", params={"agent_id": second["agentId"]}).json()["events"] == []
        assert client.portal.call(storage.list_teams, "alice") == []
        endpoint = f"/sessions/personal/{member['session_id']}/context"
        assert client.patch(endpoint, params={"agent_id": member["agent_id"]}, json={"context_mode": "isolated"}).status_code == 200
        client.portal.call(app.state.chat_service._run_impl, "alice", member["session_id"], member["agent_id"], UserMsg(name="user", content="Private next turn"))
        after = client.get(endpoint, params={"agent_id": member["agent_id"]}).json()
        assert len(after["events"]) == 2
        isolation = next(m for m in captured[-1]["middlewares"] if hasattr(m, "_packet_attachment"))
        assert isolation._packet_attachment == ""
