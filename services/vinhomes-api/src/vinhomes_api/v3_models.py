"""Tenant model registry. Public responses contain environment names, never credential values.

A key entered in the app is sealed with the deployment's VINHOMES_API_MODEL_CREDENTIALS_KEY and never
returned; only its last four characters are shown. A unit's own model serves only that unit's agents.
"""
import base64
import os
import re
import time
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
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


def sealer() -> AESGCM:
    try:
        key = base64.b64decode(os.getenv('VINHOMES_API_MODEL_CREDENTIALS_KEY','').strip(),validate=True)
    except ValueError:
        key = b''
    if len(key) != 32: raise HTTPException(503,'Bản triển khai chưa có khóa chủ để lưu khóa API. Quản trị hệ thống cần đặt VINHOMES_API_MODEL_CREDENTIALS_KEY.')
    return AESGCM(key)


def seal(model_id, api_key: str) -> str:
    # The row id is the associated data: a sealed key copied onto another row does not open.
    nonce = os.urandom(12)
    return 'v1:'+base64.b64encode(nonce+sealer().encrypt(nonce,api_key.encode(),str(model_id).encode())).decode()


def unseal(model_id, sealed: str) -> str:
    version, _, body = sealed.partition(':')
    cipher = sealer()
    try:
        if version != 'v1': raise ValueError
        data = base64.b64decode(body)
        return cipher.decrypt(data[:12],data[12:],str(model_id).encode()).decode()
    except Exception:
        raise HTTPException(422,'Không mở được khóa API đã lưu. Nhập lại khóa cho model này.') from None


def entered_key(value: SecretStr | None) -> str | None:
    if value is None: return None
    key = value.get_secret_value().strip()
    if not 8 <= len(key) <= 500 or any(c.isspace() for c in key): raise HTTPException(422,'Khóa API không hợp lệ.')
    return key


class RegisterModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
    provider: Literal['openai','custom','deepseek','groq','google']
    kind: Literal['chat','embedding'] = 'chat'
    credential_env: str | None = Field(default=None,min_length=1,max_length=120)
    # A key typed in the app, for a provider at its own fixed address. Never stored or logged in clear.
    api_key: SecretStr | None = None
    base_url_env: str | None = Field(default=None,max_length=120)
    dimension: int | None = Field(default=None,ge=1,le=32768)

    @field_validator('credential_env')
    @classmethod
    def key_reference(cls,value):
        if value is not None and not KEY_ENV.fullmatch(value): raise ValueError('Chọn biến khóa API của nhà cung cấp model.')
        return value

    @field_validator('base_url_env')
    @classmethod
    def url_reference(cls,value):
        if value and not URL_ENV.fullmatch(value): raise ValueError('Chọn biến địa chỉ API của nhà cung cấp model.')
        return value or None

    @model_validator(mode='after')
    def one_credential(self):
        if (self.credential_env is None) == (self.api_key is None): raise ValueError('Chọn biến môi trường hoặc nhập khóa API.')
        if self.api_key is not None and (self.provider not in DEFAULT_URLS or self.base_url_env or self.kind != 'chat'):
            raise ValueError('Khóa nhập trên giao diện chỉ dùng cho model trả lời của OpenAI, DeepSeek, Groq hoặc Google.')
        return self


class UnitModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
    provider: Literal['openai','deepseek','groq','google']
    api_key: SecretStr


class NewKey(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_key: SecretStr


class ModelPermission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allowed: bool


class RoleDefault(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model_id: UUID


def runtime_config(row,new_key: str | None = None):
    if new_key is not None:
        key, base = new_key, DEFAULT_URLS.get(row['provider'],'')
    elif row.get('credential_sealed'):
        key, base = unseal(row['id'],row['credential_sealed']), DEFAULT_URLS.get(row['provider'],'')
    else:
        key = os.getenv(row['credential_env'] or '','').strip()
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


async def resolve_model(db,role: str,model_id: str | None = None,workspace_id=None):
    """Internal runtime helper. None preserves deployment fallback when no default has been saved.
    A unit's own model resolves only for a specialist of that unit (`workspace_id`)."""
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
    if row['workspace_id'] is not None:
        if role != 'specialist' or workspace_id is None or str(row['workspace_id']) != str(workspace_id):
            raise HTTPException(422,'Model riêng của một đơn vị chỉ dùng cho agent của đơn vị đó.')
    elif model_id and role == 'specialist' and not row['allowed']:
        raise HTTPException(422,'Model chưa được cho phép đơn vị sử dụng.')
    if row['check_status'] != 'ok': raise HTTPException(422,'Model phải được kiểm tra thành công trước khi sử dụng.')
    return runtime_config(row)


LISTED = '''m.id,m.name,m.provider,m.kind,m.credential_env,m.base_url_env,m.allowed,m.dimension,m.check_status,m.latency_ms,
    m.checked_at,m.credential_hint,m.workspace_id,w.name as workspace_name,
    case when m.credential_sealed is null then 'env' else 'key' end as credential_source'''


@router.get('/admin/model-registry')
async def registry(scope: Scope):
    admin(scope)
    rows = await scope[0].execute(text(f'select {LISTED} from admin_model_registry m left join workspaces w on w.id=m.workspace_id and w.tenant_id=m.tenant_id order by m.workspace_id nulls first,m.created_at,m.name'))
    defaults = await scope[0].execute(text('select role,model_id,updated_at from admin_role_models order by role'))
    return {'items':[dict(r) for r in rows.mappings()],'defaults':[dict(r) for r in defaults.mappings()]}


async def taken(db, name, provider, kind, workspace_id):
    if (await db.execute(text('select 1 from admin_model_registry where name=:name and provider=:provider and kind=:kind and workspace_id is not distinct from :workspace'),
                         {'name':name,'provider':provider,'kind':kind,'workspace':workspace_id})).first():
        raise HTTPException(409,'Model này đã được thêm. Dùng "Thay khóa" để đổi khóa API.')


async def probe(row, key: str | None = None):
    """Ask the provider for one short answer (or one embedding). `key` tries a new key before it is kept."""
    config = runtime_config(row,key)
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
    return ok, int((time.perf_counter()-started)*1000), dimension


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
    key = entered_key(body.api_key)
    # Validate references now without claiming provider availability. A real check is a separate explicit action.
    runtime_config({'id':'','name':body.name,'provider':body.provider,'kind':body.kind,'credential_env':body.credential_env,'base_url_env':body.base_url_env},key)
    await taken(scope[0],body.name,body.provider,body.kind,None)
    identity = await insert_model(scope,body.name,body.provider,body.kind,body.credential_env,body.base_url_env,body.dimension,key,None)
    return {'id':identity}


async def insert_model(scope,name,provider,kind,credential_env,base_url_env,dimension,key,workspace_id):
    identity = uuid4()
    await scope[0].execute(text(f'''insert into admin_model_registry(id,tenant_id,name,provider,kind,credential_env,credential_sealed,credential_hint,
        base_url_env,dimension,workspace_id,created_by) values(:id,{TENANT},:name,:provider,:kind,:credential_env,:sealed,:hint,:base_url_env,:dimension,:workspace,:actor)'''),
        {'id':identity,'name':name,'provider':provider,'kind':kind,'credential_env':credential_env,'sealed':seal(identity,key) if key else None,
         'hint':'…'+key[-4:] if key else None,'base_url_env':base_url_env,'dimension':dimension,'workspace':workspace_id,'actor':scope[1]})
    await audit(scope[0],scope[1],'model.registered','model',str(identity),{'name':name,'provider':provider,'kind':kind,
        'credential':'entered' if key else 'environment',**({'workspaceId':str(workspace_id)} if workspace_id else {})})
    return identity


async def model_row(db, model_id, workspace_id=None, *, unit_only=False):
    row = (await db.execute(text('select * from admin_model_registry where id=:id for update'),{'id':model_id})).mappings().first()
    if not row or (unit_only and str(row['workspace_id']) != str(workspace_id)): raise HTTPException(404,'Model không tồn tại.')
    return dict(row)


async def check_row(scope, row):
    ok, latency, dimension = await probe(row)
    await scope[0].execute(text("update admin_model_registry set check_status=:status,latency_ms=:latency,checked_at=now(),dimension=:dimension where id=:id"),{'id':row['id'],'status':'ok' if ok else 'error','latency':latency,'dimension':dimension})
    await audit(scope[0],scope[1],'model.checked','model',str(row['id']),{'name':row['name'],'ok':ok,'latency_ms':latency})
    return {'ok':ok,'latency_ms':latency,'message':'Đã kiểm tra model' if ok else 'Model chưa trả lời được. Kiểm tra tên model, khóa và địa chỉ API.'}


async def replace_key(scope, row, body: NewKey):
    """A new key replaces the old one only once the provider answers with it; until then the old key keeps working."""
    if not row['credential_sealed']: raise HTTPException(409,'Model này lấy khóa từ biến môi trường của bản triển khai.')
    key = entered_key(body.api_key)
    ok, latency, _ = await probe(row,key)
    if not ok: raise HTTPException(422,'Nhà cung cấp chưa nhận khóa mới. Khóa cũ vẫn được giữ.')
    await scope[0].execute(text("update admin_model_registry set credential_sealed=:sealed,credential_hint=:hint,check_status='ok',latency_ms=:latency,checked_at=now() where id=:id"),
                           {'id':row['id'],'sealed':seal(row['id'],key),'hint':'…'+key[-4:],'latency':latency})
    await audit(scope[0],scope[1],'model.credential_replaced','model',str(row['id']),{'name':row['name']})
    return {'ok':True}


async def remove_model(scope, row):
    """Only a model nothing depends on goes: no role default, no agent's draft and no published version."""
    used = (await scope[0].execute(text('''select (select count(*) from admin_role_models where model_id=:id)
        + (select count(distinct a.id) from agents a where a.configuration->>'model_id'=:sid or exists(
            select 1 from agent_versions v join agent_releases r on r.version_id=v.id and r.tenant_id=v.tenant_id
            where v.agent_id=a.id and r.status='published' and r.revoked_at is null and v.config->>'model_id'=:sid))'''),
        {'id':row['id'],'sid':str(row['id'])})).scalar_one()
    if used: raise HTTPException(409,f'Model đang được dùng ({used} vai trò hoặc agent). Đổi model của các agent đó trước khi xóa.')
    await scope[0].execute(text('delete from admin_model_registry where id=:id'),{'id':row['id']})
    await audit(scope[0],scope[1],'model.deleted','model',str(row['id']),{'name':row['name'],'provider':row['provider']})
    return {'ok':True}


@router.post('/admin/model-registry/{model_id}/check')
async def check(model_id: UUID,scope: Scope):
    admin(scope)
    return await check_row(scope,await model_row(scope[0],model_id))


@router.put('/admin/model-registry/{model_id}/credential')
async def admin_replace_key(model_id: UUID,body: NewKey,scope: Scope):
    admin(scope)
    return await replace_key(scope,await model_row(scope[0],model_id),body)


@router.delete('/admin/model-registry/{model_id}')
async def admin_remove(model_id: UUID,scope: Scope):
    admin(scope)
    return await remove_model(scope,await model_row(scope[0],model_id))


@router.patch('/admin/model-registry/{model_id}')
async def permission(model_id: UUID,body: ModelPermission,scope: Scope):
    admin(scope)
    row = (await scope[0].execute(text('select * from admin_model_registry where id=:id for update'),{'id':model_id})).mappings().first()
    if not row: raise HTTPException(404,'Model không tồn tại.')
    if row['workspace_id'] is not None: raise HTTPException(422,'Model riêng của một đơn vị không cấp cho đơn vị khác.')
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


async def unit_of(scope, room_id: str, *, manage: bool = False):
    """The unit (workspace) behind a management room; `manage` also requires management of that unit."""
    from .v3_room_agents import managed_room
    from .v3_agent_reviews import can_author_unit
    workspace = (await managed_room(scope[:2], room_id, lock=False))['workspace_id']
    if manage and not await can_author_unit(scope[0], scope[1], workspace):
        raise HTTPException(403, 'Chỉ Ban quản lý của đơn vị được thêm hoặc đổi model.')
    return workspace


@router.get('/rooms/{room_id}/models')
async def unit_models(room_id: str, scope: Scope):
    """What an agent of this unit may run on: the models the administrator allowed, and the unit's own."""
    workspace = await unit_of(scope, room_id)
    shared = await scope[0].execute(text("select id,name,provider,kind,check_status from admin_model_registry where workspace_id is null and allowed and kind='chat' and check_status='ok' order by name"))
    own = await scope[0].execute(text(f'select {LISTED} from admin_model_registry m left join workspaces w on w.id=m.workspace_id and w.tenant_id=m.tenant_id where m.workspace_id=:workspace order by m.created_at'), {'workspace': workspace})
    from .v3_agent_reviews import can_author_unit
    return {'items': [{**dict(r), 'own': False} for r in shared.mappings()] + [{**dict(r), 'own': True} for r in own.mappings()],
            'canManage': await can_author_unit(scope[0], scope[1], workspace)}


@router.post('/rooms/{room_id}/models', status_code=201)
async def add_unit_model(room_id: str, body: UnitModel, scope: Scope):
    workspace = await unit_of(scope, room_id, manage=True)
    key = entered_key(body.api_key)
    runtime_config({'id': '', 'name': body.name, 'provider': body.provider, 'kind': 'chat', 'credential_env': None, 'base_url_env': None}, key)
    await taken(scope[0], body.name, body.provider, 'chat', workspace)
    return {'id': await insert_model(scope, body.name, body.provider, 'chat', None, None, None, key, workspace)}


@router.post('/rooms/{room_id}/models/{model_id}/check')
async def check_unit_model(room_id: str, model_id: UUID, scope: Scope):
    workspace = await unit_of(scope, room_id, manage=True)
    return await check_row(scope, await model_row(scope[0], model_id, workspace, unit_only=True))


@router.put('/rooms/{room_id}/models/{model_id}/credential')
async def replace_unit_key(room_id: str, model_id: UUID, body: NewKey, scope: Scope):
    workspace = await unit_of(scope, room_id, manage=True)
    return await replace_key(scope, await model_row(scope[0], model_id, workspace, unit_only=True), body)


@router.delete('/rooms/{room_id}/models/{model_id}')
async def remove_unit_model(room_id: str, model_id: UUID, scope: Scope):
    workspace = await unit_of(scope, room_id, manage=True)
    return await remove_model(scope, await model_row(scope[0], model_id, workspace, unit_only=True))


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
