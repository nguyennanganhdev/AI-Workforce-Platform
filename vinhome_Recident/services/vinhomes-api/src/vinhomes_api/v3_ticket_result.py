"""Read the authorized resident ticket snapshot after intake or idempotent retry."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_agent_results import agent_result


async def resident_ticket_result(
    db: AsyncConnection, actor_id: str, ticket_id: UUID, *, replayed: bool
) -> dict[str, object]:
    row = (
        (
            await db.execute(
                text("""
        select t.id,t.code,t.channel_id,t.title,t.description,t.status,t.priority,
          t.severity,t.request_kind,t.version,t.created_at,t.updated_at,
          t.contact_name,t.contact_phone,t.unit_id,t.building_id,t.domain_id,
          t.category_id,t.management_unit_id,t.address_snapshot,
          t.response_due_at,t.resolution_due_at,t.triage_status,
          b.name as building_name,u.code as unit_code,d.name as domain_name,
          c.name as category_name,c.code as category_code,
          mu.name as management_name,mu.code as management_code
        from tickets t
        join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
        join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id
        join domains d on d.id=t.domain_id and d.tenant_id=t.tenant_id
        join service_categories c on c.id=t.category_id and c.tenant_id=t.tenant_id
        join management_units mu on mu.id=t.management_unit_id and mu.tenant_id=t.tenant_id
        where t.id=:id and t.requester_user_id=:actor
    """),
                {"id": ticket_id, "actor": actor_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Resident ticket not found")
    ticket = dict(row)
    plans = (
        (
            await db.execute(
                text("""
        select id,status,version,title,estimated_amount,created_at
        from vh_ticket_plans where ticket_id=:id order by created_at desc,id
    """),
                {"id": ticket_id},
            )
        )
        .mappings()
        .all()
    )
    works = (
        (
            await db.execute(
                text("""
        select id,description,status,version,category_id,required,completed_at
        from work_orders where ticket_id=:id order by created_at,id
    """),
                {"id": ticket_id},
            )
        )
        .mappings()
        .all()
    )
    linked = (
        (
            await db.execute(
                text("""
        select f.id,f.original_name,f.status,tf.purpose
        from ticket_files tf join files f on f.id=tf.file_id and f.tenant_id=tf.tenant_id
        where tf.ticket_id=:id order by f.created_at,f.id
    """),
                {"id": ticket_id},
            )
        )
        .mappings()
        .all()
    )
    available = (
        (
            await db.execute(
                text("""
        select f.id,f.original_name from files f
        where f.channel_id=:channel and f.uploaded_by=:actor and f.status='ready'
          and exists (select 1 from messages m where m.channel_id=f.channel_id
            and m.tenant_id=f.tenant_id and m.body->'fileIds' ? f.id::text)
        order by f.created_at,f.id
    """),
                {"channel": ticket["channel_id"], "actor": actor_id},
            )
        )
        .mappings()
        .all()
    )
    deliveries = (
        (
            await db.execute(
                text("""
        select nd.status,count(*) as count from notification_deliveries nd
        join ticket_events e on e.id=nd.ticket_event_id and e.tenant_id=nd.tenant_id
        where e.ticket_id=:id and e.event_type='ticket.created' group by nd.status
    """),
                {"id": ticket_id},
            )
        )
        .mappings()
        .all()
    )
    linked_ids = {r["id"] for r in linked}
    result = {
        **{
            key: ticket[key]
            for key in ("id", "code", "channel_id", "status", "version")
        },
        "creationOutcome": "replayed" if replayed else "created",
        "ticket": {
            key: value
            for key, value in ticket.items()
            if key
            not in {
                "building_name",
                "unit_code",
                "domain_name",
                "category_name",
                "category_code",
                "management_name",
                "management_code",
            }
        },
        "location": {
            "unitId": ticket["unit_id"],
            "unitCode": ticket["unit_code"],
            "buildingId": ticket["building_id"],
            "buildingName": ticket["building_name"],
            "domainId": ticket["domain_id"],
            "domainName": ticket["domain_name"],
        },
        "category": {
            "id": ticket["category_id"],
            "name": ticket["category_name"],
            "code": ticket["category_code"],
        },
        "managementDestination": {
            "id": ticket["management_unit_id"],
            "name": ticket["management_name"],
            "code": ticket["management_code"],
        },
        "plans": [dict(r) for r in plans],
        "workOrders": [dict(r) for r in works],
        "linkedImages": [dict(r) for r in linked],
        "conversationImages": {
            "items": [dict(r) for r in available],
            "unattachedFileIds": [
                r["id"] for r in available if r["id"] not in linked_ids
            ],
        },
        "managementNotification": {
            "deliveryCounts": [dict(r) for r in deliveries],
            "meaning": "Trạng thái thông báo trong database, không xác nhận BQL đã đọc hoặc nhân viên đã nhận việc.",
        },
    }
    return agent_result("create_ticket", result, {"ticket_id": ticket_id})
