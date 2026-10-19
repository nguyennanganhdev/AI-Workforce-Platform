"""Owner-scoped room snapshots and live bus updates, without model calls."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agentscope.app._router._workforce_console import stream_room
from agentscope.app._shared_context import SharedContextService
from agentscope.app.message_bus import InMemoryMessageBus
from tests.team_shared_context_test import _Storage


class RoomStorage(_Storage):
    async def get_team(self, user_id, team_id):
        return SimpleNamespace(session_id="leader", data=SimpleNamespace(members=[]))

    async def get_agent(self, user_id, agent_id):
        return None


@pytest.mark.asyncio
async def test_room_stream_delivers_initial_snapshot_and_new_revision():
    storage, bus = RoomStorage(), InMemoryMessageBus()
    storage.sessions[("owner", "leader")] = SimpleNamespace(
        team_id="team", agent_id="leader-agent"
    )
    service = SharedContextService(storage, bus)
    await service.append_event(
        user_id="owner", team_id="team", kind="customer_message", content="Repair leak"
    )
    request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
    response = await stream_room("leader", request, "owner", storage, storage, bus)
    frames = response.body_iterator
    first = await anext(frames)
    initial = json.loads(first.split("data: ", 1)[1])
    event = await service.append_event(
        user_id="owner",
        team_id="team",
        kind="external_event",
        content="Staff accepted\n"
        + json.dumps(
            {
                "tracked_work": {
                    "operation_id": "op1",
                    "status": "accepted",
                    "owner_agent_id": "coordinator",
                    "external_job_id": "WO1",
                    "terminal": False,
                }
            }
        ),
        event_id="provider:1",
    )
    frame = await asyncio.wait_for(anext(frames), timeout=2)
    latest = json.loads(frame.split("data: ", 1)[1])
    assert latest["revision"] > initial["revision"]
    assert latest["tracked_work"][0]["owner_agent_id"] == "coordinator"
    assert latest["timeline"][-1]["kind"] == "partner_event"
    assert latest["revision"] == event.revision
    await frames.aclose()


@pytest.mark.asyncio
async def test_stream_follows_team_created_after_the_session_was_opened():
    storage, bus = RoomStorage(), InMemoryMessageBus()
    session = SimpleNamespace(team_id=None, agent_id="leader-agent")
    storage.sessions[("owner", "leader")] = session
    request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
    response = await stream_room("leader", request, "owner", storage, storage, bus)
    frames = response.body_iterator
    assert json.loads((await anext(frames)).split("data: ", 1)[1])["timeline"] == []
    session.team_id = "team"
    service = SharedContextService(storage, bus)
    await service.append_event(
        user_id="owner", team_id="team", kind="customer_message", content="New ticket"
    )
    latest = json.loads(
        (await asyncio.wait_for(anext(frames), timeout=2)).split("data: ", 1)[1]
    )
    assert latest["timeline"][0]["text"] == "New ticket"
    await frames.aclose()


@pytest.mark.asyncio
async def test_another_owner_cannot_open_the_room_stream():
    storage = RoomStorage()
    storage.sessions[("owner", "leader")] = SimpleNamespace(team_id="team")
    with pytest.raises(HTTPException) as rejected:
        await stream_room(
            "leader", None, "another-owner", storage, storage, InMemoryMessageBus()
        )
    assert rejected.value.status_code == 404
