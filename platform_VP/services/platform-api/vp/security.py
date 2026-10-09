import hashlib
import hmac
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select

from .config import settings
from .db import Audit, Login, Membership, RateWindow, User, now, transaction


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("Mật khẩu cần từ 12 đến 256 ký tự")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return f"pbkdf2:600000:{salt.hex()}:{digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    _, rounds, salt, digest = stored.split(":")
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(value.hex(), digest)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def cipher() -> Fernet:
    key = settings.encryption_key.get_secret_value()
    if not key:
        raise RuntimeError("VP_ENCRYPTION_KEY must be configured (Fernet key)")
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return cipher().decrypt(value.encode()).decode()


@dataclass
class Principal:
    user_id: str
    workspace: str
    role: str


async def current_user(request: Request) -> Principal:
    token = request.cookies.get("vp_session", "")
    workspace = request.headers.get("X-Workspace-ID", "default")
    async with transaction() as db:
        login = await db.get(Login, token_digest(token))
        if login is None or login.expires <= now():
            raise HTTPException(401, "Cần đăng nhập")
        user = await db.get(User, login.user_id)
        membership = await db.get(Membership, (workspace, login.user_id))
        if user is None or user.disabled or membership is None:
            raise HTTPException(403, "Không có quyền truy cập workspace")
        return Principal(user.id, workspace, membership.role)


async def operator(p: Principal = Depends(current_user)) -> Principal:
    if p.role not in {"admin", "operator"}:
        raise HTTPException(403, "Cần quyền vận hành")
    return p


async def admin(p: Principal = Depends(current_user)) -> Principal:
    if p.role != "admin":
        raise HTTPException(403, "Cần quyền quản trị")
    return p


def audit(db, p: Principal, action: str, target: str, body: dict | None = None):
    db.add(
        Audit(workspace=p.workspace, actor=p.user_id, action=action, target=target, body=body or {})
    )


async def bootstrap():
    cipher()  # Fail closed; never silently replace a lost encryption key.
    if not settings.bootstrap_email:
        return
    async with transaction() as db:
        if await db.scalar(select(User.id).limit(1)):
            return
        user = User(
            email=settings.bootstrap_email.lower().strip(),
            password=hash_password(settings.bootstrap_password.get_secret_value()),
        )
        db.add(user)
        await db.flush()
        db.add(Membership(workspace="default", user_id=user.id, role="admin"))


async def login_attempt(key: str):
    # Shared across API replicas. No raw IP/email is retained.
    bucket = int(now() // 300)
    async with transaction() as db:
        from .limits import upsert_rate

        count = await upsert_rate(db, "login:" + token_digest(key), bucket, 1, 0)
        if count.requests > settings.login_attempts:
            raise HTTPException(429, "Quá nhiều lần đăng nhập; thử lại sau 5 phút")
        await db.execute(delete(RateWindow).where(RateWindow.bucket < bucket - 288))


def valid_origin(request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    origin = request.headers.get("origin")
    if origin:
        allowed = {x.strip() for x in settings.trusted_origins.split(",")}
        # Same-origin reverse proxy is safe, including non-default ports.
        own = f"{request.url.scheme}://{request.headers.get('host', '')}"
        return origin in allowed or origin == own
    return request.headers.get("sec-fetch-site") not in {"cross-site", "same-site"}


async def validate_endpoint(url: str):
    import asyncio
    import ipaddress
    import socket

    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise ValueError("Endpoint phải là HTTP(S), không chứa thông tin đăng nhập")
    if settings.allow_private_endpoints:
        return
    if parsed.scheme != "https":
        raise ValueError("Endpoint công khai phải sử dụng HTTPS")
    addresses = await asyncio.get_running_loop().getaddrinfo(
        parsed.hostname,
        parsed.port or 443,
        type=socket.SOCK_STREAM,
    )
    if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Endpoint nội bộ bị chặn; cần cấu hình quản trị riêng")
