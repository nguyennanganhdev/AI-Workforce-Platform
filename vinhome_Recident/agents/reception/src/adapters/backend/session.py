"""Resolve the authoritative Reception session before a new graph turn."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ...persistence.recovery import parse_recovered_session


@dataclass(frozen=True)
class SessionResolverConfig:
    base_url: str
    service_token: str
    path: str = "/internal/reception/session/resolve"
    timeout_seconds: float = 10.0

    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("BACKEND_BASE_URL_INVALID")
        if not self.service_token.strip() or self.timeout_seconds <= 0:
            raise ValueError("SESSION_RESOLVER_CONFIG_INVALID")


class BackendSessionResolver:
    def __init__(
        self,
        config: SessionResolverConfig,
        client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            follow_redirects=False,
        )

    async def aclose(self):
        if self._owned_client:
            await self.client.aclose()

    async def __call__(self, context: dict, signal=None) -> dict:
        if signal:
            signal.throw_if_aborted()
        response = await self.client.post(
            self.config.path,
            json={"context": context},
            headers={"Authorization": "Bearer " + self.config.service_token},
        )
        response.raise_for_status()
        if signal:
            signal.throw_if_aborted()
        payload = response.json()
        parse_recovered_session(payload)
        return payload
