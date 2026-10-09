"""Settings read from the environment. Nothing here reads secrets from disk."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceKey:
    """A key a domain connector uses to call the platform."""

    tenant: str
    domain: str


@dataclass(frozen=True)
class Settings:
    db_url: str = "sqlite+aiosqlite:///./awp.db"
    agentscope_db_url: str = "sqlite+aiosqlite:///./agentscope.db"
    workspace_dir: str = "./awp_workspaces"
    # AWP_SERVICE_KEYS="key1:tenant:domain;key2:tenant:domain"
    service_keys: dict[str, ServiceKey] = field(default_factory=dict)
    # AWP_ADMIN_KEYS="key1:tenant;key2:tenant" — manage profiles, read cost, use the AgentScope API.
    admin_keys: dict[str, str] = field(default_factory=dict)
    # AWP_DEV_OPEN=1 lets requests without a key act as tenant "dev". Never in production.
    dev_open: bool = False
    models_file: str | None = None
    # Jev is an optional cheap gate; everything works with it off.
    jev_enabled: bool = False
    jev_model: str = "jev-latest"
    jev_min_support: float = 0.6
    # Cost ceiling per case in USD; 0 disables the ceiling.
    case_budget_usd: float = 0.0
    # Token ceiling per case as a fallback when prices are unknown; 0 disables.
    case_budget_tokens: int = 0
    # A case with no activity for this long is failed visibly instead of hanging (0 = never).
    case_stall_seconds: int = 900
    # Secret used to sign webhook callbacks (HMAC-SHA256) for domains that push.
    callback_secret: str = ""
    # Allow callback URLs that point at private addresses (tests, closed networks).
    callback_allow_private: bool = False
    # A request that expects a reply and gets none for this long ends the case as needs_human.
    request_timeout_hours: float = 72.0
    max_challenge_rounds: int = 2
    digest_max_chars: int = 1800
    workforce_wait_seconds: float = 25.0
    workforce_workers: int = 4
    workforce_lease_seconds: float = 60.0
    workforce_secret_key: str = ""
    workforce_monthly_budget_usd: float = 100.0
    redis_url: str = ""
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "awp-assets"
    minio_secure: bool = True
    minio_upload_origin: str = ""
    console_users: dict = field(default_factory=dict)
    console_secure_cookie: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        import json
        e = os.environ if env is None else env
        keys: dict[str, ServiceKey] = {}
        for part in filter(None, (e.get("AWP_SERVICE_KEYS") or "").split(";")):
            key, tenant, domain = (part.split(":") + ["", ""])[:3]
            if key and tenant:
                keys[key] = ServiceKey(tenant, domain or "default")
        admin: dict[str, str] = {}
        for part in filter(None, (e.get("AWP_ADMIN_KEYS") or "").split(";")):
            key, _, tenant = part.partition(":")
            if key and tenant:
                admin[key] = tenant
        return cls(
            db_url=e.get("AWP_DB_URL", cls.db_url),
            agentscope_db_url=e.get("AWP_AGENTSCOPE_DB_URL", cls.agentscope_db_url),
            workspace_dir=e.get("AWP_WORKSPACE_DIR", cls.workspace_dir),
            service_keys=keys,
            admin_keys=admin,
            dev_open=(e.get("AWP_DEV_OPEN", "").lower() in {"1", "true", "yes"}),
            models_file=e.get("AWP_MODELS_FILE") or None,
            jev_enabled=(e.get("AWP_JEV_ENABLED", "").lower() in {"1", "true", "yes"}),
            jev_model=e.get("AWP_JEV_MODEL", cls.jev_model),
            jev_min_support=float(e.get("AWP_JEV_MIN_SUPPORT", cls.jev_min_support)),
            case_budget_usd=float(e.get("AWP_CASE_BUDGET_USD", 0) or 0),
            case_budget_tokens=int(e.get("AWP_CASE_BUDGET_TOKENS", 0) or 0),
            case_stall_seconds=int(e.get("AWP_CASE_STALL_SECONDS", 900) or 0),
            callback_secret=e.get("AWP_CALLBACK_SECRET", ""),
            callback_allow_private=(e.get("AWP_CALLBACK_ALLOW_PRIVATE", "").lower() in {"1", "true", "yes"}),
            request_timeout_hours=float(e.get("AWP_REQUEST_TIMEOUT_HOURS", 72) or 72),
            max_challenge_rounds=int(e.get("AWP_MAX_CHALLENGE_ROUNDS", 2) or 2),
            digest_max_chars=int(e.get("AWP_DIGEST_MAX_CHARS", 1800) or 1800),
            workforce_wait_seconds=float(e.get("AWP_WORKFORCE_WAIT_SECONDS", 25)),
            workforce_workers=int(e.get("AWP_WORKFORCE_WORKERS", 4)),
            workforce_lease_seconds=float(e.get("AWP_WORKFORCE_LEASE_SECONDS", 60)),
            workforce_secret_key=e.get("AWP_SECRET_KEY", ""),
            workforce_monthly_budget_usd=float(e.get("AWP_WORKFORCE_MONTHLY_BUDGET_USD", 100)),
            redis_url=e.get("AWP_REDIS_URL", ""),
            minio_endpoint=e.get("AWP_MINIO_ENDPOINT", ""),
            minio_access_key=e.get("AWP_MINIO_ACCESS_KEY", ""),
            minio_secret_key=e.get("AWP_MINIO_SECRET_KEY", ""),
            minio_bucket=e.get("AWP_MINIO_BUCKET", "awp-assets"),
            minio_secure=e.get("AWP_MINIO_SECURE", "1") == "1",
            minio_upload_origin=e.get("AWP_MINIO_UPLOAD_ORIGIN", ""),
            console_users=json.loads(e.get("AWP_CONSOLE_USERS", "{}")),
            console_secure_cookie=e.get("AWP_CONSOLE_SECURE_COOKIE", "1") == "1",
        )
