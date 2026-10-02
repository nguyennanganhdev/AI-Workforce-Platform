"""Real PostgreSQL contract checks in an isolated, disposable database.

Set RESIDENT_TEST_ADMIN_URL and RESIDENT_TEST_RUNTIME_URL to local PostgreSQL URLs,
or use the existing ignored .local-v3-faker config. The live demo DB is untouched.
"""

import asyncio
import io
import json
import os
import re
import base64
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

SERVICE = Path(__file__).resolve().parents[1]
PROJECT = SERVICE.parents[1]
BASE = "/api/domains/vinhomes/resident"
OPS = "/api/domains/vinhomes/operations/resident-cases"
TENANT = UUID("11111111-1111-5111-a111-111111111111")
CATEGORY = "33333333-3333-5333-a333-333333333333"


class TestDatabase(dict):
    __test__ = False

    def __repr__(self):
        return "TestDatabase(admin=<redacted>, runtime=<redacted>)"


def env_file(name):
    path = SERVICE / ".local-v3-faker" / name
    return dict(line.split("=",1) for line in path.read_text().splitlines() if line and not line.startswith("#")) if path.exists() else {}


def database_url(url, name):
    parts = urlsplit(url.replace("postgresql+asyncpg:", "postgresql:"))
    if parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Resident database tests require a local PostgreSQL host")
    return urlunsplit(parts._replace(path="/"+name))


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    admin_url = os.getenv("RESIDENT_TEST_ADMIN_URL") or env_file("migration.env").get("DATABASE_URL")
    runtime_url = os.getenv("RESIDENT_TEST_RUNTIME_URL") or env_file("api.env").get("VINHOMES_API_DATABASE_URL")
    if not admin_url or not runtime_url:
        pytest.skip("Local PostgreSQL configuration is required for resident contract integration tests")
    test_name = "resident_contract_test_"+uuid4().hex
    created = False

    async def setup():
        nonlocal created
        admin = await asyncpg.connect(admin_url, timeout=5)
        try:
            await admin.execute(f'CREATE DATABASE "{test_name}"')
            created = True
        finally:
            await admin.close()
        db = await asyncpg.connect(database_url(admin_url,test_name))
        try:
            for entry in json.loads((PROJECT/"server/drizzle/meta/_journal.json").read_text())["entries"]:
                await db.execute((PROJECT/"server/drizzle"/(entry["tag"]+".sql")).read_text(encoding="utf-8").replace("--> statement-breakpoint", ""))
            for name in ("seed_v3_local.sql","seed_v3_faker.sql","seed_v3_demo_ui.sql","seed_v3_remaining.sql"):
                await db.execute((SERVICE/"scripts"/name).read_text(encoding="utf-8"))
            grants = (SERVICE/"scripts/grant_v3_api_role.sql").read_text(encoding="utf-8").replace("GRANT CONNECT ON DATABASE vinhomes_v3",f'GRANT CONNECT ON DATABASE "{test_name}"')
            await db.execute(grants)
            await db.execute("update users set phone_e164='+84901234567' where id='local-v3-resident'")
        finally:
            await db.close()
        runtime = await asyncpg.connect(database_url(runtime_url,test_name))
        try:
            role = await runtime.fetchrow("select rolsuper,rolbypassrls from pg_roles where rolname=current_user")
            assert not role["rolsuper"] and not role["rolbypassrls"], "Tests must exercise the restricted runtime role"
        finally:
            await runtime.close()

    async def cleanup():
        if created:
            assert re.fullmatch(r"resident_contract_test_[a-f0-9]{32}",test_name)
            admin = await asyncpg.connect(admin_url)
            try:
                await admin.execute(f'DROP DATABASE "{test_name}" WITH (FORCE)')
            finally:
                await admin.close()

    import vinhomes_api.resident_photos as photos
    import vinhomes_api.v3_files as ticket_photos
    previous_root = photos.FILE_ROOT
    photos.FILE_ROOT = tmp_path_factory.mktemp("resident-images")
    previous_ticket_root = ticket_photos.FILE_ROOT
    ticket_photos.FILE_ROOT = photos.FILE_ROOT
    try:
        asyncio.run(setup())
        yield TestDatabase(admin=database_url(admin_url,test_name), runtime=database_url(runtime_url,test_name).replace("postgresql:","postgresql+asyncpg:"))
    finally:
        photos.FILE_ROOT = previous_root
        ticket_photos.FILE_ROOT = previous_ticket_root
        asyncio.run(cleanup())


def sql(database, query, *args):
    async def run():
        db = await asyncpg.connect(database["admin"])
        try:
            return [dict(r) for r in await db.fetch(query,*args)]
        finally:
            await db.close()
    return asyncio.run(run())


@contextmanager
def client(database, actor="resident", tenant=TENANT):
    settings = V3Settings("127.0.0.1",8000,database["runtime"],tenant,None,"local-v3-"+actor,
                          resident_allowed_origins=("http://testserver",))
    with TestClient(create_app(settings),client=("127.0.0.1",50000)) as result:
        yield result


def key():
    return {"Idempotency-Key":str(uuid4())}


def image():
    buffer = io.BytesIO()
    Image.new("RGB",(5,5),"red").save(buffer,format="PNG")
    return buffer.getvalue()


def create(c, *, photo_ids=None, description="Vòi nước dưới bồn rửa đang bị rò."):
    apartment = c.get(BASE+"/me").json()["apartments"][0]["id"]
    payload = {"apartmentId":apartment,"description":description,"location":{"description":"Bếp, dưới bồn rửa"},"photoIds":photo_ids or []}
    headers = key()
    response = c.post(BASE+"/requests",json=payload,headers=headers)
    assert response.status_code==201,response.text
    assert response.headers["Location"]==BASE+"/requests/"+response.json()["id"]
    return response.json(),payload,headers


def test_upload_intake_replay_and_public_shape(database):
    with client(database) as c:
        profile = c.get(BASE+"/me").json()
        upload_key=key()
        upload = c.post(BASE+"/photos",data={"apartmentId":profile["apartments"][0]["id"]},files={"file":("leak.png",image(),"image/png")},headers=upload_key)
        assert upload.status_code==201,upload.text
        photo=upload.json()
        assert photo["status"]=="ready"
        assert c.get(photo["url"]).status_code==200
        replay_upload=c.post(BASE+"/photos",data={"apartmentId":profile["apartments"][0]["id"]},files={"file":("leak.png",image(),"image/png")},headers=upload_key)
        assert replay_upload.json()==photo
        case,body,headers=create(c,photo_ids=[photo["id"]])
        assert case["status"]=="received" and case["version"]==1
        assert case["permissions"]=={"canConfirm":False,"canRequestRework":False}
        assert case["resolutionRevision"] is None and case["eventsNextCursor"] is None
        assert c.post(BASE+"/requests",json=body,headers=headers).json()==case
        conflict=c.post(BASE+"/requests",json={**body,"description":"Một phản ánh có nội dung khác"},headers=headers)
        assert conflict.status_code==409 and conflict.json()["error"]["code"]=="IDEMPOTENCY_CONFLICT"
        assert c.post(BASE+"/requests",json=body,headers=key()).status_code==422
        listing=c.get(BASE+"/requests",params={"q":case["code"]}).json()
        assert listing["items"][0]["id"]==case["id"]
        assert "photos" not in listing["items"][0] and "events" not in listing["items"][0]
        snapshot=c.get(BASE+"/requests/"+case["id"]).json()
        assert set(snapshot)=={"id","code","title","status","createdAt","updatedAt","version","description","apartmentId","location","photos","events","eventsNextCursor","resolutionRevision","resolution","permissions"}
        assert c.get(snapshot["photos"][0]["url"]).headers["content-type"].startswith("image/png")


def test_validation_origin_and_oversize(database):
    with client(database) as c:
        case,body,_=create(c)
        assert c.post(BASE+"/requests",json=body).status_code==400
        assert c.post(BASE+"/requests",json={**body,"tenantId":str(TENANT)},headers=key()).status_code==422
        assert c.post(BASE+"/requests",json={**body,"description":"        "},headers=key()).status_code==422
        denied=c.post(BASE+"/requests",json=body,headers={**key(),"Origin":"https://evil.test"})
        assert denied.status_code==403 and denied.json()["error"]["code"]=="ORIGIN_DENIED"
        apartment=body["apartmentId"]
        invalid=c.post(BASE+"/photos",data={"apartmentId":apartment},files={"file":("bad.png",b"\x89PNG\r\n\x1a\nINVALID","image/png")},headers=key())
        assert invalid.status_code==422
        wrong_mime=c.post(BASE+"/photos",data={"apartmentId":apartment},files={"file":("bad.jpg",image(),"image/jpeg")},headers=key())
        assert wrong_mime.status_code==422
        unknown=c.post(BASE+"/photos",data={"apartmentId":apartment,"tenantId":str(TENANT)},files={"file":("test.png",image(),"image/png")},headers=key())
        assert unknown.status_code==422
        too_large=c.post(BASE+"/photos",data={"apartmentId":apartment},files={"file":("big.png",b"x"*(10*1024*1024+1),"image/png")},headers=key())
        assert too_large.status_code==413
        assert "correlationId" in too_large.json()["error"]


def test_pagination_timeline_and_scope(database):
    with client(database) as c:
        case,body,_=create(c)
        first=c.get(BASE+"/requests?limit=1").json()
        assert first["nextCursor"]
        second=c.get(BASE+"/requests",params={"limit":1,"cursor":first["nextCursor"]}).json()
        assert first["items"][0]["id"]!=second["items"][0]["id"]
        assert c.get(BASE+"/requests",params={"cursor":first["nextCursor"],"filter":"completed"}).status_code==400
        sql(database,"""insert into vh_resident_public_events(tenant_id,case_id,label)
            select $1,$2,'Public test progress '||i from generate_series(1,55) i returning id""",TENANT,UUID(case["id"]))
        detail=c.get(BASE+"/requests/"+case["id"]).json()
        assert len(detail["events"])==50 and detail["eventsNextCursor"]
        page=c.get(BASE+"/requests/"+case["id"],params={"eventsCursor":detail["eventsNextCursor"]}).json()
        assert len(page["events"])==6 and not page["eventsNextCursor"]
        assert not {e["id"] for e in detail["events"]}&{e["id"] for e in page["events"]}
    with client(database,"technical") as other:
        assert other.get(BASE+"/requests/"+case["id"]).status_code==404
        assert not any(r["id"]==case["id"] for r in other.get(BASE+"/requests").json()["items"])


def prepared_case(database):
    with client(database) as resident:
        case,_,_=create(resident)
    with client(database,"admin") as staff:
        materialized=staff.post(OPS+"/"+case["id"]+"/tickets",json={"expectedVersion":case["version"],"categoryId":CATEGORY},headers=key())
        assert materialized.status_code==201,materialized.text
        ticket_id=materialized.json()["ticketId"]
        order_id=uuid4()
        # Fixture represents an executor's completed job. Public publication still
        # goes through real evidence, QC and domain version APIs below.
        sql(database,"""insert into work_orders(id,tenant_id,ticket_id,category_id,description,status,required_specialty_id,completed_at,version)
            values($1,$2,$3,$4,'Completed fixture repair','completed',$4,now(),1) returning id""",order_id,TENANT,UUID(ticket_id),UUID(CATEGORY))
        sql(database,"update tickets set status='resolved',resolved_at=now(),version=version+1,updated_at=now() where id=$1 returning id",UUID(ticket_id))
        file=staff.post("/tickets/"+ticket_id+"/files",content=image(),headers={"Content-Type":"application/octet-stream"},params={"filename":"verified.png","mimeType":"image/png","purpose":"after"})
        assert file.status_code==201,file.text
        evidence=staff.post("/tickets/"+ticket_id+"/evidence",json={"file_id":file.json()["fileId"],"work_order_id":str(order_id),"purpose":"verification","version":sql(database,"select version from tickets where id=$1",UUID(ticket_id))[0]["version"]})
        assert evidence.status_code==201,evidence.text
        row=staff.get(OPS+"/"+case["id"]).json()["request"]
        publication={"expectedVersion":row["version"],"summary":"Đã sửa vòi và kiểm tra lại, không còn rò nước.","photoIds":[file.json()["fileId"]]}
        assert staff.post(OPS+"/"+case["id"]+"/resolution",json=publication,headers=key()).status_code==409
        qc=staff.post(f"/work-orders/{order_id}/qc",json={"outcome":"pass","criteria":[{"name":"no leak","passed":True}]})
        assert qc.status_code==201,qc.text
        publication["expectedVersion"]=staff.get(OPS+"/"+case["id"]).json()["request"]["version"]
        response=staff.post(OPS+"/"+case["id"]+"/resolution",json=publication,headers=key())
        assert response.status_code==201,response.text
        return response.json()["request"],ticket_id,order_id


def test_publication_confirmation_retry_and_shared_case(database):
    published,ticket_id,_=prepared_case(database)
    with client(database) as resident:
        visible=resident.get(BASE+"/requests/"+published["id"]).json()
        assert visible["status"]=="confirmation" and visible["permissions"]["canConfirm"]
        assert resident.get(visible["resolution"]["photos"][0]["url"]).status_code==200
        other,_,_=create(resident)
    with client(database,"admin") as staff:
        linked=staff.post(OPS+"/"+other["id"]+"/ticket-links",json={"ticketId":ticket_id,"expectedVersion":other["version"]},headers=key())
        assert linked.status_code==200,linked.text
    body={"expectedVersion":visible["version"],"resolutionRevision":visible["resolutionRevision"]}
    headers=key()
    with client(database) as resident:
        response=resident.post(BASE+"/requests/"+visible["id"]+"/confirm",json=body,headers=headers)
        assert response.status_code==200,response.text
        assert response.json()["status"]=="completed"
        assert resident.post(BASE+"/requests/"+visible["id"]+"/confirm",json=body,headers=headers).json()==response.json()
        assert resident.post(BASE+"/requests/"+visible["id"]+"/reopen",json={**body,"reason":"Vẫn còn rò nước khi mở vòi."},headers=key()).status_code==409
        assert resident.get(BASE+"/requests/"+other["id"]).json()["status"]=="processing"
    assert sql(database,"select status from tickets where id=$1",UUID(ticket_id))[0]["status"]=="resolved"


def test_concurrent_confirm_reopen_and_revision_guard(database):
    published,_,_=prepared_case(database)
    body={"expectedVersion":published["version"],"resolutionRevision":published["resolutionRevision"]}
    def run(operation):
        with client(database) as resident:
            return resident.post(BASE+"/requests/"+published["id"]+"/"+operation,json={**body,**({"reason":"Nước vẫn rò ở khớp nối sau sửa."} if operation=="reopen" else {})},headers=key()).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(run,["confirm","reopen"]))
    assert sorted(statuses)==[200,409]
    assert sql(database,"select count(*) as n from vh_resident_resolution_responses where case_id=$1",UUID(published["id"]))[0]["n"]==1
    stale,ticket_id,_=prepared_case(database)
    sql(database,"update tickets set version=version+1,updated_at=now() where id=$1 returning id",UUID(ticket_id))
    with client(database) as resident:
        assert resident.get(BASE+"/requests/"+stale["id"]).json()["status"]=="processing"
        response=resident.post(BASE+"/requests/"+stale["id"]+"/confirm",json={"expectedVersion":stale["version"],"resolutionRevision":stale["resolutionRevision"]},headers=key())
        assert response.status_code==409 and response.json()["error"]["code"]=="VERSION_CONFLICT"


def test_complete_backend_journey_without_injected_workflow_state(database):
    """Seed identity/catalog only; every workflow transition uses mounted APIs."""
    with client(database) as resident:
        case, _, _ = create(resident)
    with client(database, "management") as staff:
        intake = staff.post(OPS+"/"+case["id"]+"/tickets",
                           json={"expectedVersion":case["version"], "categoryId":CATEGORY}, headers=key())
        assert intake.status_code == 201, intake.text
        ticket_id = intake.json()["ticketId"]
        ticket = staff.get("/tickets/"+ticket_id).json()["ticket"]
        plan = staff.post("/tickets/"+ticket_id+"/plans", json={
            "title":"Repair and verify", "ticket_version":ticket["version"],
            "idempotency_key":str(uuid4()), "steps":[{"category_id":CATEGORY,"description":"Repair leak"}],
        })
        assert plan.status_code == 201, plan.text
        approved = staff.post("/plans/"+plan.json()["id"]+"/management-decision", json={
            "version":plan.json()["version"], "decision":"approve", "note":"Approve repair",
        })
        assert approved.status_code == 200, approved.text
    with client(database) as resident:
        plans = resident.get(BASE+"/requests/"+case["id"]+"/plans").json()["items"]
        assert plans[0]["canDecide"]
        decided = resident.post(BASE+"/requests/"+case["id"]+"/plans/"+plans[0]["id"]+"/decision",
                                json={"expectedVersion":plans[0]["version"],"decision":"approve","note":"Proceed"},headers=key())
        assert decided.status_code == 200, decided.text
    with client(database, "admin") as staff:
        orders = staff.get("/tickets/"+ticket_id).json()["workOrders"]
        assert len(orders) == 1 and orders[0]["status"] == "queued"
        work = orders[0]
        catalog = staff.get('/catalogs').json()
        worker = next(row for row in catalog['staff'] if row['user_id'] == 'local-v3-technical')
        from datetime import datetime, timedelta, timezone
        offered = staff.post('/work-orders/'+work['id']+'/assignments', json={
            'staff_id':worker['id'], 'offer_expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
            'work_order_version':work['version'],
        })
        assert offered.status_code == 201, offered.text
        assignment_id = offered.json()['id']
        with client(database, 'technical') as executor:
            accepted = executor.post('/assignments/'+assignment_id+'/response', json={
                'status':'accepted', 'eta_at':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),
            })
            assert accepted.status_code == 200, accepted.text
        work = staff.get('/work-orders/'+work['id']).json()['workOrder']
        for target in ["en_route","arrived","in_progress"]:
            with client(database, 'technical') as executor:
                changed = executor.patch("/work-orders/"+work["id"]+"/status",
                                         json={"version":work["version"],"status":target,"note":"Verified workflow step"})
            assert changed.status_code == 200, changed.text
            work = changed.json()
        file_id = None
        for purpose in ["before","after"]:
            photo = staff.post("/tickets/"+ticket_id+"/files",content=image(),
                               headers={"Content-Type":"application/octet-stream"},
                               params={"filename":purpose+".png","mimeType":"image/png","purpose":purpose})
            assert photo.status_code == 201, photo.text
            file_id = photo.json()["fileId"]
            version = staff.get("/tickets/"+ticket_id).json()["ticket"]["version"]
            evidence = staff.post("/tickets/"+ticket_id+"/evidence",json={
                "file_id":file_id,"work_order_id":work["id"],"assignment_id":assignment_id,"purpose":purpose,"version":version,
            })
            assert evidence.status_code == 201, evidence.text
        with client(database, 'technical') as executor:
            completed = executor.patch("/work-orders/"+work["id"]+"/status",
                                       json={"version":work["version"],"status":"completed","note":"Repair complete"})
            denied_qc = executor.post("/work-orders/"+work["id"]+"/qc",json={"outcome":"pass","criteria":[{"name":"No leak","passed":True}]})
            assert denied_qc.status_code == 403
        assert completed.status_code == 200, completed.text
        qc = staff.post("/work-orders/"+work["id"]+"/qc",json={"outcome":"pass","criteria":[{"name":"No leak","passed":True}]})
        assert qc.status_code == 201, qc.text
        current = staff.get(OPS+"/"+case["id"]).json()["request"]
        publication = staff.post(OPS+"/"+case["id"]+"/resolution",json={
            "expectedVersion":current["version"],"summary":"Repair verified by management", "photoIds":[file_id],
        },headers=key())
        assert publication.status_code == 201, publication.text
    with client(database) as resident:
        current = resident.get(BASE+"/requests/"+case["id"]).json()
        assert current["status"] == "confirmation"
        assert current["resolution"]["summary"] == "Repair verified by management"
        assert current["resolution"]["photos"][0]["id"] == file_id
        confirmed = resident.post(BASE+"/requests/"+case["id"]+"/confirm",json={
            "expectedVersion":current["version"],"resolutionRevision":current["resolutionRevision"],
        },headers=key())
        assert confirmed.status_code == 200, confirmed.text
    persisted = sql(database,"select status,current_resolution_id from vh_resident_cases where id=$1",UUID(case["id"]))[0]
    assert persisted["status"] == "completed" and str(persisted["current_resolution_id"]) == current["resolutionRevision"]
    assert sql(database,"select status from work_orders where id=$1",UUID(work["id"]))[0]["status"] == "completed"
    assert sql(database,"select status from tickets where id=$1",UUID(ticket_id))[0]["status"] == "resolved"


def test_real_resident_frontend_adapter_against_http_and_postgres(database, tmp_path):
    """Execute the actual frontend adapter, without mocked fetch or browser storage."""
    if not (PROJECT / 'resident-app/src/services/backend-adapter.ts').is_file() or not (
        PROJECT / 'resident-app/src/services/resident-api.ts'
    ).is_file():
        pytest.skip('Frontend adapter is not included in the backend-only checkout')
    import uvicorn
    bun = shutil.which('bun')
    assert bun, 'Bun is required to verify the actual frontend adapter'
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    settings = V3Settings('127.0.0.1', port, database['runtime'], TENANT, None, 'local-v3-resident',
                          resident_allowed_origins=(origin,))
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets':[listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<deadline:
            time.sleep(.05)
        assert server.started, 'Local contract HTTP server did not start'
        adapter = (PROJECT/'resident-app/src/services/backend-adapter.ts').as_posix()
        transport = (PROJECT/'resident-app/src/services/resident-api.ts').as_posix()
        script = tmp_path/'resident-adapter-check.ts'
        script.write_text(f'''
globalThis.location = {{origin: {json.dumps(origin)}}} as any;
globalThis.sessionStorage = {{getItem: () => null}} as any;
Object.defineProperty(globalThis, 'localStorage', {{get() {{throw new Error('Business data accessed localStorage');}}}});
const {{residentApi}} = await import({json.dumps(transport)});
const adapter = await import({json.dumps(adapter)});
const profile = await residentApi.me();
const state = adapter.emptyBackendState();
state.draft = {{step:'review',description:'Adapter HTTP repair {uuid4()}',location:'Kitchen sink',
  photos:[{{id:crypto.randomUUID(),name:'leak.png',url:'data:image/png;base64,{base64.b64encode(image()).decode()}'}}]}};
const created = await adapter.submitBackend(state);
const repeated = await adapter.submitBackend(state);
if (created.requests[0].id !== repeated.requests[0].id) throw new Error('Create retry duplicated a Case');
const rows = await adapter.hydrateBackend();
const row = rows.find(r=>r.id === created.requests[0].id);
if (!row || row.status !== 'received' || row.photos.length !== 1 || !row.events.length) throw new Error('Adapter projection differs from backend');
const detail = await residentApi.get(row.id);
if (detail.apartmentId !== profile.apartments[0].id) throw new Error('Apartment binding differs');
const imageResponse = await fetch(detail.photos[0].url);
if (!imageResponse.ok || (await imageResponse.arrayBuffer()).byteLength === 0) throw new Error('Uploaded photo unavailable');
console.log(JSON.stringify({{id:row.id,photoId:row.photos[0].id,apartmentId:detail.apartmentId}}));
''', encoding='utf-8')
        environment = {**os.environ, 'VITE_RESIDENT_MODE':'api', 'VITE_RESIDENT_API_BASE_URL':origin+BASE}
        result = subprocess.run([bun, str(script)], cwd=PROJECT, env=environment, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip().splitlines()[-1])
        persisted = sql(database,'select status,unit_id from vh_resident_cases where id=$1',UUID(output['id']))[0]
        assert persisted['status'] == 'received' and str(persisted['unit_id']) == output['apartmentId']
        assert sql(database,'select count(*) as n from vh_resident_photos where case_id=$1',UUID(output['id']))[0]['n'] == 1
        assert sql(database,"select count(*) as n from vh_resident_command_receipts where result_id=$1 and operation='create'",UUID(output['id']))[0]['n'] == 1
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
