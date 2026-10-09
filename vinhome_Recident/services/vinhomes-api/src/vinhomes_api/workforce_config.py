"""Backend-only Workforce configuration. Existing integration stays active until explicitly enabled."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


def enabled():
    return os.getenv("VINHOMES_WORKFORCE_ENABLED", "0") == "1"


@dataclass(frozen=True)
class WorkforceConfig:
    url: str
    customer_key: str
    provider_key: str
    signing_key_id: str
    signing_secret: str
    integration_client_id: str
    mcp_service_key: str
    mcp_context_key: str
    mcp_audience: str

    @classmethod
    def from_env(cls):
        result = cls(*(os.getenv("VINHOMES_WORKFORCE_" + key, "").strip() for key in (
            "URL", "CUSTOMER_KEY", "PROVIDER_KEY", "SIGNING_KEY_ID", "SIGNING_SECRET", "INTEGRATION_CLIENT_ID",
            "MCP_SERVICE_KEY", "MCP_CONTEXT_KEY", "MCP_AUDIENCE")))
        url = urlsplit(result.url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Workforce URL must be an HTTP(S) service origin")
        if not all(getattr(result, field) for field in result.__dataclass_fields__):
            raise ValueError("Workforce backend credentials and MCP configuration are required")
        if len(result.mcp_context_key) < 32 or len(result.mcp_service_key) < 32:
            raise ValueError("Workforce MCP keys require at least 32 characters")
        return result
