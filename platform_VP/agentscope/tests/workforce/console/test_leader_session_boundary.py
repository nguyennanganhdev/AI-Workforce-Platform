"""Resident-case navigation must not select private or hidden manager runs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._router import _workforce_console as console
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig, SessionConfig, SessionRecord
from agentscope.app.storage._model._session import PersonalChatConfig
from tests.personal_chat_test import personal_app


@pytest.mark.asyncio
async def test_bootstrap_selects_case_instead_of_hidden_or_personal_session():
    agent = AgentRecord(id="leader", user_id="u", data=AgentData(name="Leader", system_role="leader", context_config=ContextConfig(), react_config=ReActConfig()))
    hidden = SessionRecord(id="hidden", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="hidden"))
    hidden.state.middle_context.update(management_case_session_id="case", workflow_id="wf")
    direct = SessionRecord(id="direct", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="direct", personal_chat=PersonalChatConfig(kind="direct")))
    case = SessionRecord(id="case", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="case"))
    case.state.middle_context["workflow_id"] = "wf"
    storage = SimpleNamespace(list_agents=AsyncMock(return_value=[agent]), upsert_agent=AsyncMock(), list_sessions=AsyncMock(return_value=[hidden, direct, case]), upsert_session=AsyncMock())
    manager = SimpleNamespace(get_workspace=AsyncMock(return_value=SimpleNamespace(default_mcps=[])))
    model = ChatModelConfig(type="test", credential_id="offline", model="offline", parameters={})
    with patch.object(console, "_model_config", AsyncMock(return_value=model)):
        _, selected = await console._leader("u", storage, manager)
    assert selected.id == "case"
    storage.upsert_session.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_with_only_personal_history_creates_separate_case():
    personal = SessionRecord(id="personal", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="personal", personal_chat=PersonalChatConfig(kind="direct")))
    created = SessionRecord(id="new-case", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="new-case"))
    storage = SimpleNamespace(list_sessions=AsyncMock(return_value=[personal]), upsert_session=AsyncMock(return_value=created))
    manager = SimpleNamespace(assign_workspace_id=AsyncMock(return_value="new-case"))
    model = ChatModelConfig(type="test", credential_id="offline", model="offline", parameters={})
    selected = await console._primary_session(storage, manager, "u", "leader", model, "Ticket mới", leader_only=True)
    assert selected.id == "new-case"
    assert personal.config.personal_chat.kind == "direct"


def test_leader_list_does_not_hide_or_select_personal_history(personal_app):
    _, client, storage = personal_app
    records = [SessionRecord(id="case", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="case")),
               SessionRecord(id="direct", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="direct", personal_chat=PersonalChatConfig(kind="direct"))),
               SessionRecord(id="manager", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="manager"))]
    records[-1].state.middle_context["management_case_session_id"] = "case"
    records[0].state.middle_context["workflow_id"] = "wf"
    for record in records:
        client.portal.call(storage.upsert_session, "alice", "alice-a", record.config, record.state, record.id)
    response = client.get("/sessions/", params={"agent_id": "alice-a", "scope": "leader"})
    assert response.status_code == 200
    assert [view["session"]["id"] for view in response.json()["sessions"]] == ["case"]
    all_views = client.get("/sessions/", params={"agent_id": "alice-a"}).json()["sessions"]
    assert {view["session"]["id"] for view in all_views} == {"case", "direct"}
    client.headers["X-User-ID"] = "bob"
    assert client.get("/sessions/", params={"agent_id": "alice-a", "scope": "leader"}).status_code == 404


def test_legacy_manual_sessions_are_separated_by_binding_not_their_title(personal_app):
    _, client, storage = personal_app
    case = SessionRecord(id="case", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="case", name="Phiên thử Leader"))
    case.state.middle_context["workflow_id"] = "wf-real"
    manual = SessionRecord(id="manual", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="manual", name="Phiếu đã đổi tên"))
    hidden = SessionRecord(id="hidden", user_id="alice", agent_id="alice-a", config=SessionConfig(workspace_id="hidden"))
    hidden.state.middle_context["management_output_session_id"] = "case"
    for record in [case, manual, hidden]:
        client.portal.call(storage.upsert_session, "alice", "alice-a", record.config, record.state, record.id)
    for scope, expected in [("leader", ["case"]), ("leader_tests", ["manual"])]:
        response = client.get("/sessions/", params={"agent_id": "alice-a", "scope": scope})
        assert response.status_code == 200
        assert [view["session"]["id"] for view in response.json()["sessions"]] == expected
    client.headers["X-User-ID"] = "bob"
    assert client.get("/sessions/", params={"agent_id": "alice-a", "scope": "leader_tests"}).status_code == 404


@pytest.mark.asyncio
async def test_bootstrap_prefers_real_case_over_more_recent_test_and_reuses_tests_without_creating_more():
    case = SessionRecord(id="case", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="case"))
    case.state.middle_context["workflow_id"] = "wf"
    test = SessionRecord(id="test", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="test"))
    storage = SimpleNamespace(list_sessions=AsyncMock(return_value=[test, case]), upsert_session=AsyncMock())
    config = ChatModelConfig(type="test", credential_id="offline", model="offline", parameters={})
    assert (await console._primary_session(storage, object(), "u", "leader", config, "x", leader_only=True)).id == "case"
    storage.list_sessions.return_value = [test]
    assert (await console._primary_session(storage, object(), "u", "leader", config, "x", leader_only=True)).id == "test"
    storage.upsert_session.assert_not_called()


@pytest.mark.asyncio
async def test_create_test_has_its_own_workspace_and_never_binds_a_workflow():
    seed = SessionRecord(id="case", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="real"))
    seed.state.middle_context["workflow_id"] = "wf"
    created = SessionRecord(id="test", user_id="u", agent_id="leader", config=SessionConfig(workspace_id="fresh", name="Phiên thử Leader"))
    storage = SimpleNamespace(upsert_session=AsyncMock(return_value=created))
    manager = SimpleNamespace(get_workspace=AsyncMock(return_value=SimpleNamespace(default_mcps=[])))
    with patch.object(console, "_leader", AsyncMock(return_value=(SimpleNamespace(id="leader"), seed))):
        view = await console.create_leader_ticket("u", storage, manager)
    assert view.is_test and view.session_id == "test"
    assert storage.upsert_session.await_args.kwargs["config"].name == "Phiên thử Leader"
    # A personal account's new Leader session is a conversation, not a BQL test run.
    with patch.object(console, "_leader", AsyncMock(return_value=(SimpleNamespace(id="leader"), seed))), \
         patch("agentscope.app._service._personal_jobs.personal_context", AsyncMock(return_value=(object(), object()))):
        personal = await console.create_leader_ticket("u", storage, manager)
    assert not personal.is_test
    assert storage.upsert_session.await_args.kwargs["config"].name == "Cuộc trò chuyện mới"
    assert storage.upsert_session.await_args.kwargs["config"].workspace_id != "real"
    assert "workflow_id" not in created.state.middle_context
    assert seed.state.middle_context["workflow_id"] == "wf"
