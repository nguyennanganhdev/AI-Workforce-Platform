"""Process configuration for the Vinhomes HTTP service."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8001
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/vinhomes_api"
    approval_ttl_seconds: int | None = None
    field_operations_rule_set: str = "fail_closed"

    @classmethod
    def from_env(cls) -> "Settings":
        host = os.getenv("VINHOMES_API_HOST", "127.0.0.1").strip()
        if not host:
            raise ValueError("VINHOMES_API_HOST must not be empty")
        raw_port = os.getenv("VINHOMES_API_PORT", "8001")
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("VINHOMES_API_PORT must be an integer from 1 to 65535") from exc
        if not 1 <= port <= 65535:
            raise ValueError("VINHOMES_API_PORT must be an integer from 1 to 65535")
        database_url = os.getenv(
            "VINHOMES_API_DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/vinhomes_api",
        ).strip()
        if not database_url:
            raise ValueError("VINHOMES_API_DATABASE_URL must not be empty")
        field_operations_rule_set = os.getenv(
            "VINHOMES_API_RULE_SET", "fail_closed"
        ).strip().lower()
        if field_operations_rule_set not in {"fail_closed", "demo"}:
            raise ValueError("VINHOMES_API_RULE_SET must be 'fail_closed' or 'demo'")
        raw_approval_ttl = os.getenv("VINHOMES_API_APPROVAL_TTL_SECONDS")
        if raw_approval_ttl is None or not raw_approval_ttl.strip():
            approval_ttl_seconds = None
        else:
            try:
                approval_ttl_seconds = int(raw_approval_ttl)
            except ValueError as exc:
                raise ValueError(
                    "VINHOMES_API_APPROVAL_TTL_SECONDS must be a positive integer"
                ) from exc
            if approval_ttl_seconds <= 0:
                raise ValueError(
                    "VINHOMES_API_APPROVAL_TTL_SECONDS must be a positive integer"
                )
        return cls(
            host=host,
            port=port,
            database_url=database_url,
            approval_ttl_seconds=approval_ttl_seconds,
            field_operations_rule_set=field_operations_rule_set,
        )
