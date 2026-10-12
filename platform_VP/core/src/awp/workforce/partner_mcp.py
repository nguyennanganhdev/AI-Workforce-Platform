"""PartnerMCP: the platform's client for one partner MCP server (spec section 8, P0 items 15-20).

What it does, and why each rule is there (all measured in P0 against a real FastMCP server):

  * A new MCP session for every call, on one shared httpx client (connection pool): 13 ms on localhost, and no
    session that can die or go stale. The tool list is the only thing kept, with a time to live.
  * `tools/call` goes out with `send_request`, never `ClientSession.call_tool`: that one sends a hidden
    `tools/list` and, AFTER the partner already ran the tool, raises when structuredContent does not fit the
    declared schema. For an action that is "it happened and we lost the answer".
  * `timeout` is the budget of the whole call (connect, call, closing the session), enforced from outside
    with `asyncio.timeout(timeout + grace)`; closing a session on a dead server alone can take 2 s.
  * The answer is one of ok | pending | failed | unknown. Anything that may have reached the partner and has
    no clear answer is `unknown` and is never repeated. Only a read-only lookup is retried, once, and only
    when the session died.
  * The partner's error text is reduced before an agent reads it (no paths, addresses, tokens, our headers).
  * No redirect leaves the server's origin, no answer is larger than the cap, and the host is checked
    against private ranges at connection time too (ssrf.py).
"""
from __future__ import annotations

import asyncio
import contextvars
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult, ClientRequest

from . import ssrf
from .partner_result import PartnerResult, TooLarge, classify_error, normalize

MAX_PAGES = 10
RETRY_NOT_BEFORE = 1.0  # a lookup is only tried again when this many seconds of its budget are left
LIST_FAILURE_PAUSE = 10.0  # after a failed tools/list, do not ask again for this long


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    read_only: bool  # annotations.readOnlyHint is true; a missing hint means NOT read only
    annotations: dict = field(default_factory=dict)


class PartnerListError(RuntimeError):
    pass


class _Watch:
    """Set by the transport of the call in progress when an answer breaks the cap. The SDK swallows an error raised
    while it reads a response and just waits for a reply that will never come, so the call listens to this."""

    def __init__(self) -> None:
        self.event = asyncio.Event()


_WATCH: contextvars.ContextVar[_Watch | None] = contextvars.ContextVar("partner_mcp_watch", default=None)


def _too_large() -> TooLarge:
    watch = _WATCH.get()
    if watch is not None:
        watch.event.set()
    return TooLarge()


async def _unless_too_large(work: Any, watch: _Watch) -> Any:
    """`await work`, or raise TooLarge as soon as the transport saw an answer over the cap."""
    task, flag = asyncio.ensure_future(work), asyncio.ensure_future(watch.event.wait())
    try:
        done, _ = await asyncio.wait({task, flag}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return task.result()
        raise TooLarge()
    finally:
        for f in (task, flag):
            if not f.done():
                f.cancel()


# ---- the connection ---------------------------------------------------------------------------------------------------
class _Capped(httpx.AsyncByteStream):
    def __init__(self, inner: Any, cap: int) -> None:
        self.inner, self.cap, self.seen = inner, cap, 0

    async def __aiter__(self):
        async for chunk in self.inner:
            self.seen += len(chunk)
            if self.seen > self.cap:
                raise _too_large()
            yield chunk

    async def aclose(self) -> None:
        await self.inner.aclose()


class _Guarded(httpx.AsyncBaseTransport):
    """Every request: the host is checked and the connection goes to the address that was checked (the name is not
    looked up a second time, so DNS cannot answer differently); an answer larger than the cap is refused, and so is
    one the cap cannot measure because it is compressed."""

    def __init__(self, allow_private: bool, cap: int) -> None:
        self.allow_private, self.cap = allow_private, cap
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host, url = request.url.host.lower(), request.url
        address = await ssrf.pin(host, self.allow_private)
        if address is not None:  # same Host header, same TLS name, the address we checked
            request.url = url.copy_with(host=address)
            request.extensions = {**request.extensions, "sni_hostname": host}
        try:
            resp = await self.inner.handle_async_request(request)
        finally:
            request.url = url
        declared = resp.headers.get("content-length", "")
        if resp.headers.get("content-encoding", "identity").strip().lower() not in ("", "identity"):
            await resp.aclose()  # a few KiB of gzip can be a hundred MiB: the cap counts the bytes on the wire
            raise _too_large()
        if declared.isdigit() and int(declared) > self.cap:
            await resp.aclose()
            raise _too_large()
        return httpx.Response(resp.status_code, headers=resp.headers, stream=_Capped(resp.stream, self.cap),
                              extensions=resp.extensions, request=request)

    async def aclose(self) -> None:
        await self.inner.aclose()


async def send_call(session: ClientSession, name: str, args: dict, timeout: float) -> CallToolResult:
    """tools/call without ClientSession.call_tool (see the module docstring)."""
    request = ClientRequest(CallToolRequest(params=CallToolRequestParams(name=name, arguments=args)))
    return await session.send_request(request, CallToolResult, request_read_timeout_seconds=timedelta(seconds=timeout))


def _own_cancel() -> bool:
    """True when the current task was asked to cancel (not just woken by a dying transport scope)."""
    task = asyncio.current_task()
    return bool(task is not None and task.cancelling() > 0)


class PartnerMCP:
    def __init__(self, url: str, headers: dict[str, str] | None = None, *, allow_private: bool = False,
                 connect_timeout: float = 5.0, max_bytes: int = 256 * 1024, list_ttl: float = 300.0,
                 close_grace: float = 0.5, clock: Callable[[], float] = time.monotonic) -> None:
        self.url, self.headers = url, dict(headers or {})
        self.allow_private, self.connect_timeout, self.max_bytes = allow_private, connect_timeout, max_bytes
        self.list_ttl, self.close_grace, self._clock = list_ttl, close_grace, clock
        self.secrets = tuple(v for v in self.headers.values() if v)
        self._http: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock: asyncio.Lock | None = None
        self._specs: list[ToolSpec] | None = None
        self._specs_at = 0.0
        self._failed_at = -1e9
        self.stats = {"list_calls": 0, "sessions_opened": 0, "retries": 0}

    # -- transport ---------------------------------------------------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        """One httpx client per event loop, shared by every session: building one (TLS context) is most of the
        ~150 ms a fresh session costs, the pool keeps connections alive. Read timeout above the longest call."""
        loop = asyncio.get_running_loop()
        if self._http is None or self._loop is not loop:
            self._http = httpx.AsyncClient(
                headers={**self.headers, "Accept-Encoding": "identity"}, follow_redirects=False,
                timeout=httpx.Timeout(self.connect_timeout, read=20.0),
                transport=_Guarded(self.allow_private, self.max_bytes))
            self._loop, self._lock = loop, asyncio.Lock()
        return self._http

    @asynccontextmanager
    async def _session(self):
        self.stats["sessions_opened"] += 1
        async with streamable_http_client(self.url, http_client=self._client()) as (r, w, _sid):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), self.connect_timeout)
                yield s

    async def aclose(self) -> None:
        if self._http is not None and self._loop is asyncio.get_running_loop():
            await self._http.aclose()
        self._http = None

    # -- the tool list -----------------------------------------------------------------------------------------------
    async def list_tools(self, refresh: bool = False, strict: bool = False) -> list[ToolSpec]:
        """Cached for `list_ttl`; one refresh at a time. A failing refresh keeps serving the old list; with no
        list it raises PartnerListError (and does not ask again for a few seconds). `strict`: the caller wants the
        list as it is now or the failure (a discovery); the old list stays for everybody else."""
        self._client()
        async with self._lock:  # type: ignore[union-attr]
            if self._specs is not None and not refresh and self._clock() - self._specs_at < self.list_ttl:
                return self._specs
            if not refresh and self._clock() - self._failed_at < LIST_FAILURE_PAUSE:  # do not hammer a server that is down
                if self._specs is not None:
                    return self._specs
                raise PartnerListError("the partner's tool list could not be read a moment ago")
            try:
                self.stats["list_calls"] += 1
                tools = []
                async with asyncio.timeout(self.connect_timeout * 2):
                    async with self._session() as s:
                        cursor = None
                        for _ in range(MAX_PAGES):
                            page = await s.list_tools(cursor)
                            tools.extend(page.tools)
                            cursor = page.nextCursor
                            if not cursor:
                                break
            except BaseException as e:  # noqa: BLE001
                if isinstance(e, asyncio.CancelledError) and _own_cancel():
                    raise
                self._failed_at = self._clock()
                if self._specs is not None and not strict:
                    return self._specs
                raise PartnerListError("cannot list the partner's tools") from e
            self._specs = [ToolSpec(
                name=t.name, description=t.description or "", input_schema=t.inputSchema,
                read_only=bool(t.annotations and t.annotations.readOnlyHint is True),
                annotations=t.annotations.model_dump(exclude_none=True) if t.annotations else {}) for t in tools]
            self._specs_at = self._clock()
            return self._specs

    def invalidate(self) -> None:
        self._specs = None

    # -- calls -------------------------------------------------------------------------------------------------------
    async def call(self, name: str, args: dict | None = None, *, kind: str = "lookup", timeout: float = 8.0,
                   tracking: str = "events") -> PartnerResult:
        """Never raises (except for the caller's own cancellation). An action is sent at most once."""
        t0 = self._clock()
        attempts = 0
        while True:
            attempts += 1
            left = timeout - (self._clock() - t0)
            res = await self._once(name, args or {}, kind, max(left, 0.1), tracking)
            # The one retry: a read-only lookup whose session died. Never a timeout, never an action.
            if (kind == "lookup" and attempts == 1 and res.error in ("session", "transport")
                    and timeout - (self._clock() - t0) > RETRY_NOT_BEFORE):
                self.stats["retries"] += 1
                continue
            res.elapsed, res.attempts = self._clock() - t0, attempts
            return res

    async def _once(self, name: str, args: dict, kind: str, timeout: float, tracking: str) -> PartnerResult:
        phase, got, watch = "connect", None, _Watch()
        token = _WATCH.set(watch)
        try:
            # connect + call + closing the session must fit in `timeout` plus a short grace
            async with asyncio.timeout(timeout + self.close_grace):
                async with self._session() as s:
                    phase = "call"
                    got = await _unless_too_large(send_call(s, name, args, timeout), watch)
        except BaseException as e:  # noqa: BLE001
            if got is not None:  # the answer is in; only closing the session failed. Keep the answer.
                return normalize(got, kind, tracking, self.secrets)
            if isinstance(e, asyncio.CancelledError) and _own_cancel():
                raise
            return classify_error(e, phase, kind)
        finally:
            _WATCH.reset(token)
        return normalize(got, kind, tracking, self.secrets)
