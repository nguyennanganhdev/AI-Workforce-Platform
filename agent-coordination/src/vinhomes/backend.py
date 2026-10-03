"""HTTP client for the business API's Coordination endpoints.

A refusal (4xx) is a definite answer: nothing was applied. A timeout, a broken connection or
a 5xx is an unknown outcome and is never treated as "not applied".
"""
from __future__ import annotations

import httpx

from adapters.backend.errors import AdapterError

BASE = "/internal/coordination/v1"


class Refused(AdapterError):
    """The backend answered and said no."""

    def __init__(self, status: int):
        super().__init__(f"backend_rejected:{status}")
        self.status = status


class Backend:
    def __init__(self, base_url: str, token: str, client: httpx.AsyncClient, *, timeout: float = 15):
        if not base_url.startswith(("http://", "https://")) or len(token) < 32:
            raise ValueError("backend URL and a service token of 32+ characters are required")
        self.url, self.client, self.timeout = base_url.rstrip("/") + BASE, client, timeout
        self.headers = {"Authorization": "Bearer " + token}

    async def _call(self, method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        try:
            response = await self.client.request(method, self.url + path, json=body, params=params,
                                                 headers=self.headers, timeout=self.timeout)
        except httpx.HTTPError:
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True) from None
        if response.status_code >= 500:
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)
        if response.status_code >= 400:
            raise Refused(response.status_code)
        try:
            value = response.json()
        except ValueError:
            raise AdapterError("invalid_backend_response", outcome_unknown=True) from None
        if not isinstance(value, dict):
            raise AdapterError("invalid_backend_response", outcome_unknown=True)
        return value

    async def inbox(self, cursor: str | None, limit: int = 50) -> dict:
        return await self._call("GET", "/inbox", params={"limit": limit, **({"cursor": cursor} if cursor else {})})

    async def verify(self, team_id: str, message_id: str) -> dict:
        return await self._call("POST", "/reception/verify", {"team_id": team_id, "message_id": message_id})

    async def send(self, message: dict) -> dict:
        return await self._call("POST", "/reception/send", {"message": message})

    async def view(self, team_id: str) -> dict:
        return await self._call("GET", f"/teams/{team_id}/view")

    async def authorize(self, team_id: str, action_id: str, channel: str, operation: str) -> dict:
        return await self._call("POST", f"/teams/{team_id}/authorize",
                                {"action_id": action_id, "channel": channel, "operation": operation})

    async def result(self, team_id: str, message_id: str) -> dict:
        return await self._call("GET", f"/teams/{team_id}/results/{message_id}")

    async def status(self, team_id: str, phase: str, pause_reason: str | None, state_version: int) -> dict:
        return await self._call("POST", f"/teams/{team_id}/status",
                                {"phase": phase, "pause_reason": pause_reason, "state_version": state_version})

    async def admit(self, team_id: str, agent_version_id: str) -> dict:
        return await self._call("POST", f"/teams/{team_id}/members", {"agent_version_id": agent_version_id})

    async def turn_run(self, team_id: str, member_id: str, operation_id: str) -> dict:
        return await self._call("POST", f"/teams/{team_id}/members/{member_id}/runs", {"operation_id": operation_id})

    async def release(self, team_id: str, member_id: str) -> dict:
        return await self._call("GET", f"/teams/{team_id}/members/{member_id}/release")

    async def room(self, team_id: str, mirror: dict) -> dict:
        return await self._call("POST", f"/teams/{team_id}/room", mirror)
