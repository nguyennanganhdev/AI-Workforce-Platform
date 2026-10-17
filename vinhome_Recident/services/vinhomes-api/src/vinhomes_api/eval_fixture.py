"""Fresh handed-over tickets for one platform agent evaluation, synthetic sandbox only.

Each ticket is created through the normal resident intake, so the platform tools
read and change a real Domain record. Its handover never reaches the platform:
the start command is marked done in the same transaction and the link is
closed, so the sync worker neither sends commands nor reports progress for it.
The platform then asks for a ticket-scoped grant exactly as at runtime.
"""

import json
import os
import re
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text

from .owner_sandbox import CATEGORY, MARKER
from .platform import TENANT
from .v3_resident import ResidentTicketCreate, create_resident_ticket

ENABLED_ENV = "VINHOMES_API_EVAL_FIXTURES"


class EvalFixtureRefused(Exception):
    """The database or configuration is not an evaluation sandbox."""


def enabled() -> bool:
    return os.getenv(ENABLED_ENV, "").strip().lower() == "enabled"


async def create_eval_tickets(db, run_id: str, count: int) -> list[dict]:
    """Return `count` tickets for run `run_id`; repeating a run returns the same tickets."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", run_id) or not 1 <= count <= 20:
        raise ValueError("run_id must be 1-64 lower-case letters, digits, '-' or '_', count 1-20")
    marker = (await db.execute(text(
        "select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"
    ))).scalar_one_or_none()
    if marker != MARKER:
        raise EvalFixtureRefused("Evaluation fixtures require the synthetic sandbox database")
    resident = (await db.execute(text(f"""
        select ur.user_id,ur.unit_id,u.building_id,s.domain_id
        from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
        where ur.tenant_id={TENANT} and ur.user_id like 'sim-resident-%'
          and ur.verification_status='verified' and ur.valid_from<=now()
          and (ur.valid_to is null or ur.valid_to>now())
        order by ur.user_id,ur.unit_id limit 1
    """))).mappings().first()
    if resident is None:
        raise EvalFixtureRefused("Initialize the synthetic resident sandbox first")
    namespace = uuid5(NAMESPACE_URL, f"workforce-agent-eval/{run_id}")
    tickets = []
    for n in range(1, count + 1):
        channel = str(uuid5(namespace, f"chat/{n}"))
        await db.execute(text(f"""
            insert into channels(id,name,description,tenant_id,kind,created_by)
            values(:id,:name,'Synthetic agent evaluation',{TENANT},'reception',:actor)
            on conflict(id) do nothing
        """), {"id": channel, "name": f"Agent eval {run_id} #{n}", "actor": resident["user_id"]})
        await db.execute(text(f"""
            insert into channel_memberships(channel_id,user_id,tenant_id)
            values(:channel,:actor,{TENANT}) on conflict do nothing
        """), {"channel": channel, "actor": resident["user_id"]})
        body = ResidentTicketCreate(
            domain_id=resident["domain_id"], building_id=resident["building_id"],
            unit_id=resident["unit_id"], category_id=CATEGORY,
            title=f"[SIMULATION] Vòi bếp rò nước #{n}",
            description="Vòi nước bồn rửa bếp rò rỉ liên tục, nước đọng dưới tủ. Dữ liệu mô phỏng cho kiểm thử agent.",
            contact_name="Cư dân mô phỏng", contact_phone="0000000000",
            request_kind="incident", location="Bếp căn hộ mô phỏng",
            idempotency_key=f"agent-eval-{run_id}-{n}",
        )
        await create_resident_ticket(channel, body, (db, resident["user_id"]))
        ticket_id = str((await db.execute(text(f"""
            select id from tickets where channel_id=:channel and requester_user_id=:actor and tenant_id={TENANT}
        """), {"channel": channel, "actor": resident["user_id"]})).scalar_one())
        # Never hand the synthetic ticket to the platform: mark the start
        # command delivered and close the link before this transaction commits.
        await db.execute(text(f"""
            update platform_commands set status='done',result=cast(:result as jsonb)
            where ticket_id=:ticket and tenant_id={TENANT} and status='pending'
        """), {"ticket": ticket_id, "result": json.dumps({"eval_fixture": run_id})})
        closed = (await db.execute(text(f"""
            update platform_links set state='closed',next_action='none'
            where ticket_id=:ticket and tenant_id={TENANT} and status='pending' returning ticket_id
        """), {"ticket": ticket_id})).first()
        start = (await db.execute(text(f"""
            select id,body->>'text' as handover from platform_commands
            where ticket_id=:ticket and tenant_id={TENANT} and kind='start_workflow'
        """), {"ticket": ticket_id})).mappings().first()
        if closed is None or start is None:
            raise EvalFixtureRefused("The sandbox management unit is not connected to the platform; no handover was created")
        tickets.append({
            "kind": "incident_open", "ticket_id": ticket_id,
            "external_request_id": str(start["id"]), "handover_text": start["handover"],
            "summary": "Sự cố kỹ thuật mới: vòi bếp rò nước, chưa giao thợ.",
        })
    return tickets
