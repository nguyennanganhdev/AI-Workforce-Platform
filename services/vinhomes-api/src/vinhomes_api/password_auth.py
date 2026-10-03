"""PostgreSQL password identities for the V3 apps; independent of OpenBot SSO.

The existing accounts/sessions tables use dedicated provider/token namespaces.
Only hashes of passwords and opaque session tokens are stored in PostgreSQL.
"""
import asyncio
import hashlib
import hmac
import secrets
import time
from collections import OrderedDict
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

router = APIRouter(prefix="/auth", tags=["Password authentication"])
COOKIE = "vinhomes_session"
PROVIDER = "vinhomes-password-v1"
TTL = 8 * 60 * 60
_attempts: OrderedDict[str, list[float]] = OrderedDict()
_hash_slots = asyncio.Semaphore(2)


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=131072, r=8, p=1, maxmem=256*1024*1024)
    return "scrypt-v1$" + salt.hex() + "$" + digest.hex()


def check_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt-v1" or len(salt) != 32 or len(expected) != 128:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=131072, r=8, p=1, maxmem=256*1024*1024)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def session_hash(token: str) -> str:
    return "vinhomes-v1:" + hashlib.sha256(token.encode()).hexdigest()


def enabled(request: Request):
    if not request.app.state.settings.password_auth:
        raise HTTPException(404, "Password authentication is not enabled")
    if request.app.state.engine is None:
        raise HTTPException(503, "Database is not configured")
    return request.app.state.engine


def rate_limit(request: Request, identifier: str):
    # Bounded, single-process local deployment limiter. Use a shared limiter before scaling workers.
    now = time.monotonic()
    for key, limit in [("ip:" + (request.client.host if request.client else "unknown"), 60), ("account:" + identifier, 10)]:
        recent = [t for t in _attempts.get(key, []) if now-t < 300]
        if len(recent) >= limit:
            raise HTTPException(429, "Thử đăng nhập quá nhiều lần. Vui lòng chờ 5 phút.", headers={"Retry-After":"300"})
        _attempts[key] = recent + [now]
        _attempts.move_to_end(key)
    while len(_attempts) > 10000:
        _attempts.popitem(last=False)


async def context(db, request: Request, actor: str = ""):
    await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id',:actor,true)"),
                     {"tenant":str(request.app.state.settings.tenant_id),"actor":actor})


async def authenticated_user(request: Request) -> dict:
    engine = enabled(request)
    token = request.cookies.get(COOKIE, "")
    if not 32 <= len(token) <= 128:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    async with engine.begin() as db:
        user = (await db.execute(text("""
            select u.id,u.name,u.email,u.phone_e164 from sessions s join users u on u.id=s.user_id
            where s.token=:token and s.expires_at>now() and u.status='active'
        """), {"token":session_hash(token)})).mappings().first()
        if not user:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn hoặc tài khoản bị khóa.")
        await context(db,request,user["id"])
        membership = (await db.execute(text("select status from tenant_memberships where user_id=:id and tenant_id=cast(:tenant as uuid)"),
                                      {"id":user["id"],"tenant":str(request.app.state.settings.tenant_id)})).scalar_one_or_none()
        if membership not in {"active","pending"}:
            raise HTTPException(403, "Tài khoản không còn thuộc phạm vi hệ thống.")
        return dict(user)


class Credentials(BaseModel):
    identifier: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=1,max_length=128)


class Registration(BaseModel):
    name: str = Field(min_length=2,max_length=100)
    email: str = Field(min_length=5,max_length=254)
    password: str = Field(min_length=12,max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=12,max_length=128)


@router.get("/config")
async def config(request: Request):
    return {"password":request.app.state.settings.password_auth}


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response):
    engine = enabled(request)
    identifier = body.identifier.strip().lower()
    rate_limit(request,identifier)
    async with engine.begin() as db:
        await context(db,request)
        user = (await db.execute(text("""
            select u.id,u.name,u.email,a.password from users u join accounts a on a.user_id=u.id
            join tenant_memberships m on m.user_id=u.id
            where (lower(u.email)=:identifier or u.phone_e164=:identifier)
              and a.provider_id=:provider and u.status='active'
              and m.tenant_id=cast(:tenant as uuid) and m.status in ('active','pending')
            for update of a
        """), {"identifier":identifier,"provider":PROVIDER,"tenant":str(request.app.state.settings.tenant_id)})).mappings().first()
        # Same expensive check for nonexistent identities, without storing a default password.
        encoded = user["password"] if user else "scrypt-v1$" + "00"*16 + "$" + "00"*64
        async with _hash_slots:
            valid = await asyncio.to_thread(check_password,body.password,encoded)
        if not user or not valid:
            raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng.")
        token = secrets.token_urlsafe(32)
        old = request.cookies.get(COOKIE, "")
        if old:
            await db.execute(text("delete from sessions where token=:token"), {"token":session_hash(old)})
        await db.execute(text("insert into sessions(id,user_id,token,expires_at) values(:id,:user,:token,now()+interval '8 hours')"),
                         {"id":str(uuid4()),"user":user["id"],"token":session_hash(token)})
    response.set_cookie(COOKIE,token,max_age=TTL,httponly=True,secure=request.url.scheme=="https",samesite="lax",path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"user":{"id":user["id"],"name":user["name"],"email":user["email"]}}


@router.get("/session")
async def session(request: Request, response: Response):
    user = await authenticated_user(request)
    async with enabled(request).begin() as db:
        await context(db, request, user["id"])
        membership_status = (await db.execute(text("select status from tenant_memberships where user_id=:id and tenant_id=cast(:tenant as uuid)"), {"id":user["id"], "tenant":str(request.app.state.settings.tenant_id)})).scalar_one()
        is_admin = bool((await db.execute(text("select exists(select 1 from platform_admins where user_id=:id)"), {"id":user["id"]})).scalar_one())
    response.headers["Cache-Control"] = "no-store"
    return {"user":user, "membershipStatus":membership_status, "administrator":is_admin}


@router.post("/logout")
async def logout(request: Request, response: Response):
    engine = enabled(request)
    async with engine.begin() as db:
        await db.execute(text("delete from sessions where token=:token"), {"token":session_hash(request.cookies.get(COOKIE,""))})
    response.delete_cookie(COOKIE,path="/")
    return {"ok":True}


async def administrator(request: Request):
    user = await authenticated_user(request)
    async with enabled(request).begin() as db:
        if not (await db.execute(text("select 1 from platform_admins where user_id=:id"),{"id":user["id"]})).first():
            raise HTTPException(403,"Chỉ quản trị viên được quản lý tài khoản và cấp quyền.")
    return user


class AccountCreate(Registration):
    role: Literal["customer","staff","management"]


class AccountAccess(BaseModel):
    role: Literal["customer","staff","management"]
    status: Literal["active","suspended"]


async def grant_access(db,request:Request,user_id:str,actor:str,role:str,status:str):
    await context(db,request,actor)
    tenant = str(request.app.state.settings.tenant_id)
    member = (await db.execute(text("select id from tenant_memberships where user_id=:user and tenant_id=cast(:tenant as uuid) for update"),{"user":user_id,"tenant":tenant})).scalar_one_or_none()
    if not member:
        raise HTTPException(404,"Tài khoản không thuộc tenant này.")
    await db.execute(text("update tenant_memberships set status=:status,joined_at=coalesce(joined_at,now()),updated_at=now() where id=:id"),{"id":member,"status":status})
    await db.execute(text("update scoped_user_roles set valid_to=now() where membership_id=:member and (valid_to is null or valid_to>now())"),{"member":member})
    if status == "active":
        scope = (await db.execute(text("select id from access_scopes where tenant_id=cast(:tenant as uuid) and kind='tenant' limit 1"),{"tenant":tenant})).scalar_one_or_none()
        if scope is None:
            scope = (await db.execute(text("insert into access_scopes(tenant_id,kind) values(cast(:tenant as uuid),'tenant') returning id"),{"tenant":tenant})).scalar_one()
        await db.execute(text("insert into scoped_user_roles(tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values(cast(:tenant as uuid),:member,:scope,:role,:actor,now())"),{"tenant":tenant,"member":member,"scope":scope,"role":role,"actor":actor})
    await db.execute(text("delete from sessions where user_id=:id and token like 'vinhomes-v1:%'"),{"id":user_id})


@router.get("/accounts")
async def list_accounts(request:Request):
    actor=await administrator(request)
    async with enabled(request).begin() as db:
        await context(db,request,actor["id"])
        result=await db.execute(text("""
            select u.id,u.name,u.email,m.status,
              exists(select 1 from platform_admins pa where pa.user_id=u.id) as administrator,
              coalesce((select r.role_code from scoped_user_roles r where r.membership_id=m.id
                and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()) order by r.valid_from desc limit 1),'customer') as role
            from users u join tenant_memberships m on m.user_id=u.id
            where m.tenant_id=cast(:tenant as uuid) order by u.created_at desc limit 200
        """),{"tenant":str(request.app.state.settings.tenant_id)})
        return {"items":[dict(r) for r in result.mappings()]}


@router.post("/accounts",status_code=201)
async def create_account(body:AccountCreate,request:Request):
    actor=await administrator(request)
    email=body.email.strip().lower()
    if "@" not in email or any(c.isspace() for c in email):
        raise HTTPException(422,"Email không hợp lệ.")
    async with _hash_slots:
        hashed=await asyncio.to_thread(password_hash,body.password)
    async with enabled(request).begin() as db:
        await context(db,request,actor["id"])
        await db.execute(text("select pg_advisory_xact_lock(hashtext(:email))"),{"email":email})
        if (await db.execute(text("select 1 from users where lower(email)=:email"),{"email":email})).first():
            raise HTTPException(409,"Email đã được sử dụng.")
        user=str(uuid4())
        await db.execute(text("insert into users(id,email,name,status) values(:id,:email,:name,'active')"),{"id":user,"email":email,"name":body.name.strip()})
        await db.execute(text("insert into accounts(id,account_id,provider_id,user_id,password) values(:id,:user,:provider,:user,:password)"),{"id":str(uuid4()),"user":user,"provider":PROVIDER,"password":hashed})
        await db.execute(text("insert into tenant_memberships(tenant_id,user_id,status) values(cast(:tenant as uuid),:user,'pending')"),{"tenant":str(request.app.state.settings.tenant_id),"user":user})
        await grant_access(db,request,user,actor["id"],body.role,"active")
    return {"id":user}


@router.patch("/accounts/{user_id}")
async def change_access(user_id:str,body:AccountAccess,request:Request):
    actor=await administrator(request)
    async with enabled(request).begin() as db:
        if user_id == actor["id"] or (await db.execute(text("select 1 from platform_admins where user_id=:id"),{"id":user_id})).first():
            raise HTTPException(409,"Không thể sửa quyền tài khoản quản trị qua màn hình này.")
        await grant_access(db,request,user_id,actor["id"],body.role,body.status)
    return {"ok":True}


@router.post("/register",status_code=201)
async def register(body: Registration,request: Request):
    engine = enabled(request)
    email = body.email.strip().lower()
    if "@" not in email or any(c.isspace() for c in email):
        raise HTTPException(422,"Email không hợp lệ.")
    rate_limit(request,email)
    async with _hash_slots:
        hashed = await asyncio.to_thread(password_hash,body.password)
    async with engine.begin() as db:
        await context(db,request)
        await db.execute(text("select pg_advisory_xact_lock(hashtext(:email))"),{"email":email})
        exists = (await db.execute(text("select 1 from users where lower(email)=:email"),{"email":email})).first()
        if exists:
            raise HTTPException(409,"Không thể đăng ký thông tin này. Hãy đăng nhập hoặc liên hệ quản trị viên.")
        user = str(uuid4())
        await db.execute(text("insert into users(id,email,name,status) values(:id,:email,:name,'active')"),{"id":user,"email":email,"name":body.name.strip()})
        await db.execute(text("insert into accounts(id,account_id,provider_id,user_id,password) values(:id,:user,:provider,:user,:password)"),{"id":str(uuid4()),"user":user,"provider":PROVIDER,"password":hashed})
        await db.execute(text("insert into tenant_memberships(tenant_id,user_id,status) values(cast(:tenant as uuid),:user,'pending')"),{"tenant":str(request.app.state.settings.tenant_id),"user":user})
    return {"nextStep":"membership-pending"}


@router.post("/change-password")
async def change_password(body: PasswordChange,request: Request,response: Response):
    user = await authenticated_user(request)
    rate_limit(request,user["id"])
    async with enabled(request).begin() as db:
        row = (await db.execute(text("select id,password from accounts where user_id=:id and provider_id=:provider for update"),{"id":user["id"],"provider":PROVIDER})).mappings().one()
        async with _hash_slots:
            if not await asyncio.to_thread(check_password,body.current_password,row["password"]):
                raise HTTPException(401,"Mật khẩu hiện tại không đúng.")
            hashed = await asyncio.to_thread(password_hash,body.new_password)
        await db.execute(text("update accounts set password=:password,updated_at=now() where id=:id"),{"id":row["id"],"password":hashed})
        await db.execute(text("delete from sessions where user_id=:id and token like 'vinhomes-v1:%'"),{"id":user["id"]})
    response.delete_cookie(COOKIE,path="/")
    return {"ok":True}
