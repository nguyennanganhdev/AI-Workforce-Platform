"""PartnerMCP: a minimal partner-MCP client on the `mcp` SDK (prototype from P0, topic mcp_sdk).

What it gives the platform:
  * connect with static headers (Authorization) over streamable HTTP;
  * a cached tool list (one `tools/list` per refresh, never one per agent step);
  * `call(name, args, kind, timeout)` that never raises and returns a PartnerResult whose
    `outcome` is one of  ok | pending | failed | unknown  (spec section 8);
  * the rule that an error after the request may have left the client is `unknown`, never `failed`,
    and that nothing is retried unless it is a lookup that provably did not run.

Everything here was measured against a real FastMCP server (see test_p0_mcp_sdk.py).
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult, ClientRequest

OK, PENDING, FAILED, UNKNOWN = "ok", "pending", "failed", "unknown"

# status words a partner may answer with, mapped to our outcome (spec section 8)
DONE_WORDS = {"confirmed", "completed", "complete", "done", "success", "succeeded"}
PENDING_WORDS = {"pending", "accepted", "queued", "processing", "in_progress"}
FAILED_WORDS = {"failed", "rejected", "declined", "error", "cancelled", "canceled"}
JOB_KEYS = ("external_job_id", "operation_id", "job_id", "id")

REQUEST_TIMEOUT = 408   # mcp.types.REQUEST_TIMEOUT: raised by the SDK when read_timeout_seconds passes


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    read_only: bool            # annotations.readOnlyHint is True; a missing hint means NOT read only
    annotations: dict = field(default_factory=dict)
    output_schema: dict | None = None


@dataclass
class PartnerResult:
    outcome: str                      # ok | pending | failed | unknown
    text: str                         # what the agent may be shown (already merged with structuredContent)
    status: str | None = None         # the partner's own status word, lower case
    external_job_id: str | None = None
    error: str | None = None          # connect | timeout | session | tool_error | protocol | transport | cancelled
    sent: bool | None = None          # False = provably not delivered; True = delivered or may have been
    elapsed: float = 0.0
    attempts: int = 1
    structured: Any = None
    is_error: bool = False


def leaves(exc: BaseException) -> list[BaseException]:
    """Flatten ExceptionGroups (anyio task groups wrap the real error)."""
    if isinstance(exc, BaseExceptionGroup):
        out: list[BaseException] = []
        for e in exc.exceptions:
            out.extend(leaves(e))
        return out
    return [exc]


def merge_text(res: CallToolResult) -> str:
    """content + structuredContent into one text. FastMCP duplicates a plain return as
    structuredContent={"result": text}: do not show that twice."""
    texts = [b.text for b in res.content if getattr(b, "type", "") == "text"]
    text = "\n".join(texts)
    sc = res.structuredContent
    if sc is None:
        return text
    if isinstance(sc, dict) and set(sc) == {"result"} and str(sc["result"]) == text:
        return text
    if not text:
        return json.dumps(sc, ensure_ascii=False, sort_keys=True)
    try:
        if json.loads(text) == sc:
            return text
    except ValueError:
        pass
    return text + "\nstructuredContent: " + json.dumps(sc, ensure_ascii=False, sort_keys=True)


def partner_json(res: CallToolResult, text: str) -> dict | None:
    """The object that carries `status` / `operation_id`: structuredContent first, else JSON text."""
    if isinstance(res.structuredContent, dict) and "status" in res.structuredContent:
        return res.structuredContent
    for candidate in (text, *(b.text for b in res.content if getattr(b, "type", "") == "text")):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def normalize(res: CallToolResult, kind: str, tracking: str = "poll") -> PartnerResult:
    """The partner answered. Decide what it means. `tracking`='none' = we do not follow a pending job."""
    text = merge_text(res)
    if res.isError:
        return PartnerResult(FAILED, text or "the partner reported an error", error="tool_error", sent=True,
                             is_error=True, structured=res.structuredContent)
    obj = partner_json(res, text)
    status = str(obj.get("status", "")).strip().lower() if obj else ""
    job = next((str(obj[k]) for k in JOB_KEYS if obj and obj.get(k) not in (None, "")), None)
    base = dict(text=text, status=status or None, external_job_id=job, sent=True, structured=res.structuredContent)
    if status in DONE_WORDS:
        return PartnerResult(OK, **base)
    if status in PENDING_WORDS:
        return PartnerResult(PENDING if tracking != "none" else OK, **base)
    if status in FAILED_WORDS:
        return PartnerResult(FAILED, **base, error="tool_error")
    if kind == "lookup":
        return PartnerResult(OK, **base)       # a lookup has no status word: its text is the answer
    # an action whose answer we cannot read: the effect may have happened
    return PartnerResult(UNKNOWN, **base, error="protocol")


def classify_error(exc: BaseException, phase: str, own_cancel: bool) -> PartnerResult:
    """Map a transport/SDK exception to an outcome. `phase` is 'connect' (before tools/call left)
    or 'call' (tools/call was written)."""
    errs = leaves(exc)
    first = errs[0]
    msg = f"{type(first).__name__}: {first}"
    for e in errs:
        if isinstance(e, McpError):
            code = getattr(e.error, "code", None)
            if code == REQUEST_TIMEOUT:
                return PartnerResult(UNKNOWN, "no answer in time; the request may still be running at the partner",
                                     error="timeout", sent=True)
            if "Session terminated" in str(e):          # HTTP 404 for an unknown session: it did not run
                return PartnerResult(FAILED, "the partner session had expired; the request did not run",
                                     error="session", sent=False)
            return PartnerResult(FAILED, f"the partner refused the request: {e}", error="protocol",
                                 sent=phase == "call")
    if isinstance(first, asyncio.CancelledError):
        if own_cancel:
            raise first
        # a foreign cancel: the transport task group died under us; we cannot tell whether it was sent
        return PartnerResult(UNKNOWN if phase == "call" else FAILED, "the connection to the partner broke",
                             error="transport", sent=None if phase == "call" else False)
    for e in errs:
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code in (401, 403):      # the key was refused before anything ran (401/403 come from the gateway)
                return PartnerResult(FAILED, f"the partner refused our credentials (HTTP {code})", error="auth",
                                     sent=False)
            if phase == "call":         # 5xx on tools/call: the partner may have run it before failing
                return PartnerResult(UNKNOWN, f"the partner answered HTTP {code} to the request", error="http",
                                     sent=None)
    if phase == "connect":
        return PartnerResult(FAILED, f"could not reach the partner ({msg}); the request was not sent",
                             error="connect", sent=False)
    if isinstance(first, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
        return PartnerResult(UNKNOWN, "no answer in time; the request may still be running at the partner",
                             error="timeout", sent=True)
    return PartnerResult(UNKNOWN, f"the connection broke while waiting ({msg})", error="transport", sent=None)


class _Shared:
    """One long-lived session owned by one task (anyio scopes must be entered and left by one task)."""

    def __init__(self, client: "PartnerMCP") -> None:
        self.c = client
        self.task: asyncio.Task | None = None
        self.session: ClientSession | None = None
        self.stop = asyncio.Event()
        self.loop = asyncio.get_running_loop()

    @property
    def alive(self) -> bool:
        return self.session is not None and self.task is not None and not self.task.done()

    async def open(self) -> ClientSession:
        ready: asyncio.Future = self.loop.create_future()

        async def own() -> None:
            try:
                async with self.c._transport() as (r, w, _sid):
                    async with ClientSession(r, w) as s:
                        await asyncio.wait_for(s.initialize(), self.c.connect_timeout)
                        self.session = s
                        ready.set_result(s)
                        await self.stop.wait()
            except BaseException as e:           # noqa: BLE001 - reported through `ready`
                if not ready.done():
                    ready.set_exception(e)
            finally:
                self.session = None

        self.task = asyncio.create_task(own())
        return await ready

    async def close(self) -> None:
        self.stop.set()
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, 3)
            except BaseException:                # noqa: BLE001
                self.task.cancel()


class PartnerMCP:
    def __init__(self, url: str, headers: dict[str, str] | None = None, *, connect_timeout: float = 5.0,
                 call_timeout: float = 20.0, shared: bool = False, reuse_http: bool = True, close_grace: float = 0.5, list_ttl: float = 300.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.url, self.headers = url, dict(headers or {})
        self.connect_timeout, self.call_timeout, self.shared = connect_timeout, call_timeout, shared
        self.list_ttl, self._clock = list_ttl, clock
        self.reuse_http = reuse_http
        self.close_grace = close_grace
        self._http_client: httpx.AsyncClient | None = None
        self._http_loop: asyncio.AbstractEventLoop | None = None
        self._specs: list[ToolSpec] | None = None
        self._specs_at = 0.0
        self._shared: _Shared | None = None
        self.stats = {"list_calls": 0, "sessions_opened": 0, "retries": 0}

    # -- transport ---------------------------------------------------------------------------
    def _http(self) -> httpx.AsyncClient:
        """One httpx client per event loop, shared by every session: building a client (TLS context, certifi)
        costs most of the ~150 ms a fresh session takes on localhost, and the pool keeps TCP/TLS alive."""
        loop = asyncio.get_running_loop()
        if self._http_client is None or self._http_loop is not loop:
            timeout = httpx.Timeout(self.connect_timeout, read=max(self.call_timeout, 60.0) + 5)
            self._http_client = create_mcp_http_client(headers=self.headers, timeout=timeout)
            self._http_loop = loop
        return self._http_client

    @asynccontextmanager
    async def _transport(self):
        """streamable_http_client (the non-deprecated entry point) over our own httpx client: static headers,
        a connect timeout, a long read timeout (the per-call limit is read_timeout_seconds, not this)."""
        self.stats["sessions_opened"] += 1
        client = self._http() if self.reuse_http else create_mcp_http_client(
            headers=self.headers, timeout=httpx.Timeout(self.connect_timeout, read=max(self.call_timeout, 60.0) + 5))
        try:
            async with streamable_http_client(self.url, http_client=client) as streams:
                yield streams
        finally:
            if not self.reuse_http:
                await client.aclose()

    @asynccontextmanager
    async def _fresh(self):
        async with self._transport() as (r, w, _sid):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), self.connect_timeout)
                yield s

    async def _shared_session(self) -> ClientSession:
        loop = asyncio.get_running_loop()
        if self._shared is not None and (self._shared.loop is not loop or not self._shared.alive):
            if self._shared.loop is loop:
                await self._shared.close()
            self._shared = None
        if self._shared is None:
            self._shared = _Shared(self)
            try:
                return await self._shared.open()
            except BaseException:
                self._shared = None
                raise
        return self._shared.session  # type: ignore[return-value]

    async def aclose(self) -> None:
        if self._shared is not None and self._shared.loop is asyncio.get_running_loop():
            await self._shared.close()
        self._shared = None
        if self._http_client is not None and self._http_loop is asyncio.get_running_loop():
            await self._http_client.aclose()
        self._http_client = None

    # -- tool list ---------------------------------------------------------------------------
    async def list_tools(self, refresh: bool = False) -> list[ToolSpec]:
        """Cached. A failing refresh keeps serving the old list; with no list it raises."""
        fresh = self._specs is not None and (self._clock() - self._specs_at) < self.list_ttl
        if fresh and not refresh:
            return self._specs  # type: ignore[return-value]
        try:
            self.stats["list_calls"] += 1
            async with self._fresh() as s:
                listed = await asyncio.wait_for(s.list_tools(), self.connect_timeout)
        except BaseException as e:               # noqa: BLE001
            if isinstance(e, asyncio.CancelledError) and not _own_cancel():
                e = RuntimeError("transport cancelled")
            elif isinstance(e, asyncio.CancelledError):
                raise
            if self._specs is not None:
                return self._specs
            raise PartnerListError(f"cannot list the partner's tools: {leaves(e)[0]!r}") from e
        self._specs = [ToolSpec(
            name=t.name, description=t.description or "", input_schema=t.inputSchema,
            read_only=bool(t.annotations and t.annotations.readOnlyHint is True),
            annotations=t.annotations.model_dump(exclude_none=True) if t.annotations else {},
            output_schema=t.outputSchema) for t in listed.tools]
        self._specs_at = self._clock()
        return self._specs

    def invalidate(self) -> None:
        self._specs = None

    # -- calls -------------------------------------------------------------------------------
    async def call(self, name: str, args: dict | None = None, *, kind: str = "lookup",
                   timeout: float | None = None, tracking: str = "poll") -> PartnerResult:
        """Never raises (except for the caller's own cancellation). An action is sent at most once."""
        t0 = self._clock()
        timeout = timeout or self.call_timeout
        attempts = 0
        while True:
            attempts += 1
            res = await self._once(name, args or {}, kind, timeout, tracking)
            # the one retry we allow: a read-only lookup whose session died (stale session, broken transport).
            # Never for a timeout (the partner may be slow, not gone) and never for an action.
            if kind == "lookup" and attempts == 1 and res.error in ("session", "transport"):
                self.stats["retries"] += 1
                if self._shared is not None:
                    await self._shared.close()
                    self._shared = None
                continue
            res.elapsed, res.attempts = self._clock() - t0, attempts
            return res

    async def _once(self, name: str, args: dict, kind: str, timeout: float, tracking: str) -> PartnerResult:
        phase, got = "connect", None
        try:
            # hard backstop: connect + call + closing the session (which can take ~2 s on a dead server)
            # must fit in `timeout` + a short grace, or the 10 s offload threshold (spec A8) is at risk
            async with asyncio.timeout(timeout + self.close_grace):
                if self.shared and kind == "lookup":
                    s = await self._shared_session()
                    phase = "call"
                    got = await send_call(s, name, args, timeout)
                else:
                    async with self._fresh() as s:
                        phase = "call"
                        got = await send_call(s, name, args, timeout)
        except BaseException as e:               # noqa: BLE001
            if got is not None:                  # the answer is in; closing the session failed. Keep the answer.
                return normalize(got, kind, tracking)
            r = classify_error(e, phase, own_cancel=_own_cancel())
            if r.error in ("transport", "session") and self._shared is not None:
                self._shared = None              # a dead shared session never comes back: reconnect next time
            return r
        return normalize(got, kind, tracking)


async def send_call(session: ClientSession, name: str, args: dict, timeout: float) -> CallToolResult:
    """tools/call WITHOUT ClientSession.call_tool.

    call_tool (mcp 1.30) first sends a hidden `tools/list` the first time a tool name is used in a session
    (to find its outputSchema) and, after the server already ran the tool, validates structuredContent
    against that schema and RAISES RuntimeError when it does not fit. For an action that means "it ran, and
    we lost the answer". send_request is the same wire call with neither side effect."""
    request = ClientRequest(CallToolRequest(params=CallToolRequestParams(name=name, arguments=args)))
    return await session.send_request(request, CallToolResult, request_read_timeout_seconds=timedelta(seconds=timeout))


class PartnerListError(RuntimeError):
    pass


def _own_cancel() -> bool:
    """True when the current task was asked to cancel (not just woken by a dying transport scope)."""
    task = asyncio.current_task()
    return bool(task is not None and task.cancelling() > 0)

