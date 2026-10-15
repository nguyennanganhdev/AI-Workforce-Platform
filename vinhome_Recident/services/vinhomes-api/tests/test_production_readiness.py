"""Production identity retirement, clean-data preservation and isolation across three sites. No provider calls."""
import asyncio
import json
import secrets
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_account_administration import door, sign_in
from test_account_onboarding import admin_login
from test_resident_contract import TENANT, database as database, sql
from vinhomes_api import knowledge
from vinhomes_api.bootstrap import OP1, bootstrap, site_id
from vinhomes_api.password_auth import COOKIE, password_hash, session_hash
from vinhomes_api.production_reset import prepare


def test_management_cannot_sign_in_reuse_a_session_or_be_granted(database):
    manager = sql(database,"select id,email from users where id='local-v3-management'")[0]
    password = secrets.token_urlsafe(16)
    sql(database,"""insert into accounts(id,account_id,provider_id,user_id,password)
        values(gen_random_uuid()::text,$1,'vinhomes-password-v1',$1,$2)""",manager['id'],password_hash(password))
    token=secrets.token_urlsafe(32)
    sql(database,"insert into sessions(id,user_id,token,expires_at) values(gen_random_uuid()::text,$1,$2,now()+interval '1 hour')",manager['id'],session_hash(token))
    with door(database) as client:
        assert sign_in(client,manager['email'],'wrong')==401
        response=client.post('/auth/login',json={'identifier':manager['email'],'password':password})
        assert response.status_code==403 and 'Platform' in response.json()['detail']
        client.cookies.set(COOKIE,token)
        assert client.get('/auth/session').status_code==403
        assert client.get('/operations/me').status_code==403
    with door(database) as admin:
        admin_login(database,admin)
        assert admin.post('/auth/accounts',json={'name':'BQL không cấp tại Domain','email':'retired@example.invalid','password':password,'role':'management'}).status_code==422
        assert admin.patch('/auth/accounts/'+manager['id'],json={'role':'management','status':'active'}).status_code==422
        scope=sql(database,'select id from access_scopes where tenant_id=$1 limit 1',TENANT)[0]['id']
        assert admin.post('/admin/accounts/'+manager['id']+'/roles',json={'role_code':'management','scope_id':str(scope)}).status_code==422


def test_clean_reset_preserves_admin_config_and_text_but_has_no_fake_business_data(database,monkeypatch,tmp_path):
    monkeypatch.delenv('VINHOMES_API_EMBEDDING_API_KEY',raising=False)
    document,chunk,version=(uuid4() for _ in range(3))
    zone=sql(database,'select id from zones where tenant_id=$1 limit 1',TENANT)[0]['id']
    sql(database,"""insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience,zone_id,site_id,metadata)
        values($1,$2,'preserve-content',$3,'Tài liệu cần duyệt','procedure','resident',$4,$5,$6::jsonb)""",
        document,TENANT,version,zone,OP1,json.dumps({'sources':['https://market.vinhomes.vn/'],'frontMatter':{}}))
    sql(database,"""insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,text_content,text_hash,token_count,search_tsv)
        values($1,$2,$3,0,'Nội dung phải giữ nguyên','hash',6,to_tsvector('simple','Nội dung phải giữ nguyên'))""",chunk,TENANT,document)
    before=sql(database,'select count(*) n from users')[0]['n']
    target_name='clean_acceptance_'+uuid4().hex
    parts=urlsplit(database['admin']);target_url=urlunsplit(parts._replace(path='/'+target_name))

    async def check():
        try:
            report=await prepare(database['admin'],target_name)
            assert report['activated'] is False and report['admins']==1
            assert report['knowledge_content_and_vectors_preserved']
            with pytest.raises(SystemExit,match='already exists'):
                await prepare(database['admin'],target_name)
            from vinhomes_api.import_data import load
            with pytest.raises(SystemExit,match='exactly one site'):
                await load(target_url,str(tmp_path),False)
            await bootstrap(target_url)  # a normal restart never recreates users/tickets
            conn=await asyncpg.connect(target_url)
            try:
                assert await conn.fetchval('select count(*) from users')==1
                assert await conn.fetchval('select count(*) from sites')==3
                assert await conn.fetchval('select count(*) from units')==0
                assert await conn.fetchval('select count(*) from staff_profiles')==0
                assert await conn.fetchval('select count(*) from tickets')==0
                assert await conn.fetchval('select count(*) from scoped_user_roles')==0
                assert await conn.fetchval('select text_content from vh_knowledge_chunks where id=$1',chunk)=='Nội dung phải giữ nguyên'
                retained=await conn.fetchrow('select site_id,zone_id,metadata from vh_knowledge_documents where id=$1',document)
                assert retained['site_id']==OP1 and retained['zone_id'] is None
                assert json.loads(retained['metadata'])['retrieval_status']=='quarantined'
                for number in (1,2):
                    sid=site_id('ocean-park-'+str(number));doc,part=uuid4(),uuid4()
                    await conn.execute("""insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience,site_id)
                        values($1,$2,$3,$4,'daukiemthu','test','resident',$5)""",doc,TENANT,'scope-'+str(number),uuid4(),sid)
                    await conn.execute("""insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,text_content,text_hash,token_count,search_tsv)
                        values($1,$2,$3,0,'daukiemthu','hash',1,to_tsvector('simple','daukiemthu'))""",part,TENANT,doc)
            finally:
                await conn.close()
            engine=create_async_engine(target_url.replace('postgresql:','postgresql+asyncpg:',1))
            try:
                async with engine.begin() as db:
                    await db.execute(text("select set_config('app.tenant_id',:t,true)"),{'t':str(TENANT)})
                    one=await knowledge.search(db,TENANT,'resident',None,None,'daukiemthu',5,site_id=OP1)
                    two=await knowledge.search(db,TENANT,'resident',None,None,'daukiemthu',5,site_id=site_id('ocean-park-2'))
                    unknown=await knowledge.search(db,TENANT,'resident',None,None,'daukiemthu',5)
                    assert len(one['hits'])==len(two['hits'])==1
                    assert one['hits'][0]['documentId']!=two['hits'][0]['documentId']
                    assert unknown['hits']==[]
            finally:
                await engine.dispose()
        finally:
            owner=await asyncpg.connect(database['admin'])
            try:
                await owner.execute(f'DROP DATABASE IF EXISTS "{target_name}"')
            finally:
                await owner.close()
    asyncio.run(check())
    assert sql(database,'select count(*) n from users')[0]['n']==before
    assert sql(database,'select zone_id from vh_knowledge_documents where id=$1',document)[0]['zone_id']==zone
