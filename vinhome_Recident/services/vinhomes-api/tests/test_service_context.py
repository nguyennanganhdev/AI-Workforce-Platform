"""Scoped business data/MCP, role checks and safe security dispatch; no Agent/provider calls."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from test_account_administration import door
from test_owner_sandbox import (
    database as base_database,  # noqa: F401 -- fixture dependency
)
from test_owner_sandbox import person
from test_platform_mcp_v2 import BOOTSTRAP, call, rpc, version
from test_platform_tools import hand_over
from test_resident_contract import sql
from vinhomes_api.bootstrap import DOMAIN
from vinhomes_api.owner_sandbox import uid
from vinhomes_api.owner_sandbox_business import extend
from vinhomes_api.platform_access import TOOLS


@pytest.fixture(scope="module")
def database(base_database):  # noqa: F811 -- pytest resolves the imported fixture by name
    result = asyncio.run(extend(base_database["admin"]))
    assert len(result["credentials"]) == 6
    base_database["credentials"].extend(result["credentials"])
    assert asyncio.run(extend(base_database["admin"]))["idempotent_replay"]
    return base_database


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", "http://platform.invalid")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", BOOTSTRAP)
    monkeypatch.setenv("VINHOMES_API_MCP_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("VINHOMES_API_EMBEDDING_API_KEY", "")


def handed(database, user="sim-resident-1", category=None):
    with person(database, user) as c:
        _, ticket = hand_over(
            c,
            **(
                {
                    "category": category,
                    "words": "MÔ PHỎNG: tiếng ồn ở hành lang",
                    "item": "tiếng ồn",
                    "symptom": "ồn",
                }
                if category
                else {}
            ),
        )
    command = sql(
        database,
        "select id from platform_commands where ticket_id=$1 and kind='start_workflow'",
        UUID(ticket),
    )[0]["id"]
    with door(database) as c:
        result = c.post(
            "/platform/mcp-grants",
            headers={"Authorization": "Bearer " + BOOTSTRAP},
            json={
                "ticket_id": ticket,
                "external_request_id": str(command),
                "workflow_id": "fixture-" + ticket,
                "grant_request_id": str(uuid4()),
                "tools": list(TOOLS),
                "ttl_seconds": 3600,
            },
        )
        assert result.status_code == 200
    return ticket, result.json()["bearer_token"]


def test_business_data_is_consistent_idempotent_and_accounts_sign_in(database):
    counts = {
        "users": 11,
        "accounts": 11,
        "staff_profiles": 8,
        "staff_shifts": 24,
        "vehicles": 2,
        "access_cards": 4,
        "visitor_passes": 2,
        "debit_notes": 4,
        "debit_note_lines": 4,
        "amenities": 2,
        "amenity_bookings": 2,
        "construction_policies": 1,
        "construction_permits": 2,
        "service_requests": 2,
        "domain_service_catalog": 10,
    }
    for table, count in counts.items():
        assert sql(database, "select count(*) as n from " + table)[0]["n"] == count
    assert (
        sql(
            database,
            "select count(*) as n from scoped_user_roles where role_code='management'",
        )[0]["n"]
        == 0
    )
    for account in database["credentials"]:
        with door(database) as c:
            assert (
                c.post(
                    "/auth/login",
                    json={
                        "identifier": account["email"],
                        "password": account["password"],
                    },
                ).status_code
                == 200
            )


def test_resident_form_hands_over_to_platform_once_without_bql_plan(database):
    with person(database, "sim-resident-1") as c:
        channel = c.post(
            "/resident/chats", json={"title": "Synthetic form handover"}
        ).json()["id"]
        headers = {"Idempotency-Key": str(uuid4())}
        response = c.post(
            f"/resident/chats/{channel}/tickets",
            headers=headers,
            json={
                "domain_id": str(DOMAIN),
                "building_id": str(uid("building", "SIM-OP1-TOWER")),
                "unit_id": str(uid("unit", "SIM-UNIT-001")),
                "category_id": "33333333-3333-5333-a333-333333333333",
                "title": "Synthetic form request",
                "description": "Synthetic light inspection",
                "contact_name": "Synthetic resident",
                "contact_phone": "+12025550101",
                "request_kind": "service_request",
                "location": "Synthetic living room",
            },
        )
        assert response.status_code == 201, response.text
        ticket = UUID(response.json()["id"])
        assert (
            sql(
                database,
                "select count(*) as n from platform_commands where ticket_id=$1 and kind='start_workflow'",
                ticket,
            )[0]["n"]
            == 1
        )
        assert not sql(
            database,
            "select id from ticket_events where ticket_id=$1 and payload->>'requiresPlan'='true'",
            ticket,
        )


def test_sandbox_session_cookie_does_not_replace_other_local_domain_sessions(
    database, monkeypatch
):
    monkeypatch.setenv("VINHOMES_API_SESSION_NAMESPACE", "local_business_sandbox")
    account = database["credentials"][0]
    with door(database) as c:
        response = c.post(
            "/auth/login",
            json={"identifier": account["email"], "password": account["password"]},
        )
        assert response.status_code == 200
        assert "vinhomes_session_local_business_sandbox" in response.cookies
        assert "vinhomes_session" not in response.cookies
        assert c.get("/auth/session").status_code == 200
        assert c.post("/auth/logout").status_code == 200
        assert c.get("/auth/session").status_code == 401


def test_context_seven_sections_uses_resident_rights_and_masks_private_fields(database):
    first, token = handed(database)
    second, other = handed(database, "sim-resident-2")
    with door(database) as c:
        assert len(rpc(c, BOOTSTRAP, "tools/list").json()["result"]["tools"]) == 16
        for section, key, count in (
            ("cards", "cards", 2),
            ("visitors", "visits", 1),
            ("amenities", "amenities", 2),
            ("renovation", "permits", 1),
            ("service_requests", "requests", 1),
            ("services", "services", 10),
        ):
            result = call(
                c, token, "vh_service_context", {"ticket_id": first, "section": section}
            )
            assert result["read_only"] and result["data_mode"] == "synthetic_test"
            assert len(result[key]) == count
            encoded = str(result)
            assert (
                "guest_phone" not in encoded
                and "qr_token" not in encoded
                and "@op1-sandbox.test" not in encoded
            )
            if section == "cards":
                assert all(
                    not card["card_no"].startswith("SIM-") for card in result["cards"]
                )
        assert (
            call(
                c,
                token,
                "vh_service_context",
                {"ticket_id": first, "section": "billing"},
            )["outstanding"]
            == 160000
        )
        assert (
            call(
                c,
                other,
                "vh_service_context",
                {"ticket_id": second, "section": "billing"},
            )["outstanding"]
            == 270000
        )
        assert (
            call(
                c,
                token,
                "vh_service_context",
                {"ticket_id": second, "section": "cards"},
                True,
            )["error"]["code"]
            == "TICKET_SCOPE_FORBIDDEN"
        )
    # Current residency/financial rights are rechecked, not trusted from the old grant.
    sql(
        database,
        "update unit_residents set relation='household' where user_id='sim-resident-1'",
    )
    try:
        with door(database) as c:
            assert (
                call(
                    c,
                    token,
                    "vh_service_context",
                    {"ticket_id": first, "section": "billing"},
                    True,
                )["status"]
                == "failed"
            )
    finally:
        sql(
            database,
            "update unit_residents set relation='owner' where user_id='sim-resident-1'",
        )


def test_amenity_availability_is_scoped_and_never_reserves(database):
    ticket, token = handed(database)
    date = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    with door(database) as c:
        places = call(
            c,
            token,
            "vh_service_context",
            {"ticket_id": ticket, "section": "amenities"},
        )
        result = call(
            c,
            token,
            "vh_amenity_availability",
            {
                "ticket_id": ticket,
                "amenity_ref": places["amenities"][0]["amenity_ref"],
                "date": date,
            },
        )
        assert result["bookable"] and result["areas"]
        assert (
            call(
                c,
                token,
                "vh_amenity_availability",
                {"ticket_id": ticket, "amenity_ref": str(uuid4()), "date": date},
                True,
            )["error"]["code"]
            == "AMENITY_SCOPE_FORBIDDEN"
        )
    assert sql(database, "select count(*) as n from amenity_bookings")[0]["n"] == 2


def test_platform_dispatches_non_emergency_security_but_emergencies_need_escalation(
    database,
):
    category = str(
        sql(database, "select id from service_categories where code='security'")[0][
            "id"
        ]
    )
    ticket, token = handed(database, category=category)
    with door(database) as c:
        snapshot = call(c, token, "vh_ticket_get", {"ticket_id": ticket})
        assert snapshot["policy"]["actions"]["vh_work_order_dispatch"]["allowed"]
        result = call(
            c,
            token,
            "vh_work_order_dispatch",
            {
                "ticket_id": ticket,
                "client_reference": str(uuid4()),
                "description": "MÔ PHỎNG: kiểm tra tiếng ồn",
                "expected_ticket_version": snapshot["ticket_version"],
            },
        )
        assert result["status"] == "pending" and "security" in result["offered_to"]
    emergency, token = handed(database, category=category)
    sql(
        database,
        "update tickets set is_emergency=true,priority='critical',severity='critical' where id=$1",
        UUID(emergency),
    )
    with door(database) as c:
        result = call(
            c,
            token,
            "vh_work_order_dispatch",
            {
                "ticket_id": emergency,
                "client_reference": str(uuid4()),
                "description": "MÔ PHỎNG: phải chuyển cấp",
                "expected_ticket_version": version(database, UUID(emergency)),
            },
            True,
        )
        assert result["error"]["code"] == "EMERGENCY_REQUIRES_ESCALATION"
    assert (
        sql(
            database,
            "select count(*) as n from work_orders where ticket_id=$1",
            UUID(emergency),
        )[0]["n"]
        == 0
    )
