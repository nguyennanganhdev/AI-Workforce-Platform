"""Resident v0.1 HTTP producer and the staff intake/publication commands."""

import json
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy import text

from .v3_auth import resident_connection, scoped_connection
from .resident_contract import (
    BASE, OPERATIONS_BASE, TENANT, CreateRequest, ResolutionCommand, ReworkCommand,
    Profile, RequestPage, RequestView, UploadedPhoto, MaterializeTicket, LinkTicket,
    PublishResolution, ResidentPlanDecision, ResidentPlan, ResidentPlanPage, StaffCasePage, StaffCaseDetail, PhotoPage, ErrorEnvelope, key_header, require_key, decode_cursor, encode_cursor, fail,
)
from . import resident_cases as cases
from . import resident_photos as photos

ERRORS = {status: {"model": ErrorEnvelope} for status in (400,401,403,404,409,413,415,422,429,503)}
router = APIRouter(prefix=BASE, tags=["Resident contract v0.1"], responses=ERRORS)
operations_router = APIRouter(prefix=OPERATIONS_BASE, tags=["Resident Case intake and publication"], responses=ERRORS)
ticket_intake_router = APIRouter(tags=['Operations resident intake photos'])


def throttle(request, actor):
    buckets = request.app.state.resident_rate_limits
    now = time.monotonic()
    # Expire inactive users so rate limiting cannot grow indefinitely.
    if now - request.app.state.resident_rate_cleanup > 60:
        for user in list(buckets):
            if not buckets[user] or buckets[user][-1] <= now - 60:
                del buckets[user]
        request.app.state.resident_rate_cleanup = now
    bucket = buckets.setdefault(actor, deque())
    while bucket and bucket[0] <= now - 60:
        bucket.popleft()
    if len(bucket) >= 120:
        from fastapi import HTTPException
        raise HTTPException(429, {"code": "RATE_LIMITED", "message": "Bạn thao tác quá nhanh. Vui lòng thử lại sau."}, headers={"Retry-After": str(max(1,int(60-(now-bucket[0]))+1))})
    bucket.append(now)


async def resident_scope(request: Request):
    # Function-scoped yield commits before FastAPI sends a successful response.
    request.state.resident_created_paths = []
    try:
        async with asynccontextmanager(resident_connection)(request) as scope:
            throttle(request, scope[1])
            yield scope
    except BaseException:
        from starlette.concurrency import run_in_threadpool
        for path in request.state.resident_created_paths:
            await run_in_threadpool(path.unlink, missing_ok=True)
        raise


async def operations_scope(request: Request):
    async with asynccontextmanager(scoped_connection)(request) as scope:
        throttle(request, scope[1])
        yield scope


Resident = Annotated[tuple, Depends(resident_scope, scope="function")]
Operations = Annotated[tuple, Depends(operations_scope, scope="function")]


async def ticket_intake_photos(scope, ticket_id, file_id=None):
    from .v3_mutations import visible_ticket
    await visible_ticket(scope, ticket_id)
    return list((await scope[0].execute(text(f'''select distinct f.id,f.original_name,o.object_key,o.mime_type
      from vh_resident_case_tickets l
      join vh_resident_photos p on p.case_id=l.case_id and p.tenant_id=l.tenant_id
      join files f on f.id=p.file_id and f.tenant_id=p.tenant_id
      join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
      join storage_locations s on s.id=o.location_id and s.tenant_id=o.tenant_id
      where l.ticket_id=:ticket and l.tenant_id={TENANT}
        and (cast(:file as uuid) is null or f.id=cast(:file as uuid))
        and f.status='ready' and f.deleted_at is null and o.status='ready'
        and o.scan_status='clean' and o.verified_at is not null
        and o.mime_type in ('image/jpeg','image/png','image/webp') and s.provider='{photos.object_storage.provider()}' and s.status!='disabled'
      order by f.id limit 100'''), {'ticket': ticket_id, 'file': file_id})).mappings())


@ticket_intake_router.get('/tickets/{ticket_id}/resident-intake-photos', response_model=PhotoPage, operation_id='listTicketResidentIntakePhotos')
async def list_ticket_intake_photos(ticket_id: UUID, request: Request, scope: Operations):
    result = []
    for row in await ticket_intake_photos(scope, ticket_id):
        photo = photos.photo_dto(request, scope[1], row)
        photo['url'] = photo['url'].replace(BASE+'/photos', f'/api/domains/vinhomes/operations/v3/tickets/{ticket_id}/resident-intake-photos')
        result.append(photo)
    return {'items': result}


@ticket_intake_router.get('/tickets/{ticket_id}/resident-intake-photos/{file_id}/content', response_class=Response,
                        operation_id='readTicketResidentIntakePhoto', responses={200: {'content': {'image/jpeg': {}, 'image/png': {}, 'image/webp': {}}}})
async def read_ticket_intake_photo(ticket_id: UUID, file_id: UUID, request: Request, scope: Operations, access: str = Query(max_length=128)):
    from .v3_files import local_only
    local_only(request)
    photos.verify_access(scope, file_id, request, access)
    rows = await ticket_intake_photos(scope, ticket_id, file_id)
    if not rows:
        fail(404, 'PHOTO_NOT_FOUND', 'Không tìm thấy ảnh của ticket này.')
    row = rows[0]
    path = photos.object_path(row['object_key'])
    if not path.is_file():
        fail(404, 'PHOTO_NOT_FOUND', 'Không tìm thấy nội dung ảnh.')
    return photos.object_storage.respond(path, media_type=row['mime_type'], filename=row['original_name'], content_disposition_type='inline',
                                  headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get("/me", response_model=Profile, operation_id="getResidentProfile")
async def me(scope: Resident):
    db, actor = scope
    user = (await db.execute(text("select id,name from users where id=:actor"), {"actor": actor})).mappings().one()
    homes = (await db.execute(text(cases.RESIDENCE + " order by s.name,b.name,u.code,u.id"), {"actor": actor})).mappings()
    homes = {str(home['id']): home for home in homes}.values()
    return {"user": {"id": user["id"], "displayName": user["name"]},
            "apartments": [{"id": str(h["id"]), "label": f"{h['building_name']} · {h['code']}",
                            "projectId": str(h["site_id"]), "projectName": h["site_name"], "towerId": str(h["building_id"])} for h in homes]}


@router.post("/photos", status_code=201, response_model=UploadedPhoto, operation_id="uploadResidentPhoto", dependencies=[Depends(require_key)])
async def upload_photo(request: Request, scope: Resident,
                       file: Annotated[UploadFile, File()], apartmentId: Annotated[UUID, Form()]):
    form = await request.form()
    if set(form.keys()) != {"file", "apartmentId"} or any(len(form.getlist(k)) != 1 for k in form):
        fail(422, "VALIDATION_ERROR", "Upload chỉ nhận một file và một apartmentId.")
    return await photos.upload(scope, apartmentId, file, request, key_header(request))


@router.get("/photos/{file_id}/content", response_class=Response, operation_id="readResidentPhoto", responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}})
async def read_photo(file_id: UUID, request: Request, scope: Resident, access: str = Query(max_length=128)):
    return await photos.content(scope, file_id, request, access)


@router.get("/requests", response_model=RequestPage, operation_id="listResidentRequests")
async def list_requests(request: Request, scope: Resident,
                        filter: Literal["all", "open", "completed"] = "all",
                        q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=50),
                        cursor: str | None = Query(None, max_length=1024), apartmentId: UUID | None = None):
    db, actor = scope
    if apartmentId is not None:
        await cases.residence(db, actor, apartmentId)
    search = q.strip()
    cursor_scope = ["requests", str(request.app.state.settings.tenant_id), actor, filter, search, str(apartmentId)]
    at, case_id = decode_cursor(request, cursor_scope, cursor)
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    sql = f"""with projection as ({cases.PROJECTION} and {cases.OWNER}) select * from projection
      where (cast(:unit as uuid) is null or unit_id=cast(:unit as uuid))
        and (:filter='all' or (:filter='open' and public_status!='completed') or (:filter='completed' and public_status='completed'))
        and (:q='' or code ilike :search or title ilike :search or description ilike :search)
        and (cast(:at as timestamptz) is null or (created_at,id)<(cast(:at as timestamptz),cast(:id as uuid)))
      order by created_at desc,id desc limit :limit"""
    rows = list((await db.execute(text(sql), {"actor": actor, "unit": apartmentId, "filter": filter, "q": search,
      "search": f"%{escaped}%", "at": at, "id": case_id, "limit": limit+1})).mappings())
    next_cursor = encode_cursor(request, cursor_scope, rows[limit-1]["created_at"], rows[limit-1]["id"]) if len(rows)>limit else None
    return {"items": [cases.summary(r) for r in rows[:limit]], "nextCursor": next_cursor}


@router.post("/requests", status_code=201, response_model=RequestView, operation_id="createResidentRequest", dependencies=[Depends(require_key)])
async def create_request(body: CreateRequest, request: Request, response: Response, scope: Resident):
    result = await cases.create_case(scope, body, request, key_header(request))
    response.headers["Location"] = f"{BASE}/requests/{result['id']}"
    return result


@router.get("/requests/{request_id}", response_model=RequestView, operation_id="getResidentRequest")
async def get_request(request_id: UUID, request: Request, scope: Resident, eventsCursor: str | None = Query(None, max_length=1024)):
    return await cases.public_detail(scope, await cases.case_row(scope, request_id), request, eventsCursor)


@router.post("/requests/{request_id}/confirm", response_model=RequestView, operation_id="confirmResidentResolution", dependencies=[Depends(require_key)])
async def confirm(request_id: UUID, body: ResolutionCommand, request: Request, scope: Resident):
    return await cases.decide(scope, request_id, body, request, key_header(request), "confirm")


def resident_plan(row, can_decide=True):
    return {'id': str(row['id']), 'title': row['title'], 'status': row['status'], 'version': row['version'],
            'estimatedAmount': str(row['estimated_amount']), 'steps': [step['description'] for step in row['steps']],
            'canDecide': can_decide and row['status'] == 'resident_pending'}


@router.get('/requests/{request_id}/plans', response_model=ResidentPlanPage, operation_id='listResidentRequestPlans')
async def request_plans(request_id: UUID, scope: Resident):
    row = await cases.case_row(scope, request_id)
    result = (await scope[0].execute(text(f'''select p.* from vh_ticket_plans p
        join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id
        join vh_resident_case_tickets l on l.ticket_id=t.id and l.tenant_id=t.tenant_id
        where l.case_id=:case and l.tenant_id={TENANT} and t.requester_user_id=:actor
          and (p.status in ('resident_pending','approved') or p.resident_at is not null)
        order by p.created_at desc,p.id limit 100'''), {'case': request_id, 'actor': scope[1]})).mappings()
    return {'items': [resident_plan(p, row['public_status'] != 'completed') for p in result]}


@router.post('/requests/{request_id}/plans/{plan_id}/decision', response_model=ResidentPlan,
             operation_id='decideResidentRequestPlan', dependencies=[Depends(require_key)])
async def decide_plan(request_id: UUID, plan_id: UUID, body: ResidentPlanDecision, request: Request, scope: Resident):
    row = await cases.case_row(scope, request_id)
    key, payload = key_header(request), body.model_dump(mode='json')
    resource = f'{request_id}:{plan_id}'
    previous = await cases.receipt(scope, 'plan-decision', resource, key, payload)
    if previous:
        return previous['response_body']
    row = await cases.lock_case(scope, request_id)
    if row['public_status'] == 'completed':
        fail(409, 'INVALID_STATE', 'Hồ sơ đã hoàn thành.')
    linked = (await scope[0].execute(text(f'''select p.id from vh_ticket_plans p
      join vh_resident_case_tickets l on l.ticket_id=p.ticket_id and l.tenant_id=p.tenant_id
      join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id
      where p.id=:plan and l.case_id=:case and l.tenant_id={TENANT} and t.requester_user_id=:actor'''),
      {'plan': plan_id, 'case': request_id, 'actor': scope[1]})).first()
    if not linked:
        fail(404, 'PLAN_NOT_FOUND', 'Không tìm thấy phương án.')
    from .v3_plans import resident_decision, PlanDecision
    result = resident_plan(await resident_decision(plan_id, PlanDecision(decision=body.decision, version=body.expectedVersion, note=body.note), scope))
    await cases.save_receipt(scope, 'plan-decision', resource, key, payload, result, 200, request_id)
    return result


@router.post("/requests/{request_id}/reopen", response_model=RequestView, operation_id="requestResidentRework", dependencies=[Depends(require_key)])
async def reopen(request_id: UUID, body: ReworkCommand, request: Request, scope: Resident):
    return await cases.decide(scope, request_id, body, request, key_header(request), "reopen")


@operations_router.get("/photos/{file_id}/content", response_class=Response, operation_id='readStaffResidentPhoto', responses={200: {'content': {'image/jpeg': {}, 'image/png': {}, 'image/webp': {}}}})
async def staff_photo(file_id: UUID, request: Request, scope: Operations, access: str = Query(max_length=128)):
    return await photos.content(scope, file_id, request, access, operations=True)


async def staff_detail(scope, row, request, events_cursor=None):
    public = await cases.public_detail(scope, row, request, events_cursor)
    db = scope[0]
    identity = (await db.execute(text(f"""select u.name,u.phone_e164,n.code from users u
        join units n on n.id=:unit and n.tenant_id={TENANT}
        where u.id=:actor"""), {"unit":row["unit_id"],"actor":row["requester_user_id"]})).mappings().one()
    links = (await db.execute(text(f"select ticket_id from vh_resident_case_tickets where case_id=:case and tenant_id={TENANT} order by ticket_id"), {"case": row["id"]})).scalars()
    responses = (await db.execute(text(f"""select id,resolution_id,decision,reason,created_at from vh_resident_resolution_responses
      where case_id=:case and tenant_id={TENANT} order by created_at,id"""), {"case": row["id"]})).mappings()
    return {"request": public, "requesterUserId": row["requester_user_id"],
            "requesterDisplayName":identity["name"], "requesterPhone":identity["phone_e164"],
            "apartmentLabel":identity["code"], "tenantId":str(row["tenant_id"]), "ticketIds": [str(t) for t in links],
            "responses": [{"id": str(r["id"]), "resolutionRevision": str(r["resolution_id"]), "decision": r["decision"],
                           "reason": r["reason"], "createdAt": r["created_at"]} for r in responses]}


@operations_router.get("", response_model=StaffCasePage, operation_id='listStaffResidentCases')
async def intake(request: Request, scope: Operations, limit: int = Query(20, ge=1, le=50), cursor: str | None = Query(None, max_length=1024),
                 filter: Literal["all", "open", "completed"] = "open"):
    cursor_scope = ["intake", str(request.app.state.settings.tenant_id), scope[1], filter]
    at, case_id = decode_cursor(request, cursor_scope, cursor)
    sql = f"""with projection as ({cases.PROJECTION} and {cases.MANAGEMENT}) select * from projection
      where (:filter='all' or (:filter='open' and public_status!='completed') or (:filter='completed' and public_status='completed'))
        and (cast(:at as timestamptz) is null or (created_at,id)<(cast(:at as timestamptz),cast(:id as uuid)))
      order by created_at desc,id desc limit :limit"""
    rows = list((await scope[0].execute(text(sql), {"actor": scope[1], "admin": scope[2], "filter": filter, "at": at, "id": case_id, "limit": limit+1})).mappings())
    return {"items": [{**cases.summary(r), "apartmentId": str(r["unit_id"]), "requesterUserId": r["requester_user_id"]} for r in rows[:limit]],
            "nextCursor": encode_cursor(request, cursor_scope, rows[limit-1]["created_at"], rows[limit-1]["id"]) if len(rows)>limit else None}


@operations_router.get("/{case_id}", response_model=StaffCaseDetail, operation_id='getStaffResidentCase')
async def intake_detail(case_id: UUID, request: Request, scope: Operations, eventsCursor: str | None = Query(None, max_length=1024)):
    return await staff_detail(scope, await cases.case_row(scope, case_id, operations=True), request, eventsCursor)


async def attach_ticket(scope, row, ticket_id):
    db, actor = scope[:2]
    from .v3_mutations import visible_ticket
    ticket = await visible_ticket(scope, ticket_id)
    if ticket["building_id"] != row["building_id"] or ticket["domain_id"] != row["domain_id"]:
        fail(422, "VALIDATION_ERROR", "Ticket và hồ sơ phải thuộc cùng tòa nhà/miền nghiệp vụ.")
    if ticket["status"] in {"cancelled", "closed"} or row["public_status"] == "completed":
        fail(409, "INVALID_STATE", "Không thể liên kết hồ sơ/ticket đã đóng.")
    inserted = (await db.execute(text(f"""insert into vh_resident_case_tickets(tenant_id,case_id,ticket_id,linked_by)
        values({TENANT},:case,:ticket,:actor) on conflict do nothing returning ticket_id"""),
        {"case": row["id"], "ticket": ticket_id, "actor": actor})).first()
    if inserted:
        await db.execute(text(f"""update vh_resident_cases set status='processing',current_resolution_id=null,version=version+1,updated_at=now()
            where id=:case and tenant_id={TENANT}"""), {"case": row["id"]})
        await cases.event(db, row["id"], "Đã chuyển phản ánh đến bộ phận xử lý", "resident.case.routed")
    return inserted is not None


@operations_router.post("/{case_id}/tickets", status_code=201, response_model=StaffCaseDetail, operation_id='materializeResidentCaseTicket', dependencies=[Depends(require_key)])
async def materialize(case_id: UUID, body: MaterializeTicket, request: Request, scope: Operations):
    key, payload = key_header(request), body.model_dump(mode="json")
    previous = await cases.receipt(scope, "materialize", str(case_id), key, payload)
    if previous:
        await cases.case_row(scope, case_id, operations=True)
        return previous["response_body"]
    row = await cases.lock_case(scope, case_id, operations=True)
    cases.check_version(row, body.expectedVersion)
    if row["public_status"] == "completed":
        fail(409, "INVALID_STATE", "Hồ sơ đã hoàn tất.")
    person = (await scope[0].execute(text("select name,phone_e164 from users where id=:actor"), {"actor": row["requester_user_id"]})).mappings().one()
    phone = body.contactPhone or person['phone_e164']
    if not phone:
        fail(422, "VALIDATION_ERROR", "Cần bổ sung số điện thoại liên hệ trước khi tạo ticket.", fieldErrors={"contactPhone": ["Resident profile has no phone number"]})
    from .v3_resident import create_resident_ticket, ResidentTicketCreate
    ticket = await create_resident_ticket(row["channel_id"], ResidentTicketCreate(
        domain_id=row["domain_id"], building_id=row["building_id"], unit_id=row["unit_id"], category_id=body.categoryId,
        title=row["title"], description=row["description"], contact_name=person["name"], contact_phone=phone,
        request_kind=body.requestKind, idempotency_key=f"case:{case_id}:{body.categoryId}:{body.requestKind}"),
        (scope[0], row["requester_user_id"]), acting_user_id=scope[1], link_case=False)
    await attach_ticket(scope, row, ticket["id"])
    result = await staff_detail(scope, await cases.case_row(scope, case_id, operations=True), request)
    result["ticketId"] = str(ticket["id"])
    await cases.save_receipt(scope, "materialize", str(case_id), key, payload, result, 201, case_id)
    return result


@operations_router.post("/{case_id}/ticket-links", response_model=StaffCaseDetail, operation_id='linkResidentCaseTicket', dependencies=[Depends(require_key)])
async def link_ticket(case_id: UUID, body: LinkTicket, request: Request, scope: Operations):
    key, payload = key_header(request), body.model_dump(mode="json")
    previous = await cases.receipt(scope, "link", str(case_id), key, payload)
    if previous:
        await cases.case_row(scope, case_id, operations=True)
        return previous["response_body"]
    row = await cases.lock_case(scope, case_id, operations=True, extra_ticket=body.ticketId)
    cases.check_version(row, body.expectedVersion)
    await attach_ticket(scope, row, body.ticketId)
    result = await staff_detail(scope, await cases.case_row(scope, case_id, operations=True), request)
    await cases.save_receipt(scope, "link", str(case_id), key, payload, result, 200, case_id)
    return result


@operations_router.post("/{case_id}/resolution", status_code=201, response_model=StaffCaseDetail, operation_id='publishResidentCaseResolution', dependencies=[Depends(require_key)])
async def publish(case_id: UUID, body: PublishResolution, request: Request, scope: Operations):
    key, payload = key_header(request), body.model_dump(mode="json")
    previous = await cases.receipt(scope, "publish", str(case_id), key, payload)
    if previous:
        await cases.case_row(scope, case_id, operations=True)
        return previous["response_body"]
    row = await cases.lock_case(scope, case_id, operations=True)
    cases.check_version(row, body.expectedVersion)
    if row["public_status"] == "completed" or not row["basis_versions"]:
        fail(409, "INVALID_STATE", "Hồ sơ phải được tiếp nhận và còn mở.")
    db = scope[0]
    from .v3_technical import resolution as resolution_check
    for ticket_id in row["basis_versions"]:
        ticket = (await db.execute(text(f"select status from tickets where id=:id and tenant_id={TENANT}"), {"id": UUID(ticket_id)})).scalar_one()
        if ticket not in {"resolved", "closed"}:
            fail(409, "INVALID_STATE", "Còn sự cố chưa được giải quyết.")
        orders = list((await db.execute(text(f"select id,status from work_orders where ticket_id=:id and tenant_id={TENANT} and required order by id for update"), {"id": UUID(ticket_id)})).mappings())
        if not orders or any(w["status"] != "completed" for w in orders):
            fail(409, "INVALID_STATE", "Mọi công việc bắt buộc phải hoàn tất trước khi công bố kết quả.")
        for work in orders:
            qc = (await db.execute(text(f"select outcome from vh_qc_results where work_order_id=:id and tenant_id={TENANT} order by checked_at desc,id desc limit 1"), {"id": work["id"]})).scalar_one_or_none()
            check = await resolution_check(work["id"], scope)
            if qc != "pass" or not check["ready"]:
                fail(409, "QC_REQUIRED", "Công việc cần QC đạt, bằng chứng hợp lệ và hoàn tất các quyền thao tác.")
    rejected = (await db.execute(text(f"""select r.basis_versions from vh_resident_resolution_responses a
        join vh_resident_resolutions r on r.id=a.resolution_id and r.tenant_id=a.tenant_id
        where a.case_id=:case and a.tenant_id={TENANT} and a.decision='reopen' order by a.created_at desc limit 1"""), {"case": case_id})).scalar_one_or_none()
    if rejected == row["basis_versions"]:
        fail(409, "RESOLUTION_CHANGED", "Cần kiểm tra/xử lý lại trước khi công bố kết quả mới.")
    for fid in sorted(body.photoIds):
        valid = (await db.execute(text(f"""select f.id from evidence_items e join files f on f.id=e.file_id and f.tenant_id=e.tenant_id
          join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
          join vh_resident_case_tickets l on l.ticket_id=e.ticket_id and l.tenant_id=e.tenant_id
          where l.case_id=:case and l.tenant_id={TENANT} and f.id=:file and e.purpose in ('after','verification')
            and e.status='active' and f.status='ready' and f.deleted_at is null and o.status='ready' and o.scan_status='clean'
            and o.mime_type in ('image/jpeg','image/png','image/webp') and o.verified_at is not null
          for share of f,o"""), {"case": case_id, "file": fid})).first()
        if valid is None:
            fail(422, "PHOTO_NOT_READY", "Ảnh kết quả phải là bằng chứng hợp lệ của công việc liên quan.")
    revision = uuid4()
    await db.execute(text(f"""insert into vh_resident_resolutions(id,tenant_id,case_id,summary,published_by,basis_versions)
        values(:id,{TENANT},:case,:summary,:actor,cast(:basis as jsonb))"""),
        {"id": revision, "case": case_id, "summary": body.summary, "actor": scope[1], "basis": json.dumps(row["basis_versions"])})
    for fid in body.photoIds:
        await db.execute(text(f"insert into vh_resident_resolution_photos(tenant_id,resolution_id,file_id) values({TENANT},:revision,:file)"), {"revision": revision, "file": fid})
    await db.execute(text(f"""update vh_resident_cases set status='confirmation',current_resolution_id=:revision,version=version+1,updated_at=now()
        where id=:case and tenant_id={TENANT}"""), {"case": case_id, "revision": revision})
    await cases.event(db, case_id, "Đã có kết quả xử lý, mời bạn kiểm tra", "resident.case.resolution_published", note=body.summary)
    result = await staff_detail(scope, await cases.case_row(scope, case_id, operations=True), request)
    await cases.save_receipt(scope, "publish", str(case_id), key, payload, result, 201, case_id)
    return result
