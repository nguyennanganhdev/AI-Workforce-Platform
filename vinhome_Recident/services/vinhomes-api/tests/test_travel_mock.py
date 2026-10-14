"""Real PostgreSQL + MCP + resident decision contract checks. No Agent or external travel/provider calls."""

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_account_administration import door
from test_integration_auth import person
from test_platform_mcp_v2 import BOOTSTRAP, call, rpc, version
from test_platform_mcp_v2 import (
    handed as handed,  # noqa: PLC0414 -- pytest fixture export
)
from test_resident_contract import TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from vinhomes_api import platform
from vinhomes_api.bootstrap import bootstrap
from vinhomes_api.mock_travel import data
from vinhomes_api.platform_access import TOOLS
from vinhomes_api.travel_seed import CATEGORY, load


def transaction(database, action):
    async def run():
        engine = create_async_engine(database["runtime"])
        try:
            async with engine.begin() as db:
                await db.execute(
                    text("select set_config('app.tenant_id',:t,true)"),
                    {"t": str(TENANT)},
                )
                return await action(db)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.fixture
def travel_ticket(database, handed, monkeypatch):
    monkeypatch.setenv("VINHOMES_TRAVEL_MOCK_ENABLED", "1")
    asyncio.run(bootstrap(database["admin"]))
    asyncio.run(load(database["admin"], True))
    ticket, token, _ = handed
    original = sql(database, "select category_id from tickets where id=$1", ticket)[0][
        "category_id"
    ]
    sql(
        database,
        "update tickets set category_id=$2 where id=$1 returning id",
        ticket,
        CATEGORY,
    )
    # Every test starts with a fresh isolated mock inventory. Nothing here targets production.
    sql(database, "delete from travel_mock_bookings returning id")
    sql(database, "delete from travel_mock_intents returning id")
    try:
        yield ticket, token
    finally:
        sql(
            database,
            "update tickets set category_id=$2 where id=$1 returning id",
            ticket,
            original,
        )


def choice(kind):
    future = datetime.now(timezone.utc).date() + timedelta(days=14)
    if kind == "hotel":
        return {
            "hotel_id": "HTL-HCM-001",
            "room_type_id": "DELUXE",
            "check_in": future.isoformat(),
            "check_out": (future + timedelta(days=2)).isoformat(),
            "guests": 1,
            "rooms": 1,
        }
    if kind == "bus":
        trip = data.BUS_TRIPS[0]
        return {
            "trip_id": trip["trip_id"],
            "travel_date": future.isoformat(),
            "seats": 1,
            "pickup_point": trip["pickup_points"][0],
            "dropoff_point": trip["dropoff_points"][0],
        }
    item = data.RESTAURANTS[0]
    return {
        "restaurant_id": item["restaurant_id"],
        "reservation_date": future.isoformat(),
        "reservation_time": item["opening_slots"][0],
        "party_size": 2,
    }


def prepare(
    client,
    database,
    ticket,
    token,
    kind="hotel",
    operation="book",
    selection=None,
    reference=None,
):
    return call(
        client,
        token,
        "vh_travel_prepare",
        {
            "ticket_id": str(ticket),
            "kind": kind,
            "operation": operation,
            "selection": choice(kind) if selection is None else selection,
            "client_reference": reference or str(uuid4()),
            "expected_ticket_version": version(database, ticket),
        },
    )


def publish_approval(database, ticket, prepared):
    approval_id = "travel-test-" + str(uuid4())

    async def publish(db):
        link = (
            (
                await db.execute(
                    text("select * from platform_links where ticket_id=:id"),
                    {"id": ticket},
                )
            )
            .mappings()
            .one()
        )
        await platform.ask_approval(
            db,
            link,
            {
                "approval_id": approval_id,
                "expected_revision": 1,
                **prepared["approval_request"],
            },
        )

    transaction(database, publish)
    return approval_id


def resident_decision(database, ticket, approval, approve=True):
    actor = sql(database, "select requester_user_id from tickets where id=$1", ticket)[
        0
    ]["requester_user_id"]
    with person(database, actor) as client:
        response = client.post(
            "/resident/platform/approvals/" + approval + "/decision",
            json={"approve": approve},
        )
    assert response.status_code == 200, response.text


def commit_args(database, ticket, prepared, approval, reference=None):
    return {
        "ticket_id": str(ticket),
        "intent_id": prepared["intent_id"],
        "approval_id": approval,
        "client_reference": reference or str(uuid4()),
        "expected_ticket_version": version(database, ticket),
    }


@pytest.mark.parametrize("kind", ["hotel", "bus", "restaurant"])
def test_happy_case_requires_resident_consent_persists_retries_and_cancels(
    database, travel_ticket, kind
):
    ticket, token = travel_ticket
    selected = choice(kind)
    field = {
        "hotel": "available_rooms",
        "bus": "available_seats",
        "restaurant": "available_capacity",
    }[kind]
    with door(database) as client:
        before = call(
            client,
            token,
            "vh_travel_availability",
            {"ticket_id": str(ticket), "kind": kind, "selection": selected},
        )["availability"][field]
        proposed = prepare(client, database, ticket, token, kind, selection=selected)
        assert proposed["provider_mode"] == "mock" and not proposed["real_booking"]
        approval = publish_approval(database, ticket, proposed)
        args = commit_args(database, ticket, proposed, approval)
        assert (
            call(client, token, "vh_travel_commit", args, True)["error"]["code"]
            == "TRAVEL_RESIDENT_APPROVAL_REQUIRED"
        )
        resident_decision(database, ticket, approval)
        booked = call(client, token, "vh_travel_commit", args)
        assert booked[
            "status"
        ] == "mock_confirmed" and "customer_phone" not in json.dumps(booked)
        replay = call(client, token, "vh_travel_commit", args)
        assert {
            key: value for key, value in replay.items() if key != "correlation_id"
        } == {key: value for key, value in booked.items() if key != "correlation_id"}
        assert sql(database, "select count(*) n from travel_mock_bookings")[0]["n"] == 1
        for array in (data.HOTEL_BOOKINGS, data.BUS_BOOKINGS, data.RESTAURANT_BOOKINGS):
            array.clear()  # Simulate loss of provider process RAM; inventory must come back from PostgreSQL.
        after = call(
            client,
            token,
            "vh_travel_availability",
            {"ticket_id": str(ticket), "kind": kind, "selection": selected},
        )["availability"][field]
        assert after == before - (2 if kind == "restaurant" else 1)
        listed = call(client, token, "vh_travel_bookings", {"ticket_id": str(ticket)})
        assert listed["bookings"][0]["booking_ref"] == booked["booking_ref"]
        cancel = prepare(
            client,
            database,
            ticket,
            token,
            kind,
            "cancel",
            {
                "booking_ref": booked["booking_ref"],
                "reason": "Test fixture cancellation",
            },
        )
        cancel_approval = publish_approval(database, ticket, cancel)
        resident_decision(database, ticket, cancel_approval)
        cancelled = call(
            client,
            token,
            "vh_travel_commit",
            commit_args(database, ticket, cancel, cancel_approval),
        )
        assert cancelled["status"] == "mock_cancelled"
        restored = call(
            client,
            token,
            "vh_travel_availability",
            {"ticket_id": str(ticket), "kind": kind, "selection": selected},
        )["availability"][field]
        assert restored == before
        notices = sql(
            database,
            "select body from platform_commands where ticket_id=$1 and body ? 'domain_notice_key' and body->>'domain_notice_key' like 'travel-mock:%'",
            ticket,
        )
        assert len(notices) >= 2 and all(
            json.loads(row["body"])["own"] is True for row in notices
        )


def test_platform_cannot_forge_a_resident_decision_or_replace_the_identity(
    database, travel_ticket
):
    ticket, token = travel_ticket
    with door(database) as client:
        proposed = prepare(client, database, ticket, token)
        approval = publish_approval(database, ticket, proposed)
        sql(
            database,
            "update platform_approvals set status='approved' where approval_id=$1 returning approval_id",
            approval,
        )
        args = commit_args(database, ticket, proposed, approval)
        assert (
            call(client, token, "vh_travel_commit", args, True)["error"]["code"]
            == "TRAVEL_RESIDENT_APPROVAL_REQUIRED"
        )
        unsafe = {
            "ticket_id": str(ticket),
            "kind": "hotel",
            "operation": "book",
            "selection": {**choice("hotel"), "customer_phone": "+84000000000"},
            "client_reference": str(uuid4()),
            "expected_ticket_version": version(database, ticket),
        }
        assert (
            call(client, token, "vh_travel_prepare", unsafe, True)["error"]["code"]
            == "TRAVEL_INPUT_INVALID"
        )
        assert sql(database, "select count(*) n from travel_mock_bookings")[0]["n"] == 0


@pytest.mark.parametrize("change", ["expiry", "price", "terms", "hash", "reject"])
def test_changed_expired_or_unapproved_quotes_cannot_commit(
    database, travel_ticket, change
):
    ticket, token = travel_ticket
    with door(database) as client:
        proposed = prepare(client, database, ticket, token)
        approval = publish_approval(database, ticket, proposed)
        resident_decision(database, ticket, approval, change != "reject")
        if change == "expiry":
            sql(
                database,
                "update travel_mock_intents set expires_at=now()-interval '1 second' where id=$1 returning id",
                UUID(proposed["intent_id"]),
            )
        elif change in ("price", "terms"):
            path = (
                ["room_types", "0", "price_per_night"]
                if change == "price"
                else ["cancellation_policy"]
            )
            value = "99999999" if change == "price" else '"Changed mock terms"'
            sql(
                database,
                "update travel_mock_catalog set data=jsonb_set(data,$1::text[],$2::jsonb) where kind='hotel' and service_id='HTL-HCM-001' returning service_id",
                path,
                value,
            )
        elif change == "hash":
            sql(
                database,
                "update platform_approvals set arguments_hash='different' where approval_id=$1 returning approval_id",
                approval,
            )
        result = call(
            client,
            token,
            "vh_travel_commit",
            commit_args(database, ticket, proposed, approval),
            True,
        )
        assert result["error"]["code"] in {
            "TRAVEL_QUOTE_EXPIRED",
            "TRAVEL_QUOTE_CHANGED",
            "TRAVEL_RESIDENT_APPROVAL_REQUIRED",
        }
        assert sql(database, "select count(*) n from travel_mock_bookings")[0]["n"] == 0


def test_travel_tools_are_scoped_and_fail_closed_when_disabled(
    database, travel_ticket, monkeypatch
):
    ticket, token = travel_ticket
    with door(database) as client:
        tools = rpc(client, BOOTSTRAP, "tools/list").json()["result"]["tools"]
        assert {tool["name"] for tool in tools} == set(TOOLS) and len(tools) == 14
        assert not any(
            tool["name"]
            in {"list_customer_bookings", "book_hotel", "calculate_expression"}
            for tool in tools
        )
        assert (
            call(
                client, token, "vh_travel_bookings", {"ticket_id": str(uuid4())}, True
            )["error"]["code"]
            == "TICKET_SCOPE_FORBIDDEN"
        )
        monkeypatch.setenv("VINHOMES_TRAVEL_MOCK_ENABLED", "0")
        assert (
            call(client, token, "vh_travel_catalog", {"ticket_id": str(ticket)}, True)[
                "error"
            ]["code"]
            == "TRAVEL_DISABLED"
        )


def test_travel_ticket_cannot_create_a_physical_staff_work_order(
    database, travel_ticket
):
    ticket, token = travel_ticket
    before = sql(database, "select count(*) n from work_orders")[0]["n"]
    with door(database) as client:
        args = {
            "ticket_id": str(ticket),
            "client_reference": str(uuid4()),
            "description": "Do not create physical work",
            "expected_ticket_version": version(database, ticket),
        }
        assert (
            call(client, token, "vh_work_order_dispatch", args, True)["error"]["code"]
            == "TRAVEL_USE_BOOKING_TOOLS"
        )
        assert (
            call(client, token, "vh_staff_available", {"ticket_id": str(ticket)}, True)[
                "error"
            ]["code"]
            == "TRAVEL_USE_BOOKING_TOOLS"
        )
    assert sql(database, "select count(*) n from work_orders")[0]["n"] == before


def test_prepare_reference_is_idempotent_and_conflicting_content_is_refused(
    database, travel_ticket
):
    ticket, token = travel_ticket
    with door(database) as client:
        reference = str(uuid4())
        first = prepare(client, database, ticket, token, reference=reference)
        repeated = prepare(client, database, ticket, token, reference=reference)
        assert first["intent_id"] == repeated["intent_id"]
        args = {
            "ticket_id": str(ticket),
            "kind": "hotel",
            "operation": "book",
            "selection": {**choice("hotel"), "rooms": 2},
            "client_reference": reference,
            "expected_ticket_version": version(database, ticket),
        }
        assert (
            call(client, token, "vh_travel_prepare", args, True)["error"]["code"]
            == "REFERENCE_CONFLICT"
        )


def test_two_ticket_workflows_cannot_book_the_last_mock_room_twice(
    database, travel_ticket
):
    ticket, token = travel_ticket
    other = sql(
        database,
        "select id,category_id from tickets where id<>$1 and status in ('open','triaging','assigned','in_progress') order by created_at limit 1",
        ticket,
    )[0]
    other_token = "vhm_" + str(uuid4())
    sql(
        database,
        "update tickets set category_id=$2 where id=$1 returning id",
        other["id"],
        CATEGORY,
    )
    sql(
        database,
        """insert into platform_links(ticket_id,tenant_id,channel_id,user_id,management_ref)
        select t.id,t.tenant_id,t.channel_id,t.requester_user_id,m.code from tickets t
        join management_units m on m.id=t.management_unit_id where t.id=$1
        on conflict(ticket_id) do update set status='open' returning ticket_id""",
        other["id"],
    )
    sql(
        database,
        """insert into platform_mcp_grants(tenant_id,ticket_id,management_ref,token_hash,tools,expires_at)
        select tenant_id,ticket_id,management_ref,$2,$3,now()+interval '1 hour' from platform_links where ticket_id=$1 returning id""",
        other["id"],
        hashlib.sha256(other_token.encode()).hexdigest(),
        list(TOOLS),
    )
    sql(
        database,
        "update travel_mock_catalog set data=jsonb_set(data,'{room_types,0,total_rooms}','1'::jsonb) where kind='hotel' and service_id='HTL-HCM-001' returning service_id",
    )
    calls = []
    try:
        with door(database) as client:
            for current, bearer in ((ticket, token), (other["id"], other_token)):
                proposed = prepare(client, database, current, bearer)
                approval = publish_approval(database, current, proposed)
                resident_decision(database, current, approval)
                calls.append(
                    (bearer, commit_args(database, current, proposed, approval))
                )

        def execute(item):
            with door(database) as client:
                response = rpc(
                    client,
                    item[0],
                    "tools/call",
                    {"name": "vh_travel_commit", "arguments": item[1]},
                )
                assert response.status_code == 200
                return response.json()["result"]["structuredContent"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, calls))
        assert sum(result["status"] == "mock_confirmed" for result in results) == 1
        assert (
            sum(
                result.get("error", {}).get("code") == "TRAVEL_SOLD_OUT"
                for result in results
            )
            == 1
        )
        assert sql(database, "select count(*) n from travel_mock_bookings")[0]["n"] == 1
    finally:
        sql(
            database,
            "update tickets set category_id=$2 where id=$1 returning id",
            other["id"],
            other["category_id"],
        )
