"""New password identities complete the real domain business flow. No Agent or model is invoked."""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from test_resident_contract import TENANT, sql, database as database
from test_account_administration import door, sign_in
from vinhomes_api.password_auth import password_hash


def admin_login(database, client):
    admin = sql(database, "select u.id,u.email from users u join platform_admins p on p.user_id=u.id limit 1")[0]
    password = secrets.token_urlsafe(16)
    sql(database, """insert into accounts(id,account_id,provider_id,user_id,password)
        values(gen_random_uuid()::text,$1,'vinhomes-password-v1',$1,$2)
        on conflict(provider_id,account_id) do update set password=excluded.password""", admin['id'], password_hash(password))
    assert sign_in(client, admin['email'], password) == 200


def new_resident(admin, resident):
    password = secrets.token_urlsafe(16)
    email = f"onboarding-{uuid4().hex}@example.invalid"
    response = resident.post('/auth/register', json={'email':email,'name':'Cư dân kiểm thử','password':password})
    assert response.status_code == 201, response.text
    response = resident.post('/auth/login',json={'identifier':email,'password':password})
    assert response.status_code == 200
    return response.json()['user']['id'], email, password


def staff_payload(database):
    unit = sql(database, "select id from management_units where tenant_id=$1 and status='active' order by code limit 1", TENANT)[0]['id']
    category = sql(database, "select id from service_categories where tenant_id=$1 and code='technical'", TENANT)[0]['id']
    now = datetime.now(timezone.utc)
    return {'management_unit_id':str(unit),'employee_code':'TEST-'+uuid4().hex[:12], 'category_ids':[str(category)],
            'max_concurrent_jobs':1,'availability':'available','shifts':[{'starts_at':(now-timedelta(hours=1)).isoformat(), 'ends_at':(now+timedelta(hours=8)).isoformat()}]}


def test_approval_is_atomic_and_verified_home_is_required(database):
    with door(database) as admin, door(database) as resident:
        admin_login(database,admin)
        user,email,password = new_resident(admin,resident)
        unit = sql(database,"select id from units where tenant_id=$1 and status='active' order by code limit 1",TENANT)[0]['id']
        assert resident.get('/auth/session').json()['membershipStatus']=='pending'
        assert resident.get('/auth/onboarding-options').status_code==403
        body={'role':'customer','status':'active','residency':{'unit_id':str(uuid4()),'relation':'owner'}}
        assert admin.patch(f'/auth/accounts/{user}',json=body).status_code==404
        assert resident.get('/auth/session').json()['membershipStatus']=='pending'  # rollback includes session revocation
        body['residency']['unit_id']=str(unit)
        for _ in range(2):
            response=admin.patch(f'/auth/accounts/{user}',json=body)
            assert response.status_code==200,response.text
        assert resident.get('/auth/session').status_code==401
        assert sign_in(resident,email,password)==200
        assert str(unit) in {u['id'] for u in resident.get('/resident/me').json()['units']}
        assert sql(database,"select count(*) as n from unit_residents where user_id=$1 and verification_status='verified'",user)[0]['n']==1
        body['residency']['relation']='tenant'
        assert admin.patch(f'/auth/accounts/{user}',json=body).status_code==409
        detail=admin.get(f'/auth/accounts/{user}/onboarding').json()
        residency=detail['residencies'][0]['id']
        assert admin.delete(f'/auth/accounts/{user}/residencies/{residency}').status_code==200
        assert resident.get('/auth/session').status_code==401
        assert sign_in(resident,email,password)==200
        assert resident.get('/resident/me').json()['units']==[]


def test_staff_profile_and_shift_are_idempotent_and_validate_collisions(database):
    with door(database) as admin, door(database) as staff:
        admin_login(database,admin)
        profile=staff_payload(database)
        password=secrets.token_urlsafe(16)
        email=f'staff-{uuid4().hex}@example.invalid'
        body={'name':'Nhân viên kiểm thử','email':email,'password':password,'role':'staff','staff_profile':profile}
        made=admin.post('/auth/accounts',json=body)
        assert made.status_code==201,made.text
        user=made.json()['id']
        assert sign_in(staff,email,password)==200
        assert staff.get('/operations/me').json()['role']=='staff'
        assert admin.patch(f'/auth/accounts/{user}',json={'role':'staff','status':'active','staff_profile':profile}).status_code==200
        detail=admin.get(f'/auth/accounts/{user}/onboarding').json()['staff_profile']
        assert len(detail['shifts'])==1
        assert detail['category_ids']==profile['category_ids']
        assert any(s['user_id']==user for s in admin.get('/catalogs').json()['staff'])
        duplicate=admin.post('/auth/accounts',json={**body,'email':f'collision-{uuid4().hex}@example.invalid'})
        assert duplicate.status_code==409
        overlap={**profile,'shifts':[dict(profile['shifts'][0],ends_at=(datetime.now(timezone.utc)+timedelta(hours=10)).isoformat())]}
        assert admin.patch(f'/auth/accounts/{user}',json={'role':'staff','status':'active','staff_profile':overlap}).status_code==409
        assert admin.patch(f'/auth/accounts/{user}',json={'role':'staff','status':'suspended'}).status_code==200
        assert not sql(database,'select active from staff_profiles where user_id=$1',user)[0]['active']


def test_pagination_and_search_reach_accounts_beyond_first_200(database):
    sql(database,"""insert into users(id,name,email,status) select 'page-'||n,'Pagination '||n,'page-'||n||'@example.invalid','active'
        from generate_series(1,205) n on conflict do nothing""")
    sql(database,"""insert into tenant_memberships(tenant_id,user_id,status)
        select $1,'page-'||n,'pending' from generate_series(1,205) n on conflict do nothing""",TENANT)
    with door(database) as admin:
        admin_login(database,admin)
        first=admin.get('/auth/accounts?search=Pagination&limit=200').json()
        assert first['total']==205 and first['nextOffset']==200 and len(first['items'])==200
        second=admin.get('/auth/accounts?search=Pagination&limit=200&offset=200').json()
        assert len(second['items'])==5 and second['nextOffset'] is None
        assert not {x['id'] for x in first['items']} & {x['id'] for x in second['items']}
        target=second['items'][-1]
        found=admin.get('/auth/accounts',params={'search':target['email'],'status':'pending','role':'customer'}).json()
        assert found['total']==1 and found['items'][0]['id']==target['id']
        assert found['items'][0]['has_password'] is False
        assert admin.get('/auth/accounts?limit=201').status_code==422


def test_new_resident_and_new_staff_complete_ticket_without_agent(database,monkeypatch):
    import test_resident_integration as flow
    with door(database) as admin, door(database) as resident, door(database) as staff, door(database) as other:
        admin_login(database,admin)
        user,email,password=new_resident(admin,resident)
        unit=sql(database,"select id from units where tenant_id=$1 and status='active' order by code limit 1",TENANT)[0]['id']
        assert admin.patch(f'/auth/accounts/{user}',json={'role':'customer','status':'active','residency':{'unit_id':str(unit),'relation':'tenant'}}).status_code==200
        assert sign_in(resident,email,password)==200
        staff_email=f'flow-staff-{uuid4().hex}@example.invalid'
        profile=staff_payload(database)
        made=admin.post('/auth/accounts',json={'name':'Kỹ thuật viên mới','email':staff_email,'password':password,'role':'staff','staff_profile':profile})
        assert made.status_code==201,made.text
        assert sign_in(staff,staff_email,password)==200
        other_email=f'other-staff-{uuid4().hex}@example.invalid'
        assert admin.post('/auth/accounts',json={'name':'Nhân viên khác','email':other_email,'password':password,'role':'staff'}).status_code==201
        assert sign_in(other,other_email,password)==200
        clients={'resident':resident,'management':admin,'technical':staff,'security':other}
        def call(method,path,actor='resident',expected=200,**kwargs):
            response=clients[actor].request(method,path,**kwargs)
            assert response.status_code==expected,f'{method} {path}: {response.status_code} {response.text}'
            return response.json()
        monkeypatch.setattr(flow,'call',call)
        p=resident.get('/resident/me').json()
        home=p['units'][0]
        chat=call('POST','/resident/chats',expected=201,json={'title':'Kiểm thử nghiệp vụ không Agent'})
        ticket=call('POST',f"/resident/chats/{chat['id']}/tickets",expected=201,headers={'Idempotency-Key':str(uuid4())},json={
            'domain_id':home['domain_id'],'building_id':home['building_id'],'unit_id':home['id'],
            'category_id':profile['category_ids'][0],'title':'Ổ điện cần sửa','description':'Ổ điện phòng khách không hoạt động.',
            'contact_name':'Cư dân kiểm thử','contact_phone':'0900000000','location':'Phòng khách','request_kind':'incident','file_ids':[]})
        _,approval=flow.finish_work(ticket['id'],profile['category_ids'][0],staff_user_id=made.json()['id'])
        current=call('GET',f"/resident/tickets/{ticket['id']}")['ticket']
        body={'approved':True,'note':'Đã kiểm tra đạt yêu cầu','version':current['version']}
        key=str(uuid4())
        path=f'/resident/approvals/{approval}/decision'
        result=call('POST',path,headers={'Idempotency-Key':key},json=body)
        assert call('POST',path,headers={'Idempotency-Key':key},json=body)==result
        assert call('GET',f"/resident/tickets/{ticket['id']}")['ticket']['status']=='closed'
