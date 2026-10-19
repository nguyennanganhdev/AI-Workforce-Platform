"""Real ticket fixtures for a single synthetic business acceptance run.

Only a loopback, explicitly marked owner_pilot_test database is accepted. A run
is idempotent: rerunning its seed never resets tickets already being exercised.
A clean reset is a new run/project/database, never a delete of operational data.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .database import TENANT
from .owner_sandbox import CATEGORY, MARKER, guard
from .sandbox_initialize import initialize
from .v3_resident import ResidentTicketCreate, create_resident_ticket


def fixture_plan(run_id: str, seed: int = 42, scenarios: int = 24, repetitions: int = 3):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", run_id):
        raise ValueError("run_id must be 1-48 lower-case letters, digits, '-' or '_'")
    if not 1 <= scenarios <= 30 or not 3 <= repetitions <= 10:
        raise ValueError("Require 1-30 scenarios and 3-10 repetitions")
    namespace = uuid5(NAMESPACE_URL, f"workforce-business-sandbox/{run_id}/{seed}")
    return [
        {
            "scenario": scenario,
            "repetition": repetition,
            "channel_id": str(uuid5(namespace, f"chat/{scenario}/{repetition}")),
            "idempotency_key": f"sandbox-{run_id}-{seed}-{scenario}-{repetition}",
        }
        for scenario in range(1, scenarios + 1)
        for repetition in range(1, repetitions + 1)
    ]


async def build_fixture(url: str, run_id: str, seed: int = 42,
                        scenarios: int = 24, repetitions: int = 3):
    guard(url)  # Must fail before opening a connection to any other target.
    plan = fixture_plan(run_id, seed, scenarios, repetitions)
    engine = create_async_engine(url.replace("postgresql:", "postgresql+asyncpg:", 1))
    try:
        async with engine.begin() as db:
            marker = (await db.execute(text(
                "select shobj_description(oid,'pg_database') from pg_database "
                "where datname=current_database()"
            ))).scalar_one_or_none()
            if marker != MARKER:
                raise ValueError("Business fixture requires the synthetic sandbox marker")
            await db.execute(text("select pg_advisory_xact_lock(hashtextextended(:run,0))"),
                             {"run": f"business-fixture/{run_id}"})
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"),
                             {"tenant": TENANT})
            resident = (await db.execute(text("""
                select ur.user_id,ur.unit_id,u.building_id,b.site_id,s.domain_id
                from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
                join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
                join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
                where ur.tenant_id=cast(:tenant as uuid) and ur.user_id like 'sim-resident-%'
                  and ur.verification_status='verified' and ur.valid_from<=now()
                  and (ur.valid_to is null or ur.valid_to>now())
                order by ur.user_id,ur.unit_id limit 1
            """), {"tenant": TENANT})).mappings().first()
            staff = (await db.execute(text("""
                select sp.id,sp.user_id from staff_profiles sp
                join staff_specialties ss on ss.staff_id=sp.id and ss.tenant_id=sp.tenant_id
                where sp.tenant_id=cast(:tenant as uuid) and ss.category_id=:category
                  and sp.user_id like 'sim-%' order by sp.user_id
            """), {"tenant": TENANT, "category": CATEGORY})).mappings().all()
            if resident is None or not staff:
                raise ValueError("Initialize the complete synthetic resident/staff sandbox first")
            tickets = []
            for item in plan:
                channel = item["channel_id"]
                await db.execute(text("""
                    insert into channels(id,name,description,tenant_id,kind,created_by)
                    values(:id,:name,'Synthetic acceptance fixture',cast(:tenant as uuid),'reception',:actor)
                    on conflict(id) do nothing
                """), {"id": channel, "name": f"Sandbox {run_id} {item['scenario']}/{item['repetition']}",
                       "tenant": TENANT, "actor": resident["user_id"]})
                await db.execute(text("""
                    insert into channel_memberships(channel_id,user_id,tenant_id)
                    values(:channel,:actor,cast(:tenant as uuid)) on conflict do nothing
                """), {"channel": channel, "actor": resident["user_id"], "tenant": TENANT})
                body = ResidentTicketCreate(
                    domain_id=resident["domain_id"], building_id=resident["building_id"],
                    unit_id=resident["unit_id"], category_id=CATEGORY,
                    title=f"[SIMULATION] Business acceptance {item['scenario']}/{item['repetition']}",
                    description="Synthetic leaking tap in the kitchen; no production service requested.",
                    contact_name="Synthetic resident", contact_phone="0000000000",
                    request_kind="incident", location="Synthetic kitchen",
                    idempotency_key=item["idempotency_key"],
                )
                await create_resident_ticket(channel, body, (db, resident["user_id"]))
                ticket_id = (await db.execute(text("""
                    select id from tickets where channel_id=:channel and requester_user_id=:actor
                      and tenant_id=cast(:tenant as uuid)
                """), {"channel": channel, "actor": resident["user_id"], "tenant": TENANT})).scalar_one()
                # The UUID is the real Domain record, never a transport-only pseudo-ticket.
                UUID(str(ticket_id))
                tickets.append({**item, "ticket_id": str(ticket_id)})
            return {
                "data_mode": "synthetic_test", "run_id": run_id, "seed": seed,
                "tenant_id": TENANT, "resident_user_id": resident["user_id"],
                "staff": [{"staff_id": str(s["id"]), "user_id": s["user_id"]} for s in staff],
                "tickets": tickets, "reset_policy": "new_run_project_and_database",
                "production_changed": False,
            }
    finally:
        await engine.dispose()


async def main():
    folder = Path(os.getenv("SANDBOX_PRIVATE_DIR", "/sandbox"))
    url = os.environ["DATABASE_URL"]
    await initialize(url, folder, os.environ["SANDBOX_RUNTIME_PASSWORD"])
    result = await build_fixture(url, os.environ["SANDBOX_RUN_ID"],
                                 int(os.getenv("SANDBOX_SEED", "42")))
    path = folder / "fixture.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": result["run_id"], "tickets": len(result["tickets"]),
                      "production_changed": False}))


if __name__ == "__main__":
    asyncio.run(main())
