"""Email password recovery; disabled until SMTP and the public HTTPS origin are configured."""

import asyncio
import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import password_auth as auth
from .v3_audit import audit


class RecoveryRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class RecoveryConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def mail_config():
    host = os.getenv("VINHOMES_SMTP_HOST", "").strip()
    sender = os.getenv("VINHOMES_SMTP_FROM", "").strip()
    origin = os.getenv("VINHOMES_PUBLIC_URL", "").rstrip("/")
    parsed = urlsplit(origin)
    if not host or "@" not in sender or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise HTTPException(503, "Khôi phục mật khẩu chưa được cấu hình. Vui lòng liên hệ quản trị viên.")
    return host, sender, origin


def send_reset_email(host: str, sender: str, email: str, link: str):
    message = EmailMessage()
    message["Subject"] = "Vinhomes — Đặt lại mật khẩu"
    message["From"] = sender
    message["To"] = email
    message.set_content("Bạn đã yêu cầu đặt lại mật khẩu Vinhomes. Link có hiệu lực 15 phút, dùng một lần:\n\n"
                        + link + "\n\nNếu không yêu cầu thao tác này, bạn có thể bỏ qua email.")
    secure = os.getenv("VINHOMES_SMTP_SECURITY", "starttls")
    if secure not in {"starttls", "ssl"}:
        raise ValueError("SMTP security must be starttls or ssl")
    port = int(os.getenv("VINHOMES_SMTP_PORT", "465" if secure == "ssl" else "587"))
    transport = smtplib.SMTP_SSL if secure == "ssl" else smtplib.SMTP
    options = {"context": ssl.create_default_context()} if secure == "ssl" else {}
    with transport(host, port, timeout=10, **options) as smtp:
        if secure == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        username = os.getenv("VINHOMES_SMTP_USERNAME", "")
        if username:
            smtp.login(username, os.getenv("VINHOMES_SMTP_PASSWORD", ""))
        smtp.send_message(message)


@auth.router.post("/password-reset/request")
async def request_reset(body: RecoveryRequest, request: Request, response: Response):
    engine = auth.enabled(request)
    host, sender, origin = mail_config()
    email = body.email.strip().lower()
    if "@" not in email or any(c.isspace() for c in email):
        raise HTTPException(422, "Email không hợp lệ.")
    await auth.rate_limit(request, "reset:" + email)
    async with engine.begin() as db:
        await auth.context(db, request)
        user = (await db.execute(text("""select u.id,u.email from users u join accounts a on a.user_id=u.id
            join tenant_memberships m on m.user_id=u.id where lower(u.email)=:email and u.status='active'
            and a.provider_id=:provider and m.tenant_id=cast(:tenant as uuid) and m.status in ('active','pending')"""),
            {"email": email, "provider": auth.PROVIDER, "tenant": str(request.app.state.settings.tenant_id)})).mappings().first()
        if user:
            token = secrets.token_urlsafe(32)
            await db.execute(text("delete from password_reset_tokens where expires_at<now()"))
            await db.execute(text("""insert into password_reset_tokens(token_hash,tenant_id,user_id,expires_at)
                values(:hash,cast(:tenant as uuid),:user,now()+interval '15 minutes')"""),
                {"hash": hashlib.sha256(token.encode()).hexdigest(), "tenant": str(request.app.state.settings.tenant_id), "user": user["id"]})
            try:
                # Token stays in the fragment: reverse proxies never receive it in request URLs or access logs.
                await asyncio.to_thread(send_reset_email, host, sender, user["email"], origin + "/login#reset-password?" + urlencode({"token": token}))
            except Exception:
                # Same public response as an unknown account, including during a mail outage.
                await db.execute(text("delete from password_reset_tokens where token_hash=:hash"),
                                 {"hash":hashlib.sha256(token.encode()).hexdigest()})
                logging.getLogger(__name__).warning("Password recovery email delivery failed; token discarded")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "message": "Nếu tài khoản phù hợp, hướng dẫn khôi phục sẽ được gửi qua email."}


@auth.router.post("/password-reset/confirm")
async def confirm_reset(body: RecoveryConfirm, request: Request, response: Response):
    engine = auth.enabled(request)
    await auth.rate_limit(request, "reset-token:" + hashlib.sha256(body.token.encode()).hexdigest())
    async with engine.begin() as db:
        await auth.context(db, request)
        # Lock identity before token: concurrent resets and ordinary password changes serialize on the account.
        identity = (await db.execute(text("""select a.id,a.user_id from accounts a join users u on u.id=a.user_id
            join tenant_memberships m on m.user_id=u.id join password_reset_tokens t on t.user_id=u.id and t.tenant_id=m.tenant_id
            where t.token_hash=:hash and t.used_at is null and t.expires_at>now() and t.created_at>=a.updated_at and u.status='active'
              and m.status in ('active','pending') and a.provider_id=:provider and m.tenant_id=cast(:tenant as uuid) for update of a"""),
            {"hash": hashlib.sha256(body.token.encode()).hexdigest(), "provider": auth.PROVIDER,
             "tenant": str(request.app.state.settings.tenant_id)})).mappings().first()
        if not identity:
            raise HTTPException(400, "Link khôi phục không hợp lệ, đã dùng hoặc hết hạn.")
        used = (await db.execute(text("""update password_reset_tokens set used_at=now()
            where token_hash=:hash and used_at is null and expires_at>now() returning user_id"""),
            {"hash": hashlib.sha256(body.token.encode()).hexdigest()})).first()
        if not used:
            raise HTTPException(400, "Link khôi phục không hợp lệ, đã dùng hoặc hết hạn.")
        async with auth._hash_slots:
            hashed = await asyncio.to_thread(auth.password_hash, body.new_password)
        await db.execute(text("update accounts set password=:password,updated_at=now() where id=:id"), {"password": hashed, "id": identity["id"]})
        await db.execute(text("update password_reset_tokens set used_at=now() where user_id=:user and used_at is null"), {"user": identity["user_id"]})
        await db.execute(text("delete from sessions where user_id=:user and token like 'vinhomes-v1:%'"), {"user": identity["user_id"]})
        await audit(db, identity["user_id"], "account.password_recovered", "user", identity["user_id"], {})
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(auth.cookie(request), path="/")
    return {"ok": True}
