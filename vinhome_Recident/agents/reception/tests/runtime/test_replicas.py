"""Several copies of the runtime in `loop` mode: nothing a turn needs lives in one copy.

Two apps stand for two containers; they share only the backend, as in the package. That a conversation's
turns reach the copies one at a time is the backend's job (services/vinhomes-api, dispatch_turn) and is tested there.
"""

import json
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.runtime import service
from src.runtime.model import ModelConfig

TOKEN = "s" * 32
MESSAGE = {"id": "m1", "text": "Vòi nước bếp bị rò"}
HOME = {"domain_id": "d1", "building_id": "b1", "unit_id": "u1", "unit_code": "1201", "building_name": "S1.01"}


def backend():
    """The backend's side of a turn, reduced to what makes a retry safe: receipts by key, one reply per message."""
    app, receipts, tickets, replies = FastAPI(), {}, [], {}

    @app.get("/internal/reception/chats/{chat}/context")
    async def context(chat: str):
        # The worst case for a turn delivered twice: neither copy sees yet what the other filed.
        return {"history": [{"id": "m1", "role": "resident", "text": MESSAGE["text"], "photos": 0}],
                "open_request": None, "past_requests": []}

    @app.get("/internal/reception/catalog")
    async def catalog():
        return {"categories": [{"id": "c1", "code": "technical", "name": "Kỹ thuật"}]}

    @app.post("/internal/reception/policy/evaluate")
    async def policy():
        return {"emergency": False}

    @app.post("/internal/reception/chats/{chat}/intake")
    async def intake(chat: str):
        return {"ready": True, "review": False, "missing": None, "question": None, "title": MESSAGE["text"],
                "description": MESSAGE["text"], "facts": [], "rejected": [], "file_ids": []}

    @app.post("/internal/reception/v1/execute")
    async def execute(request: Request):
        call = await request.json()
        if call["idempotency_key"] not in receipts:
            if call["operation"] == "handoff_ticket":
                tickets.append(call["input"]["draft_id"])
            receipts[call["idempotency_key"]] = {
                "get_verified_resident_context": {"resident": {"name": "Cư dân"}, "residences": [HOME]},
                "create_ticket_draft": {"draftId": f"draft-{len(receipts)}"},
                "resolve_management_destination": {"managementUnitId": "bql-1"},
                "handoff_ticket": {"accepted": True, "ticket": {"id": f"t{len(tickets)}", "code": f"VH-{len(tickets)}"}},
            }.get(call["operation"], {})
        return {"result": receipts[call["idempotency_key"]]}

    @app.post("/internal/reception/chats/{chat}/replies", status_code=201)
    async def reply(chat: str, request: Request):
        body = await request.json()
        return {"id": replies.setdefault(body["reply_to_id"], body["text"])}

    return app, tickets, replies


class Model:
    """Files the resident's report, then says so. Holds nothing, like the real client."""

    async def complete(self, messages, tools):
        if messages[-1]["role"] == "tool":
            return {"content": json.dumps({"reply": "Mình đã ghi nhận và chuyển yêu cầu tới Ban quản lý.", "sources": []})}
        return {"content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {
            "name": "file_request", "arguments": json.dumps({
                "symptom": "bị rò", "item": "Vòi nước bếp", "kind": "incident", "category_code": "technical", "priority": "normal"})}}]}


def copy(monkeypatch, shared, state, agent="loop"):
    monkeypatch.setattr(service, "httpx", SimpleNamespace(
        AsyncClient=lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=shared))))
    settings = service.Settings(backend_url="http://backend", service_token=TOKEN, state_path=str(state), agent=agent,
                                model=ModelConfig(model="scripted", api_key="none"))
    return TestClient(service.create_app(settings, model=Model()), headers={"Authorization": "Bearer " + TOKEN})


def turn(run="run-1"):
    return {"user_id": "resident-1", "channel_id": "chat-1", "message": MESSAGE, "delegation": {
        "token": "delegation", "expiresAt": 0,
        "context": {"tenantId": "t", "runId": run, "bindingId": "channel:chat-1", "principalId": "resident-1"}}}


def test_a_turn_delivered_to_two_copies_files_one_request_and_one_reply(monkeypatch, tmp_path):
    shared, tickets, replies = backend()
    with copy(monkeypatch, shared, tmp_path / "one" / "reception.sqlite3") as one, \
            copy(monkeypatch, shared, tmp_path / "two" / "reception.sqlite3") as two:
        first = one.post("/v1/turns", json=turn())
        again = two.post("/v1/turns", json=turn())
    assert first.status_code == again.status_code == 200 and first.json()["reply"] == again.json()["reply"]
    # The keys come from the conversation and the message alone, so the second copy repeats the first one's calls.
    assert len(tickets) == 1 and len(replies) == 1
    # Neither copy wrote a state file: there is nothing to share and nothing to lose with a container.
    assert not (tmp_path / "one").exists() and not (tmp_path / "two").exists()


def test_only_the_fixed_workflow_keeps_a_state_file(monkeypatch, tmp_path):
    shared, _, _ = backend()
    with copy(monkeypatch, shared, tmp_path / "graph" / "reception.sqlite3", agent="graph"):
        assert (tmp_path / "graph" / "reception.sqlite3").exists()
