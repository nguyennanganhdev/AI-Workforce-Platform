"""M2 disabled by default; selected residents cannot open a second intake."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from vinhomes_api.intake_cohorts import configuration, policy, require_legacy_intake
from test_resident_contract import TENANT, BASE, client, sql
from test_resident_contract import database as database  # noqa: F401


def cohort(monkeypatch, **changes):
    value = {"id": "pilot-a", "tenant_id": str(TENANT), "resident_ids": ["local-v3-resident"],
             "platform_url": "http://127.0.0.1:15173"}
    value.update(changes)
    monkeypatch.setenv("VINHOMES_CHATBOT_PLATFORM_COHORTS", json.dumps([value]))
    monkeypatch.setenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", "true")


def test_disabled_flag_ignores_draft_config_and_activated_config_is_strict(monkeypatch):
    monkeypatch.delenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", raising=False)
    monkeypatch.setenv("VINHOMES_CHATBOT_PLATFORM_COHORTS", "not-json")
    assert configuration() == []
    monkeypatch.setenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", "true")
    with pytest.raises(HTTPException) as invalid:
        configuration()
    assert invalid.value.status_code == 503
    for changes in ({"platform_url": "http://external.invalid"}, {"resident_ids": []}, {"tenant_id": "bad"}):
        cohort(monkeypatch, **changes)
        with pytest.raises(HTTPException):
            configuration()


def test_verified_actor_and_tenant_select_cohort_not_user_input(monkeypatch):
    cohort(monkeypatch)
    async def run():
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: str(TENANT))))
        assert not (await policy(db, "local-v3-resident"))["legacy_new_intake"]
        assert (await policy(db, "another-resident"))["legacy_new_intake"]
        with pytest.raises(HTTPException) as denied:
            await require_legacy_intake(db, "local-v3-resident")
        assert denied.value.status_code == 409 and denied.value.detail["code"] == "INTAKE_MOVED_TO_PLATFORM"
        db.execute.return_value.scalar_one = lambda: str(uuid4())
        assert (await policy(db, "local-v3-resident"))["legacy_new_intake"]
    asyncio.run(run())


def test_m2_blocks_new_intake_preserves_history_staff_and_rolls_back(database, monkeypatch):
    monkeypatch.delenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", raising=False)
    with client(database) as resident:
        created = resident.post("/resident/chats", json={"title": "Before cohort cutover"})
        assert created.status_code == 201, created.text
        channel = str(created.json()["id"])
        before = sql(database, "SELECT count(*) AS n FROM channels")[0]["n"]
        cohort(monkeypatch)
        current = resident.get("/resident/intake-policy").json()
        assert current["mode"] == "platform" and current["cohort_id"] == "pilot-a"
        assert "resident_ids" not in current and "tenant_id" not in current
        assert resident.post("/resident/chats", json={"title": "Must not create"}).status_code == 409
        denied = resident.post(f"/resident/chats/{channel}/messages", json={"text": "New request", "client_message_id": uuid4().hex})
        assert denied.status_code == 409, denied.text
        profile = resident.get(BASE + "/me").json()
        body = {"apartmentId": profile["apartments"][0]["id"], "description": "Vòi nước rò cần kiểm tra kỹ thuật.",
                "location": {"description": "Bồn rửa bếp"}, "photoIds": []}
        assert resident.post(BASE + "/requests", json=body, headers={"Idempotency-Key": uuid4().hex}).status_code == 409
        assert resident.get(f"/resident/chats/{channel}/messages").status_code == 200
        assert resident.get(BASE + "/requests").status_code == 200
        assert sql(database, "SELECT count(*) AS n FROM channels")[0]["n"] == before
        with client(database, "technical") as staff:
            assert staff.get("/my-work-orders").status_code == 200
        monkeypatch.setenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", "false")
        assert resident.get("/resident/intake-policy").json()["mode"] == "legacy"
        assert resident.post("/resident/chats", json={"title": "After explicit rollback"}).status_code == 201
