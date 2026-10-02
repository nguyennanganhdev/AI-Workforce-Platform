"""Transactional Case intake and public projection on the existing V3 database."""

import json
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from .resident_contract import (
    TENANT, CreateRequest, RequestSummary, RequestView, digest, fail,
    encode_cursor, decode_cursor,
)

# The apartment is an authorization scope, never a client-supplied identity.
RESIDENCE = """
 select u.id,u.code,b.id as building_id,b.name as building_name,b.site_id,b.zone_id,
        s.name as site_name,s.domain_id
 from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
 join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
 join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
 join domains d on d.id=s.domain_id and d.tenant_id=s.tenant_id
 where ur.user_id=:actor and ur.verification_status='verified'
   and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
   and u.status='active' and b.status='active' and s.status='active' and d.status='active'
   and ur.tenant_id=""" + TENANT

OWNER = """c.requester_user_id=:actor and exists (
 select 1 from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
 join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
 join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
 join domains d on d.id=s.domain_id and d.tenant_id=s.tenant_id
 where ur.unit_id=c.unit_id and ur.user_id=:actor and ur.tenant_id=c.tenant_id
   and ur.verification_status='verified' and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
   and u.status='active' and b.status='active' and s.status='active' and d.status='active')"""

MANAGEMENT = """(:admin or exists (
 select 1 from scoped_user_roles r
 join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
 join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
 where m.user_id=:actor and m.status='active' and r.role_code='management'
   and r.tenant_id=c.tenant_id and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
   and (s.kind='tenant' or (s.kind='site' and s.site_id=c.site_id)
     or (s.kind='building' and s.building_id=c.building_id)
     or (s.kind='zone' and s.zone_id=(select zone_id from buildings where id=c.building_id))
     or (s.kind='management' and exists (
       select 1 from management_coverage mc join access_scopes coverage on coverage.id=mc.scope_id and coverage.tenant_id=mc.tenant_id
       where mc.management_unit_id=s.management_unit_id and mc.tenant_id=c.tenant_id
         and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
         and (coverage.kind='tenant' or (coverage.kind='site' and coverage.site_id=c.site_id)
          or (coverage.kind='building' and coverage.building_id=c.building_id)
          or (coverage.kind='zone' and coverage.zone_id=(select zone_id from buildings where id=c.building_id))))))))"""

# Version advances for either public Case commands or canonical domain changes.
# A publication names the exact linked ticket versions. Any domain event invalidates
# the publication immediately, including before the next polling GET.
PROJECTION = """
 select c.*, c.version+coalesce(link.version,0) as public_version,
        greatest(c.updated_at,link.updated_at) as public_updated_at,
        coalesce(link.basis,'{}'::jsonb) as basis_versions,
        case when c.status='completed' then 'completed'
          when c.status='confirmation' and r.basis_versions=coalesce(link.basis,'{}'::jsonb) then 'confirmation'
          when c.status in ('processing','confirmation') then 'processing'
          else 'received' end as public_status,
        r.summary as resolution_summary,r.published_at
 from vh_resident_cases c
 left join lateral (
   select sum(t.version) as version,max(t.updated_at) as updated_at,
          jsonb_object_agg(t.id::text,t.version) as basis
   from vh_resident_case_tickets l join tickets t on t.id=l.ticket_id and t.tenant_id=l.tenant_id
   where l.case_id=c.id and l.tenant_id=c.tenant_id
 ) link on true
 left join vh_resident_resolutions r on r.id=c.current_resolution_id and r.tenant_id=c.tenant_id
 where c.tenant_id=""" + TENANT


async def residence(db, actor: str, apartment_id: UUID):
    row = (await db.execute(text(RESIDENCE + " and u.id=:unit"), {"actor": actor, "unit": apartment_id})).mappings().first()
    if row is None:
        fail(403, "APARTMENT_ACCESS_DENIED", "Bạn chưa có quyền sử dụng căn hộ này.")
    return dict(row)


async def case_row(scope, case_id: UUID, *, operations: bool = False):
    predicate = MANAGEMENT if operations else OWNER
    params = {"actor": scope[1], "id": case_id, "admin": bool(scope[2]) if operations else False}
    row = (await scope[0].execute(text(PROJECTION + f" and c.id=:id and {predicate}"), params)).mappings().first()
    if row is None:
        fail(404, "REQUEST_NOT_FOUND", "Không tìm thấy hồ sơ.")
    return dict(row)


async def lock_case(scope, case_id: UUID, *, operations=False, extra_ticket: UUID | None = None):
    # All commands lock source tickets in UUID order before locking the Case.
    # Domain commands already serialize against the same ticket rows.
    await scope[0].execute(text("select pg_advisory_xact_lock(:lock)"),
                          {"lock": int(digest(["case", str(case_id)])[:16], 16) - (1 << 63)})
    await case_row(scope, case_id, operations=operations)
    await scope[0].execute(text(f"""select t.id from tickets t where t.tenant_id={TENANT}
      and (t.id=cast(:extra as uuid) or exists(select 1 from vh_resident_case_tickets l where l.ticket_id=t.id and l.tenant_id=t.tenant_id and l.case_id=:case))
      order by t.id for update of t"""), {"extra": extra_ticket, "case": case_id})
    await scope[0].execute(text(f"select id from vh_resident_cases where id=:id and tenant_id={TENANT} for update"), {"id": case_id})
    # Linking is serialized on the Case; recheck all source rows after its lock.
    await scope[0].execute(text(f"""select t.id from tickets t join vh_resident_case_tickets l on l.ticket_id=t.id and l.tenant_id=t.tenant_id
        where l.case_id=:case and l.tenant_id={TENANT} order by t.id for update of t"""), {"case": case_id})
    return await case_row(scope, case_id, operations=operations)


def summary(row) -> dict:
    return RequestSummary(id=str(row["id"]), code=row["code"], title=row["title"], status=row["public_status"],
                          createdAt=row["created_at"], updatedAt=row["public_updated_at"], version=row["public_version"]).model_dump(mode="json")


async def public_detail(scope, row, request: Request, events_cursor: str | None = None) -> dict:
    from .resident_photos import photo_dto
    db = scope[0]
    case_id = row["id"]
    cursor_scope = ["events", str(request.app.state.settings.tenant_id), scope[1], str(case_id)]
    at, event_id = decode_cursor(request, cursor_scope, events_cursor)
    events = list((await db.execute(text(f"""select id,label,note,occurred_at from vh_resident_public_events
      where case_id=:case and tenant_id={TENANT}
        and (cast(:at as timestamptz) is null or (occurred_at,id)>(cast(:at as timestamptz),cast(:id as uuid)))
      order by occurred_at,id limit 51"""), {"case": case_id, "at": at, "id": event_id})).mappings())
    next_cursor = encode_cursor(request, cursor_scope, events[49]["occurred_at"], events[49]["id"]) if len(events) > 50 else None
    intake_photos = (await db.execute(text(f"""select f.id,f.original_name from vh_resident_photos p
      join files f on f.id=p.file_id and f.tenant_id=p.tenant_id
      where p.case_id=:case and p.tenant_id={TENANT} and f.status='ready' and f.deleted_at is null order by p.created_at,f.id"""), {"case": case_id})).mappings()
    resolution = None
    revision = None
    if row["public_status"] in {"confirmation", "completed"}:
        revision = str(row["current_resolution_id"])
        result_photos = (await db.execute(text(f"""select f.id,f.original_name from vh_resident_resolution_photos p
          join files f on f.id=p.file_id and f.tenant_id=p.tenant_id
          where p.resolution_id=:revision and p.tenant_id={TENANT} and f.status='ready' and f.deleted_at is null order by f.id"""), {"revision": row["current_resolution_id"]})).mappings()
        resolution = {"summary": row["resolution_summary"], "publishedAt": row["published_at"],
                      "photos": [photo_dto(request, scope[1], p) for p in result_photos]}
    allowed = row["public_status"] == "confirmation"
    return RequestView(**summary(row), description=row["description"], apartmentId=str(row["unit_id"]),
                       location=row["location_label"], photos=[photo_dto(request, scope[1], p) for p in intake_photos],
                       events=[{"id": str(e["id"]), "label": e["label"], "at": e["occurred_at"], **({"note": e["note"]} if e["note"] else {})} for e in events[:50]],
                       eventsNextCursor=next_cursor, resolutionRevision=revision, resolution=resolution,
                       permissions={"canConfirm": allowed, "canRequestRework": allowed}).model_dump(mode="json", exclude_none=False)


async def event(db, case_id, label, event_type, *, note=None, payload=None):
    row_id = (await db.execute(text(f"""insert into vh_resident_public_events(tenant_id,case_id,label,note)
        values({TENANT},:case,:label,:note) returning id"""), {"case": case_id, "label": label, "note": note})).scalar_one()
    await db.execute(text(f"""insert into vh_resident_outbox(tenant_id,case_id,event_id,event_type,payload)
        values({TENANT},:case,:event,:type,cast(:payload as jsonb))"""),
        {"case": case_id, "event": row_id, "type": event_type, "payload": json.dumps(payload or {"caseId": str(case_id)})})


async def append_domain_event(db, ticket_id, event_type, to_status=None):
    """Allowlisted public labels; internal notes, costs and actor data stay private."""
    labels = {"ticket.routing_accepted": "Ban quản lý đã tiếp nhận phản ánh",
              "work_order.offered": "Đã đề nghị nhân viên tiếp nhận công việc",
              "work_assignment.responded": "Đã cập nhật phân công xử lý",
              "work_order.status_changed": "Đã cập nhật tiến độ xử lý",
              "work_order.qc_recorded": "Đã cập nhật kết quả kiểm tra chất lượng",
              "work_order.redo_created": "Đã yêu cầu kiểm tra và xử lý lại",
              "ticket.status_changed": "Đã cập nhật tiến độ phản ánh"}
    labels.update({'plan.proposed': 'BQL đang chuẩn bị phương án xử lý',
                   'plan.management_decided': 'Đã cập nhật phương án xử lý',
                   'plan.resident_decided': 'Đã ghi nhận phản hồi phương án của cư dân'})
    if event_type not in labels:
        return
    # Older deployments may run the existing Operations routes before migration 0005.
    if (await db.execute(text("select to_regclass('public.vh_resident_cases')"))).scalar_one() is None:
        return
    ids = (await db.execute(text(f"""select c.id from vh_resident_cases c
      join vh_resident_case_tickets l on l.case_id=c.id and l.tenant_id=c.tenant_id
      where l.ticket_id=:ticket and c.tenant_id={TENANT} and c.status!='completed' order by c.id"""), {"ticket": ticket_id})).scalars()
    for case_id in ids:
        await event(db, case_id, labels[event_type], "resident.case.progress")


async def receipt(scope, operation, resource, key, payload):
    db, actor = scope[:2]
    # Serialize identical keys even before the aggregate exists. Receipt is committed
    # in the same transaction as the command, so concurrent retries cannot double-create.
    lock = digest([str(db.info.get("resident_tenant", "")), actor, operation, resource, key])
    await db.execute(text("select pg_advisory_xact_lock(:lock)"), {"lock": int(lock[:16], 16) - (1 << 63)})
    old = (await db.execute(text(f"""select * from vh_resident_command_receipts
        where tenant_id={TENANT} and actor_id=:actor and operation=:op and resource=:resource and key=:key"""),
        {"actor": actor, "op": operation, "resource": resource, "key": key})).mappings().first()
    if old and old["request_hash"] != digest(payload):
        fail(409, "IDEMPOTENCY_CONFLICT", "Key này đã được dùng cho nội dung khác.")
    return dict(old) if old else None


async def save_receipt(scope, operation, resource, key, payload, result, status, result_id):
    await scope[0].execute(text(f"""insert into vh_resident_command_receipts
      (tenant_id,actor_id,operation,resource,key,request_hash,response_status,response_body,result_id)
      values({TENANT},:actor,:op,:resource,:key,:hash,:status,cast(:body as jsonb),:id)"""),
      {"actor": scope[1], "op": operation, "resource": resource, "key": key, "hash": digest(payload),
       "status": status, "body": json.dumps(jsonable_encoder(result)), "id": result_id})


def check_version(row, expected):
    if row["public_version"] != expected:
        fail(409, "VERSION_CONFLICT", "Hồ sơ đã thay đổi. Vui lòng tải lại.", currentVersion=row["public_version"])


async def create_case(scope, body: CreateRequest, request: Request, key: str):
    payload = body.model_dump(mode="json")
    previous = await receipt(scope, "create", "cases", key, payload)
    if previous:
        await case_row(scope, previous["result_id"])
        return previous["response_body"]
    db, actor = scope
    place = await residence(db, actor, body.apartmentId)
    photos = []
    for file_id in sorted(body.photoIds):
        p = (await db.execute(text(f"""select p.*,f.status,f.deleted_at from vh_resident_photos p
          join files f on f.id=p.file_id and f.tenant_id=p.tenant_id
          where p.file_id=:file and p.tenant_id={TENANT} and p.uploaded_by=:actor and p.unit_id=:unit for update of p,f"""),
          {"file": file_id, "actor": actor, "unit": body.apartmentId})).mappings().first()
        if p is None:
            fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy ảnh có quyền gắn vào hồ sơ.")
        if p["status"] != "ready" or p["deleted_at"] is not None or p["case_id"] is not None:
            fail(422, "PHOTO_NOT_READY", "Ảnh chưa sẵn sàng hoặc đã được gắn vào hồ sơ khác.")
        expired = (await db.execute(text("select :expiry<=now()"), {"expiry": p["expires_at"]})).scalar_one()
        if expired:
            fail(422, "PHOTO_NOT_READY", "Ảnh chưa gửi đã hết hạn. Vui lòng tải lại.")
        photos.append(file_id)
    from .v3_resident import CreateChat, create_chat
    title = " ".join(body.description.split())[:90]
    chat = await create_chat(CreateChat(title=title), scope)
    new_id = uuid4()
    await db.execute(text(f"""insert into vh_resident_cases
      (id,tenant_id,requester_user_id,unit_id,building_id,site_id,domain_id,channel_id,code,title,description,location_description,location_label)
      values(:id,{TENANT},:actor,:unit,:building,:site,:domain,:channel,:code,:title,:description,:location,:label)"""),
      {"id": new_id, "actor": actor, "unit": body.apartmentId, "building": place["building_id"],
       "site": place["site_id"], "domain": place["domain_id"], "channel": chat["id"],
       "code": f"YC-{new_id.hex[:12].upper()}", "title": title, "description": body.description,
       "location": body.location.description, "label": f"{place['building_name']} · {place['code']} — {body.location.description}"})
    await db.execute(text(f"""insert into vh_resident_submissions(tenant_id,case_id,submitted_by,description,location_description)
      values({TENANT},:case,:actor,:description,:location)"""),
      {"case": new_id, "actor": actor, "description": body.description, "location": body.location.description})
    for fid in photos:
        await db.execute(text(f"update vh_resident_photos set case_id=:case where file_id=:id and tenant_id={TENANT}"), {"case": new_id, "id": fid})
        await db.execute(text(f"update files set retention_until=null where id=:id and tenant_id={TENANT}"), {"id": fid})
    await event(db, new_id, "Đã tiếp nhận phản ánh", "resident.case.created")
    result = await public_detail(scope, await case_row(scope, new_id), request)
    await save_receipt(scope, "create", "cases", key, payload, result, 201, new_id)
    return result


async def decide(scope, case_id, body, request, key, operation):
    payload = body.model_dump(mode="json")
    previous = await receipt(scope, operation, str(case_id), key, payload)
    if previous:
        await case_row(scope, case_id)
        return previous["response_body"]
    row = await lock_case(scope, case_id)
    check_version(row, body.expectedVersion)
    if row["current_resolution_id"] != body.resolutionRevision:
        fail(409, "RESOLUTION_CHANGED", "Kết quả đã thay đổi. Vui lòng xem lại kết quả hiện hành.")
    if row["public_status"] != "confirmation":
        fail(409, "INVALID_STATE", "Hồ sơ chưa ở bước chờ xác nhận kết quả.")
    db, actor = scope
    await db.execute(text(f"""insert into vh_resident_resolution_responses(tenant_id,case_id,resolution_id,actor_id,decision,reason)
      values({TENANT},:case,:revision,:actor,:decision,:reason)"""),
      {"case": case_id, "revision": body.resolutionRevision, "actor": actor, "decision": operation,
       "reason": body.reason if operation == "reopen" else None})
    status = "completed" if operation == "confirm" else "processing"
    await db.execute(text(f"""update vh_resident_cases set status=:status,current_resolution_id=:revision,
      version=version+1,updated_at=now() where id=:case and tenant_id={TENANT}"""),
      {"status": status, "revision": body.resolutionRevision if operation == "confirm" else None, "case": case_id})
    await event(db, case_id, "Bạn đã xác nhận kết quả" if operation == "confirm" else "Đã yêu cầu kiểm tra lại",
                f"resident.case.{operation}", note=body.reason if operation == "reopen" else None)
    result = await public_detail(scope, await case_row(scope, case_id), request)
    await save_receipt(scope, operation, str(case_id), key, payload, result, 200, case_id)
    return result
