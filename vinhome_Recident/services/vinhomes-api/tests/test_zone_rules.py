"""Limits that differ from one zone to another are data (migration 0012): the towers keep the standard ones, the villa zone sets its own."""
import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_integration_auth import person
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api.jobs import sweep_tenant
from vinhomes_api.mock_data import build

AN, DUNG, MINH = "mock-an", "mock-dung", "mock-minh"
TOWER, VILLA = "S1.01-1201", "HA2.05"


@pytest.fixture(scope="module", autouse=True)
def world(database):
    asyncio.run(build(database["admin"], "test", 42))


def home(database, code):
    return sql(database, "select id from units where tenant_id=$1 and code=$2", TENANT, code)[0]["id"]


def rules(database, who, code):
    with person(database, who) as resident:
        answer = resident.get(f"/resident/units/{home(database, code)}/rules")
        assert answer.status_code == 200, answer.text
        return answer.json()


def in_hours(hours):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_a_zone_that_sets_nothing_gets_the_standard_rules_and_the_villa_zone_gets_its_own(database):
    tower = rules(database, AN, TOWER)
    assert tower == {"visits": {"maxWaiting": 10, "maxDaysAhead": 30, "maxHours": 72, "noApprovalPurposes": ["family_visit", "delivery"],
                                "noApprovalMaxGuests": 5, "earlyEntryMinutes": 15},
                     "cards": {"resident": 6, "vehicle": 4}, "amenities": {"paymentHoldMinutes": 15}}                    # 1: the standard rules
    villa = rules(database, DUNG, VILLA)
    assert villa["cards"] == {"resident": 8, "vehicle": 6}                                                              # 2: what the villa zone sets
    assert (villa["visits"]["maxWaiting"], villa["visits"]["maxHours"], villa["visits"]["noApprovalMaxGuests"]) == (20, 96, 8)
    assert villa["visits"]["maxDaysAhead"] == 30 and villa["amenities"]["paymentHoldMinutes"] == 15                      # 3: and inherits the rest


def test_the_rules_decide_what_a_resident_may_announce(database):
    group = {"guest_name": "Nhóm bạn", "guest_count": 8, "purpose": "family_visit", "visit_from": in_hours(2), "visit_to": in_hours(6)}
    long_stay = {**group, "guest_count": 2, "visit_to": in_hours(2 + 80)}
    with person(database, AN) as c:
        made = c.post(f"/resident/units/{home(database, TOWER)}/visitor-passes", json=group)
        assert made.status_code == 201 and made.json()["status"] == "pending_approval"                                    # 1: 8 people wait for the desk in a tower
        assert c.post(f"/resident/units/{home(database, TOWER)}/visitor-passes", json=long_stay).status_code == 422       # 2: 80 hours is too long there
    with person(database, DUNG) as c:
        made = c.post(f"/resident/units/{home(database, VILLA)}/visitor-passes", json=group)
        assert made.status_code == 201 and made.json()["status"] == "approved"                                            # 3: in the villa zone 8 people need no approval
        assert c.post(f"/resident/units/{home(database, VILLA)}/visitor-passes", json=long_stay).status_code == 201       # 4: and 80 hours is fine


def test_a_home_holds_as_many_cards_as_its_zone_allows(database):
    villa = home(database, VILLA)
    live = sql(database, "select count(*) as n from access_cards where unit_id=$1 and kind='resident' and status in ('pending_issue','active','suspended')", villa)[0]["n"]
    for n in range(max(0, 6 - live)):                                    # six resident cards: the standard limit is reached
        sql(database, "insert into access_cards(tenant_id,card_no,kind,unit_id,status) values($1,$2,'resident',$3,'pending_issue') returning id", TENANT, f"C-ZONE-A{n}", villa)

    def ask():
        with person(database, DUNG) as c:
            request = c.post(f"/resident/units/{villa}/service-requests", json={"kind": "card_issue", "details": {"card_kind": "resident"}}).json()["id"]
            c.post(f"/resident/service-requests/{request}/submit")
        with person(database, MINH) as m:
            for to in ("in_review", "approved"):
                m.post(f"/operations/service-requests/{request}/transition", json={"to_status": to})
            return m.post(f"/operations/service-requests/{request}/transition", json={"to_status": "fulfilled"})

    assert ask().status_code == 200                                                                                     # 1: a seventh card: the villa zone allows 8
    assert ask().status_code == 200                                                                                     # 2: an eighth
    refused = ask()
    assert refused.status_code == 409 and "8 resident cards" in refused.text                                            # 3: a ninth is refused, with the zone's number


def test_a_tenant_wide_rule_is_inherited_by_zones_that_do_not_set_it_and_a_zone_still_wins(database):
    sql(database, "insert into zone_settings(tenant_id,zone_id,visit_early_minutes,card_limit_vehicle,note) values($1,null,40,3,'toàn khu') returning id", TENANT)
    try:
        tower, villa = rules(database, AN, TOWER), rules(database, DUNG, VILLA)
        assert tower["visits"]["earlyEntryMinutes"] == 40 and tower["cards"]["vehicle"] == 3                             # 1: the tower zone has no row: the tenant's
        assert villa["visits"]["earlyEntryMinutes"] == 40 and villa["cards"]["vehicle"] == 6                             # 2: the villa zone's own number wins; the rest is inherited
    finally:
        sql(database, "delete from zone_settings where tenant_id=$1 and zone_id is null returning id", TENANT)
    assert rules(database, AN, TOWER)["cards"]["vehicle"] == 4                                                           # 3: without the row, back to the standard


def test_a_rule_that_makes_no_sense_is_refused_and_a_zone_has_one_row(database):
    zone = sql(database, "select zone_id from units where id=$1", home(database, VILLA))[0]["zone_id"]
    for column, value in (("visit_max_waiting", 0), ("visit_max_hours", 0), ("card_limit_vehicle", -1), ("amenity_payment_hold_minutes", 0)):
        with pytest.raises(asyncpg.CheckViolationError):
            sql(database, f"insert into zone_settings(tenant_id,zone_id,{column}) values($1,$2,{value}) returning id", TENANT, sql(database, "select id from zones where id<>$1 limit 1", zone)[0]["id"])
    with pytest.raises(asyncpg.CheckViolationError):
        sql(database, "insert into zone_settings(tenant_id,zone_id,visit_auto_approve_purposes) values($1,null,ARRAY['nonsense']) returning id", TENANT)
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(database, "insert into zone_settings(tenant_id,zone_id,card_limit_vehicle) values($1,$2,5) returning id", TENANT, zone)


async def sweep_once(database):
    engine = create_async_engine(database["admin"].replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": str(TENANT)})
            return await sweep_tenant(db)
    finally:
        await engine.dispose()


def test_an_unpaid_booking_is_released_after_the_hold_its_zone_sets(database):
    amenity = sql(database, "select id,zone_id from amenities where tenant_id=$1 and price>0 and zone_id is not null order by code limit 1", TENANT)[0]
    sql(database, """insert into zone_settings(tenant_id,zone_id,amenity_payment_hold_minutes) values($1,$2,30)
        on conflict (tenant_id,zone_id) where zone_id is not null do update set amenity_payment_hold_minutes=30 returning id""", TENANT, amenity["zone_id"])
    base = datetime.now(timezone.utc) + timedelta(days=40)
    ids = []
    for n, minutes_ago in enumerate((20, 40)):
        ids.append(sql(database, """insert into amenity_bookings(tenant_id,code,amenity_id,unit_id,booked_by_user_id,start_at,end_at,status,total_amount,created_at)
            values($1,$2,$3,$4,'mock-an',$5,$6,'pending_payment',50000,now()-make_interval(mins=>$7)) returning id""",
                       TENANT, f"BK-ZONE-{n}", amenity["id"], home(database, TOWER), base + timedelta(hours=2 * n), base + timedelta(hours=2 * n + 1), minutes_ago)[0]["id"])
    counts = asyncio.run(sweep_once(database))
    after = [sql(database, "select status from amenity_bookings where id=$1", booking)[0]["status"] for booking in ids]
    assert after == ["pending_payment", "expired"], counts                                                              # 20 minutes is within a 30-minute hold, 40 is past it
    assert counts["bookings_expired"] >= 1
