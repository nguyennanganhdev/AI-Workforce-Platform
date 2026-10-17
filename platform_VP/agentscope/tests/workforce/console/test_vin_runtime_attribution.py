"""All entry points use server-derived attribution; no provider is constructed."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("agentscope.app.vin_platform")
from vin_fixtures import authority as authority

from test_vin_model_resolver_contract import real_authority as real_authority
from agentscope.app._service._chat import ChatService
from agentscope.app.vin_platform._context import execution_context, execution_scope


@pytest.mark.asyncio
@pytest.mark.parametrize("origin,purpose", [("user", "chat"), ("schedule", "schedule"), ("channel", "channel")])
async def test_chat_rebuilds_context_for_server_session_origin_and_restores_parent(real_authority, origin, purpose):
    storage, authority, _, _ = real_authority
    storage.get_session = AsyncMock(return_value=SimpleNamespace(origin=SimpleNamespace(type=origin)))
    service = ChatService.__new__(ChatService)
    service._storage = storage
    seen = []

    async def run(*args):
        seen.append(execution_context.get())

    service._run_impl = AsyncMock(side_effect=run)
    parent = await authority.context("bob")
    with execution_scope(parent):
        await service.run("alice", "private-session", "private-agent")
        assert execution_context.get() is parent
    assert seen[0].initiator_user_id == seen[0].billing_subject_id == "alice"
    assert seen[0].workspace_id == "personal:alice"
    assert seen[0].purpose == purpose and seen[0].environment == "production"
    storage.get_session.assert_awaited_once_with("alice", "private-agent", "private-session")


@pytest.mark.asyncio
async def test_parallel_users_do_not_inherit_another_billing_subject(real_authority):
    storage, _, _, _ = real_authority
    storage.get_session = AsyncMock(return_value=SimpleNamespace(origin=SimpleNamespace(type="user")))
    service = ChatService.__new__(ChatService)
    service._storage = storage
    entered, seen = [], []
    ready = asyncio.Event()

    async def run(user_id, *args):
        entered.append(user_id)
        if len(entered) == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), timeout=2)
        seen.append((user_id, execution_context.get().billing_subject_id))

    service._run_impl = AsyncMock(side_effect=run)
    await asyncio.gather(service.run("alice", "a", "agent-a"), service.run("bob", "b", "agent-b"))
    assert set(seen) == {("alice", "alice"), ("bob", "bob")}
    assert execution_context.get() is None


@pytest.mark.asyncio
async def test_enabled_mode_without_authority_never_enters_runtime(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    service = ChatService.__new__(ChatService)
    service._storage = SimpleNamespace()
    service._run_impl = AsyncMock()
    await service.run("alice", "private-session", "private-agent")
    service._run_impl.assert_not_awaited()
