"""Tenant model registry. Public responses contain environment names, never credential values."""
import os
import re
import time
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from .v3_auth import scoped_connection
from .v3_audit import audit

router = APIRouter(tags=['Model registry'])
Scope = Annotated[tuple, Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
ROLES = {'reception','supervisor','specialist','factory','embedding'}
KEY_ENV = re.compile(r'^(?:OPENAI|RECEPTION|COORDINATION|SPECIALIST|FACTORY|EMBEDDING|GOOGLE|GEMINI|DEEPSEEK|GROQ|CUSTOM)(?:_[A-Z0-9]+)*_API_KEY$')
URL_ENV = re.compile(r'^(?:OPENAI|RECEPTION|COORDINATION|SPECIALIST|FACTORY|EMBEDDING|GOOGLE|GEMINI|DEEPSEEK|GROQ|CUSTOM)(?:_[A-Z0-9]+)*_BASE_URL$')
DEFAULT_URLS = {'openai':'https://api.openai.com/v1','deepseek':'https://api.deepseek.com/v1','groq':'https://api.groq.com/openai/v1','google':'https://generativelanguage.googleapis.com/v1beta/openai'}


def admin(scope):
    if not scope[2]: raise HTTPException(403,'Platform admin required')


class RegisterModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
    provider: Literal['openai','custom','deepseek','groq','google']
    kind: Literal['chat','embedding'] = 'chat'
    credential_env: str = Field(min_length=1,max_length=120)
    base_url_env: str | None = Field(default=None,max_length=120)
    dimension: int | None = Field(default=None,ge=1,le=32768)

    @field_validator('credential_env')
    @classmethod
    def key_reference(cls,value):
        if not KEY_ENV.fullmatch(value): raise ValueError('Chọn biến khóa API của nhà cung cấp model.')
        return value

    @field_validator('base_url_env')
    @classmethod
    def url_reference(cls,value):
        if value and not URL_ENV.fullmatch(value): raise ValueError('Chọn biến địa chỉ API của nhà cung cấp model.')
        return value or None


class ModelPermission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allowed: bool


class RoleDefault(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model_id: UUID


def runtime_config(row):
    key = os.getenv(row['credential_env'],'').strip()
    base = os.getenv(row['base_url_env'],'').strip() if row['base_url_env'] else DEFAULT_URLS.get(row['provider'],'')
    if not key or not base: raise HTTPException(422,'Biến khóa hoặc địa chỉ API chưa được cấu hình trên bản triển khai.')
    parsed = urlsplit(base)
    # Only deployment-owned references can determine an endpoint. Never accept a URL or secret from the UI.
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422,'Địa chỉ API trong bản triển khai không hợp lệ.')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
        raise HTTPException(422,'Địa chỉ API ngoài máy cục bộ phải dùng HTTPS.')
    if key.startswith(('sk-proj-','sk-svcacct-')) and (row['provider'] != 'openai' or parsed.hostname != 'api.openai.com'):
        raise HTTPException(422,'Khóa OpenAI phải dùng đúng nhà cung cấp và địa chỉ OpenAI.')
    if key.startswith('sk-or-') and parsed.hostname != 'openrouter.ai':
        raise HTTPException(422,'Khóa OpenRouter phải dùng đúng địa chỉ OpenRouter.')
    return {'model_id':str(row['id']),'model_name':row['name'],'provider':row['provider'],'kind':row['kind'],'api_key':key,'base_url':base.rstrip('/')}


async def resolve_model(db,role: str,model_id: str | None = None):
    """Internal runtime helper. None preserves deployment fallback when no default has been saved."""
    if role not in ROLES: raise HTTPException(422,'Vai trò model không hợp lệ.')
    if model_id:
        try: model_id = str(UUID(model_id))
        except (ValueError, TypeError, AttributeError): raise HTTPException(422,'Mã model không hợp lệ.') from None
        row = (await db.execute(text('select * from admin_model_registry where id=cast(:id as uuid)'),{'id':model_id})).mappings().first()
    else:
        row = (await db.execute(text('select m.* from admin_role_models r join admin_model_registry m on m.id=r.model_id and m.tenant_id=r.tenant_id where r.role=:role'),{'role':role})).mappings().first()
    if not row:
        if model_id: raise HTTPException(422,'Model không thuộc tổ chức này.')
        return None
    if row['kind'] != ('embedding' if role == 'embedding' else 'chat'):
        raise HTTPException(422,'Loại model không phù hợp với vai trò.')
    if model_id and role == 'specialist' and not row['allowed']:
        raise HTTPException(422,'Model chưa được cho phép đơn vị sử dụng.')
    if row['check_status'] != 'ok': raise HTTPException(422,'Model phải được kiểm tra thành công trước khi sử dụng.')
    return runtime_config(row)


@router.get('/admin/model-registry')
async def registry(scope: Scope):
    admin(scope)
    rows = await scope[0].execute(text('select id,name,provider,kind,credential_env,base_url_env,allowed,dimension,check_status,latency_ms,checked_at from admin_model_registry order by created_at,name'))
    defaults = await scope[0].execute(text('select role,model_id,updated_at from admin_role_models order by role'))
    return {'items':[dict(r) for r in rows.mappings()],'defaults':[dict(r) for r in defaults.mappings()]}


@router.get('/models/allowed')
async def allowed(scope: Scope):
    rows = await scope[0].execute(text("select id,name,provider,kind from admin_model_registry where allowed and kind='chat' and check_status='ok' order by name"))
    # Staff cannot consume management models solely because they share a tenant.
    if not scope[2]:
        management = (await scope[0].execute(text("select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id where m.user_id=:actor and m.status='active' and r.role_code='management' and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()) limit 1"),{'actor':scope[1]})).first()
        if not management: raise HTTPException(403,'Management role required')
    return {'items':[dict(r) for r in rows.mappings()]}


@router.post('/admin/model-registry',status_code=201)
async def register(body: RegisterModel,scope: Scope):
    admin(scope)
    if body.kind == 'chat' and body.dimension is not None: raise HTTPException(422,'Model trả lời không có số chiều embedding.')
    # Validate references now without claiming provider availability. A real check is a separate explicit action.
    runtime_config({'id':'','name':body.name,'provider':body.provider,'kind':body.kind,'credential_env':body.credential_env,'base_url_env':body.base_url_env})
    identity = (await scope[0].execute(text(f'insert into admin_model_registry(tenant_id,name,provider,kind,credential_env,base_url_env,dimension,created_by) values({TENANT},:name,:provider,:kind,:credential_env,:base_url_env,:dimension,:actor) returning id'),{**body.model_dump(),'actor':scope[1]})).scalar_one()
    await audit(scope[0],scope[1],'model.registered','model',str(identity),{'name':body.name,'provider':body.provider,'kind':body.kind})
    return {'id':identity}


@router.post('/admin/model-registry/{model_id}/check')
async def check(model_id: UUID,scope: Scope):
    admin(scope)
    row = (await scope[0].execute(text('select * from admin_model_registry where id=:id for update'),{'id':model_id})).mappings().first()
    if not row: raise HTTPException(404,'Model không tồn tại.')
    config = runtime_config(row)
    started = time.perf_counter()
    ok = False
    dimension = row['dimension']
    try:
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            if row['kind'] == 'embedding':
                payload = {'model':row['name'],'input':'Kiểm tra kết nối'}
                if dimension and row['provider'] == 'openai': payload['dimensions'] = dimension
                reply = await client.post(config['base_url']+'/embeddings',headers={'Authorization':'Bearer '+config['api_key']},json=payload)
                values = reply.json()['data'][0]['embedding'] if reply.status_code == 200 else []
                ok = isinstance(values,list) and len(values)>0 and all(isinstance(v,(int,float)) for v in values)
                if ok:
                    if dimension and len(values) != dimension: ok = False
                    else: dimension = len(values)
            else:
                payload = {'model':row['name'],'messages':[{'role':'user','content':'Chỉ trả lời OK.'}],('max_completion_tokens' if row['provider']=='openai' else 'max_tokens'):16}
                if row['provider'] == 'openai' and row['name'] == 'gpt-6-luna': payload['reasoning_effort'] = 'none'
                reply = await client.post(config['base_url']+'/chat/completions',headers={'Authorization':'Bearer '+config['api_key']},json=payload)
                ok = reply.status_code == 200 and bool(reply.json().get('choices'))
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError):
        ok = False
    latency = int((time.perf_counter()-started)*1000)
    await scope[0].execute(text("update admin_model_registry set check_status=:status,latency_ms=:latency,checked_at=now(),dimension=:dimension where id=:id"),{'id':model_id,'status':'ok' if ok else 'error','latency':latency,'dimension':dimension})
    await audit(scope[0],scope[1],'model.checked','model',str(model_id),{'name':row['name'],'ok':ok,'latency_ms':latency})
    return {'ok':ok,'latency_ms':latency,'message':'Đã kiểm tra model' if ok else 'Model chưa trả lời được. Kiểm tra tên model, khóa và địa chỉ API.'}


@router.patch('/admin/model-registry/{model_id}')
async def permission(model_id: UUID,body: ModelPermission,scope: Scope):
    admin(scope)
    row = (await scope[0].execute(text('select * from admin_model_registry where id=:id for update'),{'id':model_id})).mappings().first()
    if not row: raise HTTPException(404,'Model không tồn tại.')
    if body.allowed and (row['kind'] != 'chat' or row['check_status'] != 'ok'):
        raise HTTPException(422,'Chỉ model trả lời đã kiểm tra thành công được cấp cho đơn vị.')
    await scope[0].execute(text('update admin_model_registry set allowed=:allowed where id=:id'),{'id':model_id,'allowed':body.allowed})
    await audit(scope[0],scope[1],'model.permission_changed','model',str(model_id),{'name':row['name'],'allowed':body.allowed})
    return {'ok':True}


@router.put('/admin/model-defaults/{role}')
async def set_default(role: str,body: RoleDefault,scope: Scope):
    admin(scope)
    await scope[0].execute(text("select pg_advisory_xact_lock(hashtext(current_setting('app.tenant_id')||'-role-models'))"))
    config = await resolve_model(scope[0],role,str(body.model_id))
    if role == 'embedding':
        row = (await scope[0].execute(text('select dimension from admin_model_registry where id=:id'),{'id':body.model_id})).mappings().one()
        active = (await scope[0].execute(text('select provider,model_name,dimension from embedding_models where active order by updated_at desc limit 1'))).mappings().first()
        populated = (await scope[0].execute(text('select exists(select 1 from knowledge_embeddings limit 1)'))).scalar_one()
        if row['dimension'] != 1536 or (active and (active['model_name'] != config['model_name'] or active['provider'] != config['provider'] or active['dimension'] != row['dimension'])) or (populated and not active):
            raise HTTPException(409,'Kho tri thức hiện có chỉ chấp nhận cùng model và 1536 chiều. Cần quy trình nhập lại kho riêng trước khi đổi model.')
    await scope[0].execute(text(f'insert into admin_role_models(tenant_id,role,model_id,updated_by) values({TENANT},:role,:model,:actor) on conflict(tenant_id,role) do update set model_id=excluded.model_id,updated_at=now(),updated_by=excluded.updated_by'),{'role':role,'model':body.model_id,'actor':scope[1]})
    await audit(scope[0],scope[1],'model.default_changed','model_role',role,{'role':role,'model_name':config['model_name'],'model_id':str(body.model_id)})
    return {'ok':True,'role':role,'model_id':body.model_id}


@router.delete('/admin/model-defaults/{role}')
async def clear_default(role: str, scope: Scope):
    admin(scope)
    if role not in ROLES:
        raise HTTPException(422, 'Vai trò model không hợp lệ.')
    await scope[0].execute(text("select pg_advisory_xact_lock(hashtext(current_setting('app.tenant_id')||'-role-models'))"))
    previous = (await scope[0].execute(text('delete from admin_role_models where role=:role returning model_id'), {'role': role})).scalar_one_or_none()
    if previous is not None:
        await audit(scope[0], scope[1], 'model.default_cleared', 'model_role', role,
                    {'role': role, 'previous_model_id': str(previous), 'fallback': 'deployment'})
    return {'ok': True, 'role': role, 'model_id': None}


from .v3_coordination import Scope as CoordinationScope
from .reception_delegation import DelegatedScope as ReceptionScope
from fastapi.responses import JSONResponse

@router.get('/internal/coordination/v1/model-config/{role}')
async def coordination_model_config(role: str,scope: CoordinationScope):
    if role not in ('supervisor','specialist'): raise HTTPException(403,'Coordination role required')
    return JSONResponse({'config':await resolve_model(scope,role)},headers={'Cache-Control':'no-store'})


@router.get('/internal/reception/v1/model-config')
async def reception_model_config(scope: ReceptionScope):
    return JSONResponse({'config':await resolve_model(scope[0],'reception')},headers={'Cache-Control':'no-store'})
