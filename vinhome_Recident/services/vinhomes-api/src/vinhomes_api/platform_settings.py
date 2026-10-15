"""Tenant-owned Platform connection; secrets never leave through a settings read."""

import asyncio
import base64
import io
import ipaddress
import json
import os
import re
import socket
import zipfile
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import text

from .platform import Bridge, Platform, PlatformError, TENANT
from .platform_access import TOOLS
from .v3_admin import Admin, admin
from .v3_audit import audit

router = APIRouter(prefix='/admin/platform-connection', tags=['Platform connection administration'])
SECRET_FIELDS = ('customer_key', 'provider_key', 'signing_secret')
FIELDS = (*SECRET_FIELDS, 'signing_key_id')


def cipher() -> Fernet:
    value = os.getenv('VINHOMES_API_CONFIG_ENCRYPTION_KEY', '').strip()
    try:
        if len(value) == 64:
            value = base64.urlsafe_b64encode(bytes.fromhex(value)).decode()
        return Fernet(value.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, 'Máy chủ chưa cấu hình khóa mã hóa kết nối Platform.') from None


def encrypt(values: dict) -> str:
    return cipher().encrypt(json.dumps(values).encode()).decode()


def decrypt(value: str) -> dict:
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError):
        raise HTTPException(503, 'Không đọc được cấu hình bảo mật. Kiểm tra khóa mã hóa trên máy chủ.') from None


def normalize_url(value: str) -> str:
    value = value.strip().rstrip('/')
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Địa chỉ Platform không hợp lệ.') from None
    allowed = {s.strip().lower() for s in os.getenv('VINHOMES_PLATFORM_ALLOWED_HOSTS', 'awp-platform,host.docker.internal').split(',') if s.strip()}
    host = (parsed.hostname or '').lower()
    if (parsed.scheme not in ('https', 'http') or not host or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path or any(c.isspace() for c in value)
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError('Nhập URL gốc của Platform, không kèm đường dẫn, tài khoản hoặc tham số.')
    if host not in allowed:
        if parsed.scheme != 'https':
            raise ValueError('Platform công khai phải dùng HTTPS.')
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError('Máy chủ này chưa cho phép địa chỉ nội bộ đó.')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise ValueError('Không được dùng địa chỉ loopback, metadata hoặc mạng riêng chưa được cho phép.')
    return value


async def validate_destination(url: str) -> None:
    """No redirect following; reject public names resolving into the private network."""
    normalize_url(url)
    parsed = urlsplit(url)
    allowed = {s.strip().lower() for s in os.getenv('VINHOMES_PLATFORM_ALLOWED_HOSTS', 'awp-platform,host.docker.internal').split(',') if s.strip()}
    if parsed.hostname.lower() in allowed:
        return
    try:
        records = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(
            parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM), timeout=5)
    except (OSError, TimeoutError):
        raise HTTPException(422, 'Không phân giải được địa chỉ Platform.') from None
    if not records or any(not ipaddress.ip_address(record[4][0]).is_global for record in records):
        raise HTTPException(422, 'Địa chỉ Platform trỏ tới mạng nội bộ chưa được cho phép.')


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    enabled: bool = False
    url: str = Field(default='', max_length=500)
    customer_key: SecretStr | None = None
    provider_key: SecretStr | None = None
    signing_key_id: str | None = Field(default=None, max_length=160)
    signing_secret: SecretStr | None = None

    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        return normalize_url(value)

    @field_validator('customer_key', 'provider_key', 'signing_secret')
    @classmethod
    def valid_secret(cls, value):
        if value is not None:
            raw = value.get_secret_value()
            if not 16 <= len(raw) <= 4096 or any(c.isspace() for c in raw):
                raise ValueError('Khóa cần từ 16 đến 4096 ký tự, không chứa khoảng trắng.')
        return value

    @field_validator('signing_key_id')
    @classmethod
    def valid_key_id(cls, value):
        if value is not None:
            value = value.strip()
            if value and not re.fullmatch(r'[A-Za-z0-9_.:-]+', value):
                raise ValueError('Signing key ID chỉ dùng chữ, số và các ký tự _ . : -')
        return value


async def row(db):
    return (await db.execute(text(f'SELECT * FROM platform_connection_settings WHERE tenant_id={TENANT}'))).mappings().first()


async def lock(db):
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(current_setting('app.tenant_id')||'-platform-settings',0))"))


def env_values() -> dict:
    return {k: os.getenv('VINHOMES_API_PLATFORM_' + k.upper(), '').strip() for k in FIELDS}


def bridge_from(url: str, values: dict) -> Bridge | None:
    if not url:
        return None
    if any(not values.get(k) for k in FIELDS):
        raise HTTPException(422, 'Cần đủ Customer key, Provider key, Signing key ID và Signing secret.')
    return Bridge(url, values['customer_key'], values['provider_key'], values['signing_key_id'],
                  values['signing_secret'], os.getenv('VINHOMES_API_PLATFORM_MCP_TOKEN', '').strip())


async def load_bridge(db) -> Bridge | None:
    saved = await row(db)
    if saved is None:
        return Bridge.from_env()
    return bridge_from(saved['url'], decrypt(saved['credentials_ciphertext'])) if saved['enabled'] else None


async def connection_enabled(db, management_ref: str | None = None) -> bool:
    saved = await row(db)
    if saved is None:
        from .platform import enabled
        return enabled()
    return bool(saved['enabled'] and (management_ref is None or saved['routes'].get(management_ref, {}).get('status') == 'active'))


async def candidate(db, body: ConnectionInput):
    saved = await row(db)
    if body.version != (saved['version'] if saved else 0):
        raise HTTPException(409, 'Cấu hình đã thay đổi. Tải lại trước khi lưu.')
    values = decrypt(saved['credentials_ciphertext']) if saved else env_values()
    for key in FIELDS:
        value = getattr(body, key)
        if value is not None:
            values[key] = value.get_secret_value() if isinstance(value, SecretStr) else value.strip()
    return saved, values


async def counts(db) -> dict:
    result = await db.execute(text("""SELECT
        (SELECT count(*) FROM platform_links WHERE status IN ('pending','open')) AS active_workflows,
        (SELECT count(*) FROM platform_commands WHERE status='pending') AS pending_commands,
        (SELECT count(*) FROM platform_commands WHERE status='failed') AS failed_commands,
        (SELECT count(*) FROM platform_outbox WHERE status='pending' OR receipt->>'ingestion_status' IN ('accepted','processing','quarantined')) AS pending_events,
        (SELECT count(*) FROM platform_outbox WHERE status='rejected') AS rejected_events
    """))
    return dict(result.mappings().one())


def public_mcp(request: Request) -> str:
    origins = os.getenv('VINHOMES_API_ALLOWED_ORIGINS', '').split(',')
    base = next((v.strip().rstrip('/') for v in origins if v.strip().startswith('https://')), str(request.base_url).rstrip('/'))
    return base + '/mcp'


async def view(db, request: Request) -> dict:
    saved = await row(db)
    values = decrypt(saved['credentials_ciphertext']) if saved else env_values()
    routes = saved['routes'] if saved else {}
    units = (await db.execute(text("SELECT code,name FROM management_units WHERE status='active' ORDER BY name"))).mappings().all()
    try:
        cipher()
        ready = True
    except HTTPException:
        ready = False
    return {'version': saved['version'] if saved else 0,
            'source': 'admin' if saved else 'environment',
            'enabled': saved['enabled'] if saved else bool(os.getenv('VINHOMES_API_PLATFORM_URL', '').strip()),
            'url': saved['url'] if saved else os.getenv('VINHOMES_API_PLATFORM_URL', '').strip(),
            'signing_key_id': values.get('signing_key_id', ''),
            'secrets_configured': {k: bool(values.get(k)) for k in SECRET_FIELDS},
            'encryption_ready': ready, 'updated_at': saved['updated_at'] if saved else None,
            'worker_seen_at': saved['worker_seen_at'] if saved else None,
            'worker_version': saved['worker_version'] if saved else None,
            'last_check': saved['last_check'] if saved else None, 'counts': await counts(db),
            'units': [{**dict(unit), 'route': routes.get(unit['code'])} for unit in units],
            'mcp': {'url': public_mcp(request), 'transport': 'streamable_http', 'tools': list(TOOLS),
                    'configured': bool(os.getenv('VINHOMES_API_PLATFORM_MCP_TOKEN', '').strip()),
                    'grant_path': '/api/business/platform/mcp-grants', 'ttl_seconds': 3600}}


async def probe(bridge: Bridge) -> dict:
    await validate_destination(bridge.url)
    client = Platform(bridge)
    checks = []
    marker = 'connection-check-' + uuid4().hex
    try:
        for key, call in [('customer_key', lambda: client.snapshot(marker, marker)),
                          ('provider_key', lambda: client.receipt(marker))]:
            try:
                await call()
                checks.append({'key': key, 'ok': False, 'code': 'UNEXPECTED_RESPONSE'})
            except PlatformError as exc:
                accepted = exc.status == 404 and exc.code in ('RESOURCE_NOT_FOUND', 'NOT_FOUND', 'CONVERSATION_NOT_FOUND')
                checks.append({'key': key, 'ok': accepted, 'code': 'ACCEPTED' if accepted else (
                    'AUTH_REFUSED' if exc.status in (401, 403) else 'CONTRACT_MISMATCH')})
            except httpx.HTTPError:
                checks.append({'key': key, 'ok': False, 'code': 'UNREACHABLE'})
    finally:
        await client.aclose()
    return {'ok': all(check['ok'] for check in checks), 'checks': checks,
            'checked_at': datetime.now(UTC).isoformat(), 'url': bridge.url,
            'signing': 'configured_not_verified'}


@router.get('')
async def get_connection(scope: Admin, request: Request, response: Response):
    admin(scope)
    response.headers['Cache-Control'] = 'no-store'
    return await view(scope[0], request)


@router.post('/check')
async def check_connection(body: ConnectionInput, scope: Admin, response: Response):
    admin(scope)
    db, actor, _ = scope
    _, values = await candidate(db, body)
    bridge = bridge_from(body.url, values)
    if bridge is None:
        raise HTTPException(422, 'Nhập địa chỉ Platform trước khi kiểm tra.')
    result = await probe(bridge)
    await audit(db, actor, 'platform_connection.checked', 'platform_connection', 'connection', {'ok': result['ok']})
    response.headers['Cache-Control'] = 'no-store'
    return result


@router.put('')
async def save_connection(body: ConnectionInput, scope: Admin, request: Request, response: Response):
    admin(scope)
    db, actor, _ = scope
    await lock(db)
    saved, values = await candidate(db, body)
    old_url = saved['url'] if saved else os.getenv('VINHOMES_API_PLATFORM_URL', '').strip().rstrip('/')
    old_enabled = saved['enabled'] if saved else bool(old_url)
    old_values = decrypt(saved['credentials_ciphertext']) if saved else env_values()
    keys_changed = any(values.get(k) != old_values.get(k) for k in FIELDS)
    pending = await counts(db)
    if pending['active_workflows'] and (body.url != old_url or keys_changed or (old_enabled and not body.enabled)):
        raise HTTPException(409, 'Còn workflow đang mở. Hoàn tất chúng trước khi tắt, đổi máy chủ hoặc khóa Platform.')
    routes = saved['routes'] if saved and body.url == old_url and values.get('customer_key') == old_values.get('customer_key') else {}
    checked = None
    if body.enabled:
        bridge = bridge_from(body.url, values)
        if bridge is None or not any(r.get('status') == 'active' for r in routes.values()):
            raise HTTPException(422, 'Lưu cấu hình và xác nhận ít nhất một tuyến đơn vị quản lý trước khi bật.')
        if len(bridge.mcp_token) < 32:
            raise HTTPException(422, 'Máy chủ chưa bật MCP hợp lệ để Platform xử lý ticket.')
        checked = await probe(bridge)
        if not checked['ok']:
            raise HTTPException(422, 'Kiểm tra xác thực chưa đạt. Kết nối chưa được bật.')
    await db.execute(text(f"""INSERT INTO platform_connection_settings
        (tenant_id,enabled,url,credentials_ciphertext,routes,last_check,updated_by)
        VALUES ({TENANT},:enabled,:url,:credentials,cast(:routes as jsonb),cast(:checked as jsonb),:actor)
        ON CONFLICT(tenant_id) DO UPDATE SET version=platform_connection_settings.version+1,
          enabled=excluded.enabled,url=excluded.url,credentials_ciphertext=excluded.credentials_ciphertext,
          routes=excluded.routes,last_check=excluded.last_check,updated_by=excluded.updated_by,updated_at=now()
    """), {'enabled': body.enabled, 'url': body.url, 'credentials': encrypt(values), 'routes': json.dumps(routes),
            'checked': json.dumps(checked), 'actor': actor})
    await audit(db, actor, 'platform_connection.updated', 'platform_connection', 'connection',
                {'enabled': body.enabled, 'changed_fields': [k for k in FIELDS if getattr(body, k) is not None],
                 'url_changed': body.url != old_url})
    response.headers['Cache-Control'] = 'no-store'
    return await view(db, request)


class RouteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    management_ref: str = Field(min_length=1, max_length=60)
    route_id: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9_-]+$')
    revision: int = Field(ge=1)


@router.post('/routes/confirm')
async def confirm_route(body: RouteInput, scope: Admin, request: Request):
    admin(scope)
    db, actor, _ = scope
    await lock(db)
    saved = await row(db)
    if saved is None or saved['version'] != body.version:
        raise HTTPException(409, 'Lưu hoặc tải lại cấu hình trước khi xác nhận tuyến.')
    if not (await db.execute(text("SELECT 1 FROM management_units WHERE code=:ref AND status='active'"), {'ref': body.management_ref})).first():
        raise HTTPException(422, 'Đơn vị quản lý không hoạt động trong tổ chức này.')
    previous = saved['routes'].get(body.management_ref)
    if previous and (previous['route_id'] != body.route_id or previous['revision'] != body.revision):
        active = (await db.execute(text("SELECT 1 FROM platform_links WHERE management_ref=:ref AND status IN ('pending','open') LIMIT 1"), {'ref': body.management_ref})).first()
        if active:
            raise HTTPException(409, 'Đơn vị còn workflow đang mở, chưa thể thay tuyến.')
    bridge = bridge_from(saved['url'], decrypt(saved['credentials_ciphertext']))
    if bridge is None:
        raise HTTPException(422, 'Chưa có địa chỉ Platform.')
    await validate_destination(bridge.url)
    client = Platform(bridge)
    try:
        result = await client.confirm_route(body.route_id, body.management_ref, body.revision)
    except (PlatformError, httpx.HTTPError):
        raise HTTPException(422, 'Platform chưa xác nhận tuyến. Kiểm tra mã tuyến, revision và Customer key.') from None
    finally:
        await client.aclose()
    if (result.get('status') != 'active' or result.get('revision') != body.revision + 1
            or result.get('route_id') != body.route_id or result.get('external_management_ref') != body.management_ref):
        raise HTTPException(422, 'Tuyến trả về chưa hoạt động hoặc không đúng revision.')
    routes = {**saved['routes'], body.management_ref: {'route_id': body.route_id, 'revision': result['revision'],
              'status': 'active', 'confirmed_at': datetime.now(UTC).isoformat()}}
    await db.execute(text(f"UPDATE platform_connection_settings SET routes=cast(:routes as jsonb),version=version+1,updated_by=:actor,updated_at=now() WHERE tenant_id={TENANT}"),
                     {'routes': json.dumps(routes), 'actor': actor})
    await audit(db, actor, 'platform_connection.route_confirmed', 'platform_connection', body.management_ref,
                {'route_id': body.route_id, 'revision': result['revision']})
    return await view(db, request)


@router.post('/mcp-export')
async def export_mcp(scope: Admin, request: Request):
    admin(scope)
    token = os.getenv('VINHOMES_API_PLATFORM_MCP_TOKEN', '').strip()
    if not token:
        raise HTTPException(422, 'Máy chủ chưa bật MCP.')
    url = public_mcp(request)
    config = {'name': 'vinhomes', 'transport': 'streamable_http', 'url': url,
              'headers': {'Authorization': 'Bearer ${VINHOMES_MCP_TOKEN}'}, 'timeout': 8,
              'mcp_grants': {'vinhomes': {'path': '/api/business/platform/mcp-grants', 'ttl_seconds': 3600}},
              'tools': list(TOOLS)}
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('mcp-server.json', json.dumps(config, ensure_ascii=False, indent=2))
        bundle.writestr('vinhomes-mcp.secret.env', 'VINHOMES_MCP_TOKEN=' + token + '\n')
        bundle.writestr('README.txt', 'Bộ kết nối riêng tư. Nạp token từ file env vào Authorization của MCP client; không phải client nào cũng tự thay biến ${...}.\n'
                         'Token khởi tạo chỉ discovery/control-plane. Backend cần đổi grant theo ticket/workflow trước khi gọi tool.\n'
                         'Platform cấp URL, Customer key, Provider key, Signing key ID/secret và route ID/revision để nhập lại vào trang quản trị Domain.\n'
                         'Không commit hoặc gửi bộ này vào chat công khai.\n')
    await audit(scope[0], scope[1], 'platform_connection.mcp_exported', 'platform_connection', 'vinhomes', {})
    return Response(data.getvalue(), media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="vinhomes-platform-connection.zip"', 'Cache-Control': 'no-store'})
