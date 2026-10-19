"""Canonical case closure aggregation, on the restricted runtime PostgreSQL role.

Ticket closure is seeded explicitly here; the full staff/QC/consent path belongs
to the Docker browser roundtrip. This regression catches SQL typing and ensures
aggregation cannot close an unfinished ticket or duplicate a confirmation.
"""

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_account_administration import door
from test_platform_customers import link
from test_resident_contract import CATEGORY, TENANT, sql
from test_resident_contract import database as database  # noqa: F401
from vinhomes_api.platform_customers import complete_customer_case


def test_canonical_completion_waits_for_closed_tickets_and_retains_one_receipt(database, monkeypatch):
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    with door(database) as client:
        linked, body = link(client, database, monkeypatch)
        token = client.post("/platform/customer/grants", json={"client_id": body["client_id"],
            "client_secret": body["client_secret"], "link_token": linked["link_token"]}).json()["access_token"]
        headers = {"Authorization": "Bearer " + token, "Idempotency-Key": uuid4().hex}
        apartment = client.get("/platform/customer/me", headers=headers).json()["apartments"][0]["id"]
        response = client.post("/platform/customer/requests", headers=headers, json={"platform_case_id": uuid4().hex,
            "platform_workflow_id": uuid4().hex, "request": {"apartmentId": apartment, "description": "Vòi nước cần nhân viên kiểm tra.",
                "location": {"description": "Bếp trong căn hộ"}, "photoIds": []}})
        assert response.status_code == 201, response.text
        case = response.json()
        response = client.post(f'/platform/customer/requests/{case["id"]}/tickets', headers={**headers, "Idempotency-Key": uuid4().hex},
            json={"category_id": CATEGORY, "expected_version": case["version"]})
        assert response.status_code == 201, response.text
        ticket_id = response.json()["ticket_id"]

    async def aggregate():
        engine = create_async_engine(database["runtime"])
        try:
            async with engine.begin() as db:
                await db.execute(text("SELECT set_config('app.tenant_id',:tenant,true),set_config('app.user_id','local-v3-resident',true)"), {"tenant": str(TENANT)})
                await complete_customer_case((db, "local-v3-resident"), UUID(case["id"]))
        finally:
            await engine.dispose()
    asyncio.run(aggregate())
    assert sql(database, "SELECT status FROM vh_resident_cases WHERE id=$1", UUID(case["id"]))[0]["status"] == "processing"
    sql(database, "UPDATE tickets SET status='closed',closed_at=now() WHERE id=$1", UUID(ticket_id))
    asyncio.run(aggregate())
    first = sql(database, "SELECT status,version,current_resolution_id FROM vh_resident_cases WHERE id=$1", UUID(case["id"]))[0]
    assert first["status"] == "completed" and first["current_resolution_id"]
    asyncio.run(aggregate())
    assert sql(database, "SELECT status,version,current_resolution_id FROM vh_resident_cases WHERE id=$1", UUID(case["id"]))[0] == first
    assert sql(database, "SELECT count(*) AS n FROM vh_resident_resolution_responses WHERE case_id=$1 AND decision='confirm'", UUID(case["id"]))[0]["n"] == 1
