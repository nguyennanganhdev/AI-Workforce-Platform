"""Standard-library HTTP transport. Redirects are refused, including 307/308."""

from __future__ import annotations

import asyncio
from typing import Mapping
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .client import HttpResponse


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibTransport:
    def __init__(self, *, max_response_bytes: int = 1_048_576) -> None:
        if max_response_bytes <= 0:
            raise ValueError("invalid response limit")
        self._limit = max_response_bytes

    async def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse:
        return await asyncio.to_thread(self._post, url, dict(headers), body, timeout)

    def _post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> HttpResponse:
        opener = build_opener(_NoRedirect())
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            return HttpResponse(response.code, response.read(self._limit + 1))
