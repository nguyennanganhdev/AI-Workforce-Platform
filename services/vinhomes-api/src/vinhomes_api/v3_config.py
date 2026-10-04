"""Configuration for the active V3 API. Legacy vh_* settings live in config.py."""

import hashlib
import os
import re
from dataclasses import dataclass
from uuid import UUID


def deployment_tenant_uuid(external_key: str) -> UUID:
    """Match server/src/db/deployment-scope.ts for the existing deployment."""
    digest = hashlib.sha256(f"openbot:tenant:{external_key}".encode()).hexdigest()
    return UUID(f"{digest[:8]}-{digest[8:12]}-5{digest[13:16]}-a{digest[17:20]}-{digest[20:32]}")


@dataclass(frozen=True)
class V3Settings:
    host: str
    port: int
    database_url: str | None
    tenant_id: UUID | None
    auth_url: str | None
    dev_user_id: str | None
    demo_mode: bool = False
    password_auth: bool = False
    local_file_storage: bool = False
    resident_allowed_origins: tuple[str, ...] = ()
    resident_signing_key: str | None = None
    resident_local_storage: bool = False
    # A container deployment keeps files on a volume its operator mounts and backs up.
    volume_file_storage: bool = False
    reception_service_token: str | None = None
    reception_url: str | None = None
    # Authenticates the Coordination runtime (the Supervisor) on /internal/coordination.
    coordination_service_token: str | None = None
    # Messages one resident may send to the assistant per minute; each one costs model calls.
    resident_messages_per_minute: int = 30

    @classmethod
    def from_env(cls) -> "V3Settings":
        host = os.getenv("VINHOMES_API_HOST", "127.0.0.1").strip()
        port = int(os.getenv("VINHOMES_API_PORT", "8000"))
        if not host or not 1 <= port <= 65535:
            raise ValueError("VINHOMES_API_HOST or VINHOMES_API_PORT is invalid")
        raw_tenant_id = os.getenv("VINHOMES_API_TENANT_ID", "").strip()
        tenant_key = os.getenv("VINHOMES_API_TENANT_KEY", "").strip()
        tenant_id = UUID(raw_tenant_id) if raw_tenant_id else (
            deployment_tenant_uuid(tenant_key) if tenant_key else None
        )
        dev_user_id = os.getenv("VINHOMES_API_DEV_USER_ID", "").strip() or None
        if dev_user_id and host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("VINHOMES_API_DEV_USER_ID requires a loopback host")
        auth_url = os.getenv("VINHOMES_API_AUTH_URL", "").strip() or None
        demo_mode = os.getenv("VINHOMES_API_DEMO_MODE", "0") == "1"
        password_auth = os.getenv("VINHOMES_API_PASSWORD_AUTH", "0") == "1"
        if password_auth and (demo_mode or dev_user_id or auth_url):
            raise ValueError("Password authentication cannot be combined with demo, fixed identity or external auth")
        if demo_mode and host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Demo mode requires a loopback host")
        if demo_mode:
            if not os.getenv("VINHOMES_API_DATABASE_URL", "").strip():
                raise ValueError("Database demo requires VINHOMES_API_DATABASE_URL; run setup_demo_database.ps1")
            if str(tenant_id) != "11111111-1111-5111-a111-111111111111":
                raise ValueError("Database demo requires the seeded local V3 tenant")
            if auth_url or dev_user_id:
                raise ValueError("Database demo uses seeded actors; unset AUTH_URL and DEV_USER_ID")
        if dev_user_id and auth_url:
            raise ValueError("Choose VINHOMES_API_AUTH_URL or VINHOMES_API_DEV_USER_ID")
        origins = tuple(o.strip().rstrip('/') for o in os.getenv('VINHOMES_API_RESIDENT_ALLOWED_ORIGINS', '').split(',') if o.strip())
        from urllib.parse import urlsplit
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError('Resident allowed origins must be explicit HTTP(S) origins')
        signing_key = os.getenv('VINHOMES_API_RESIDENT_SIGNING_KEY', '').strip() or None
        if signing_key and (len(signing_key) < 64 or any(c not in '0123456789abcdefABCDEF' for c in signing_key)):
            raise ValueError('Resident signing key requires at least 32 bytes encoded as even-length hex')
        if signing_key and len(signing_key) % 2:
            raise ValueError('Resident signing key must have an even length')
        local_storage = os.getenv('VINHOMES_API_RESIDENT_LOCAL_STORAGE', '0') == '1'
        if local_storage and host not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Resident local storage requires a loopback host')
        reception_token = os.getenv('VINHOMES_API_RECEPTION_SERVICE_TOKEN', '').strip() or None
        if reception_token and len(reception_token) < 32:
            raise ValueError('Reception service token requires at least 32 characters')
        reception_url = os.getenv('VINHOMES_API_RECEPTION_URL', '').strip().rstrip('/') or None
        if reception_url and (not reception_url.startswith(('http://', 'https://')) or not reception_token):
            raise ValueError('Reception URL must be HTTP(S) and requires the Reception service token')
        if reception_url and not re.fullmatch(r'(?:[0-9a-fA-F]{2}){32,}', os.getenv('RECEPTION_DELEGATION_KEY', '')):
            # Fail at startup instead of answering every resident with the fallback reply.
            raise ValueError('Reception URL requires RECEPTION_DELEGATION_KEY (at least 32 random bytes as hex)')
        coordination_token = os.getenv('VINHOMES_API_COORDINATION_SERVICE_TOKEN', '').strip() or None
        if coordination_token and len(coordination_token) < 32:
            raise ValueError('Coordination service token requires at least 32 characters')
        if coordination_token and coordination_token == reception_token:
            raise ValueError('Coordination and Reception need different service tokens')
        return cls(
            host=host,
            port=port,
            database_url=os.getenv("VINHOMES_API_DATABASE_URL", "").strip() or None,
            tenant_id=tenant_id,
            auth_url=auth_url,
            dev_user_id=dev_user_id,
            demo_mode=demo_mode,
            password_auth=password_auth,
            local_file_storage=os.getenv("VINHOMES_API_LOCAL_FILE_STORAGE", "0") == "1",
            resident_allowed_origins=origins,
            resident_signing_key=signing_key,
            resident_local_storage=local_storage,
            volume_file_storage=os.getenv("VINHOMES_API_VOLUME_FILE_STORAGE", "0") == "1",
            reception_service_token=reception_token,
            reception_url=reception_url,
            coordination_service_token=coordination_token,
            resident_messages_per_minute=int(os.getenv('VINHOMES_API_RESIDENT_MESSAGES_PER_MINUTE', '30')),
        )
