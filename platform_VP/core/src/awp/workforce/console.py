"""Human console sessions never hand a machine administrator key to the browser."""
import hashlib
import hmac
import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .service import Fault

COOKIE = "awp_console"


def password_hash(password):
    salt = secrets.token_bytes(16)
    return f"pbkdf2:600000:{salt.hex()}:" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()


def verify(password, stored):
    try:
        method, iterations, salt, expected = stored.split(":")
        if method != "pbkdf2" or not 100000 <= int(iterations) <= 2000000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def read_cookie(settings, value):
    from cryptography.fernet import Fernet, InvalidToken
    try:
        claims = json.loads(Fernet(settings.workforce_secret_key.encode()).decrypt(value.encode(), ttl=28800))
        user = settings.console_users[claims["sub"]]
        if claims["version"] != hashlib.sha256(user["password_hash"].encode()).hexdigest() or user.get("disabled"):
            return None
        return {**claims, "tenant": user["tenant"], "role": user.get("role", "viewer")}
    except (ValueError, KeyError, TypeError, InvalidToken):
        return None


def build_console(service):
    router = APIRouter(prefix="/console")

    class Login(BaseModel):
        username: str = Field(min_length=1, max_length=200)
        password: str = Field(min_length=1, max_length=500)

    @router.get("", response_class=HTMLResponse)
    async def page():
        return Path(__file__).with_name("console.html").read_text(encoding="utf-8")

    @router.post("/login")
    async def login(body: Login, request: Request):
        # Cookie authentication cannot be established by another website.
        origin = request.headers.get("origin")
        from urllib.parse import urlsplit
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            raise Fault(403, "UNTRUSTED_ORIGIN")
        await service.rate_limit("console-login:" + hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest(), 20)
        users = service.rt.settings.console_users
        user = users.get(body.username)
        # Perform the same hash work for unknown users.
        dummy = "pbkdf2:600000:" + "00" * 16 + ":" + "00" * 32
        ok = verify(body.password, user.get("password_hash", dummy) if user else dummy)
        if not ok or not user or user.get("disabled"):
            raise Fault(401, "INVALID_CREDENTIAL")
        claims = {"sub": body.username, "csrf": secrets.token_urlsafe(32),
                  "version": hashlib.sha256(user["password_hash"].encode()).hexdigest()}
        value = service.cipher().encrypt(json.dumps(claims).encode()).decode()
        response = JSONResponse({"username": body.username, "role": user.get("role", "viewer"), "csrf": claims["csrf"]})
        response.set_cookie(COOKIE, value, httponly=True, secure=service.rt.settings.console_secure_cookie,
                            samesite="strict", max_age=28800, path="/")
        return response

    @router.get("/session")
    async def session(request: Request):
        claims = read_cookie(service.rt.settings, request.cookies.get(COOKIE, ""))
        if not claims:
            raise Fault(401, "INVALID_CREDENTIAL")
        return {"username": claims["sub"], "role": claims["role"], "csrf": claims["csrf"]}

    @router.post("/logout")
    async def logout():
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    return router
