"""Configuration for the active V3 API. Legacy vh_* settings live in config.py."""

import hashlib
import os
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
        return cls(
            host=host,
            port=port,
            database_url=os.getenv("VINHOMES_API_DATABASE_URL", "").strip() or None,
            tenant_id=tenant_id,
            auth_url=auth_url,
            dev_user_id=dev_user_id,
            demo_mode=demo_mode,
        )
