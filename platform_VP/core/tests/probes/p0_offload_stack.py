"""Helper for the P0 offload probe: the real AgentScope service (create_app, in memory bus, SQLite) with
one partner-style tool and a scripted OpenAI-compatible model. It does not use anything from awp, so
the result is about AgentScope only. Nothing here is shared with other probes (prefix p0_offload_).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
import uuid
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from agentscope.app import create_app
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk
from pydantic import Field

USER = {"X-User-ID": "u-probe"}


# --------------------------------------------------------------------------- the tool
class _P(ParamsBase):
    seconds: float = Field(description="How long the partner takes")
    tag: str = Field(default="x", description="Label")


class Ledger:
    """What really happened to the tool, independent of what the model was told."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, float]] = []  # (what, tag, monotonic)
        self.t0 = time.monotonic()

    def add(self, what: str, tag: str) -> None:
        self.events.append((what, tag, time.monotonic() - self.t0))

    def at(self, what: str, tag: str) -> float | None:
        for w, t, ts in self.events:
            if w == what and t == tag:
                return ts
        return None


LEDGER = Ledger()


class PartnerBook(ToolBase):
    """Stands for our wrapper around a partner MCP tool with a side effect: a plain ToolBase, not MCPTool."""

    name = "partner_book"
    description = "Book a technician at the partner (has a side effect)."
    input_schema = _P.model_json_schema()
    is_read_only = False
    is_concurrency_safe = False

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="probe")

    async def call(self, seconds: float, tag: str = "x", **_ignored):
        LEDGER.add("start", tag)
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            LEDGER.add("cancelled", tag)
            raise
        LEDGER.add("side_effect_done", tag)
        return ToolChunk(content=[TextBlock(text=f"BOOKED ref=BK-{tag}")], state=ToolResultState.SUCCESS)


class PartnerBookStateInjected(PartnerBook):
    """Same tool, marked state-injected: the framework passes the live AgentState as _agent_state."""

    is_state_injected = True
    seen_state: list[Any] = []

    async def call(self, seconds: float, tag: str = "x", _agent_state=None, **_ignored):
        PartnerBookStateInjected.seen_state.append(type(_agent_state).__name__)
        return await super().call(seconds=seconds, tag=tag)


class PartnerBookCapped(PartnerBook):
    """Our own deadline inside the tool (decision A8): give up before AgentScope's 10 s and say unknown."""

    cap = 8.0

    async def call(self, seconds: float, tag: str = "x", **_ignored):
        try:
            return await asyncio.wait_for(super().call(seconds=seconds, tag=tag), timeout=self.cap)
        except asyncio.TimeoutError:
            LEDGER.add("capped", tag)
            return ToolChunk(
                content=[TextBlock(text=f"PENDING: the partner has not answered in {self.cap}s; "
                                        f"the booking may or may not exist (tag {tag}). Do not retry.")],
                state=ToolResultState.SUCCESS)


class PartnerBookNoOffload(PartnerBook):
    """Declares for itself that it must never be offloaded (read by OffloadPolicy below)."""

    name = "partner_book_nooffload"
    allow_offload = False


class PartnerBookPreWork(PartnerBook):
    """A cap that forgets the work done before it: 3 s of preparation, then an 8 s cap on the partner call."""

    cap = 8.0
    pre = 3.0

    async def call(self, seconds: float, tag: str = "x", **_ignored):
        await asyncio.sleep(self.pre)  # e.g. writing the operation row, checking idempotency
        try:
            return await asyncio.wait_for(super().call(seconds=seconds, tag=tag), timeout=self.cap)
        except asyncio.TimeoutError:
            LEDGER.add("capped", tag)
            return ToolChunk(content=[TextBlock(text=f"PENDING after cap (tag {tag})")],
                             state=ToolResultState.SUCCESS)


# --------------------------------------------------------------------------- supported extension points
from agentscope.agent import Agent  # noqa: E402
from agentscope.app.middleware import ToolOffloadMiddleware  # noqa: E402
from agentscope.middleware import MiddlewareBase  # noqa: E402


class OffloadPolicy(MiddlewareBase):  # pylint: disable=abstract-method
    """Wraps the framework's ToolOffloadMiddleware: tools that say `allow_offload = False` bypass it."""

    def __init__(self, inner: ToolOffloadMiddleware, timeout_secs: float | None = None) -> None:
        self.inner = inner
        if timeout_secs is not None:
            inner._timeout_secs = timeout_secs  # the only private attribute touched

    async def on_acting(self, agent, input_kwargs, next_handler):  # type: ignore[override]
        tool = await agent.toolkit.get_tool(input_kwargs["tool_call"].name)
        if tool is not None and getattr(tool, "allow_offload", True) is False:
            async for item in next_handler(**input_kwargs):
                yield item
            return
        async for item in self.inner.on_acting(agent, input_kwargs, next_handler):
            yield item


def agent_cls_with(timeout_secs: float | None):
    """An Agent subclass for create_app(custom_agent_cls=...) that swaps the installed offload middleware."""

    class PolicyAgent(Agent):
        def __init__(self, *args, middlewares=None, **kwargs):
            swapped = [OffloadPolicy(m, timeout_secs) if type(m) is ToolOffloadMiddleware else m
                       for m in (middlewares or [])]
            super().__init__(*args, middlewares=swapped, **kwargs)

    return PolicyAgent


class OrderRecorder(Agent):
    """Records the class names of the middlewares the service gave the agent, in order."""

    seen: list[list[str]] = []

    def __init__(self, *args, middlewares=None, **kwargs):
        OrderRecorder.seen.append([type(m).__name__ for m in (middlewares or [])])
        super().__init__(*args, middlewares=middlewares, **kwargs)


class ProbeExtra(MiddlewareBase):  # pylint: disable=abstract-method
    """Stands for any middleware given through extra_agent_middlewares."""

    calls: list[str] = []

    async def on_acting(self, agent, input_kwargs, next_handler):  # type: ignore[override]
        ProbeExtra.calls.append(input_kwargs["tool_call"].name)
        async for item in next_handler(**input_kwargs):
            yield item


# --------------------------------------------------------------------------- the scripted model
class Script:
    """Scripted model. Records every request. `steps[n]` is the output once n tool results are in the context
    (step 0 = the first reasoning step); anything missing means a plain text answer."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.t0 = time.monotonic()
        self.steps: dict[int, Any] = {0: [("partner_book", {"seconds": 1, "tag": "a"})]}
        self.after_hint = "Noted."         # text answer when woken by a hint (last message is not a tool result)
        self.lock = threading.Lock()

    def book(self, seconds: float, tag: str, name: str = "partner_book") -> None:
        self.steps = {0: [(name, {"seconds": seconds, "tag": tag})]}

    def decide(self, msgs: list[dict]) -> list[tuple[str, dict]] | str:
        n = sum(1 for m in msgs if m.get("role") == "tool")
        if n > 0 and msgs[-1].get("role") != "tool":
            return self.after_hint
        return self.steps.get(n, "Done.")


SCRIPT = Script()


def _text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def _chunk(cid: str, delta, finish=None, usage=None) -> str:
    body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "fake-1",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"


def make_model_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(req: Request):
        body = await req.json()
        msgs = body.get("messages", [])
        out = SCRIPT.decide(msgs)
        with SCRIPT.lock:
            SCRIPT.requests.append({
                "t": time.monotonic() - SCRIPT.t0,
                "roles": [m.get("role") for m in msgs],
                "tool_results": [_text(m) for m in msgs if m.get("role") == "tool"],
                "non_system_text": " ".join(_text(m) for m in msgs if m.get("role") != "system"),
                "last_role": msgs[-1].get("role") if msgs else None,
                "out": out,
            })
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]

        async def gen():
            if isinstance(out, str):
                yield _chunk(cid, {"role": "assistant", "content": ""})
                yield _chunk(cid, {"content": out})
                yield _chunk(cid, {}, "stop")
                yield _chunk(cid, None, usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
            else:
                yield _chunk(cid, {"role": "assistant", "content": None})
                for i, (name, args) in enumerate(out):
                    yield _chunk(cid, {"tool_calls": [{"index": i, "id": f"call_{uuid.uuid4().hex[:8]}",
                                                       "type": "function", "function": {"name": name, "arguments": ""}}]})
                    yield _chunk(cid, {"tool_calls": [{"index": i, "function": {"arguments": json.dumps(args)}}]})
                yield _chunk(cid, {}, "tool_calls")
                yield _chunk(cid, None, usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


class ModelServer:
    def __enter__(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.server = uvicorn.Server(uvicorn.Config(make_model_app(), host="127.0.0.1", port=self.port,
                                                    log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=5)


# --------------------------------------------------------------------------- the stack
class Stack:
    def __init__(self, client: TestClient, app, agent_id: str, session_id: str) -> None:
        self.client, self.app, self.agent_id, self.session_id = client, app, agent_id, session_id
        self.t0 = time.monotonic()

    def now(self) -> float:
        return time.monotonic() - SCRIPT.t0

    def chat(self, text: str = "please book") -> None:
        SCRIPT.t0 = time.monotonic()
        LEDGER.t0 = SCRIPT.t0
        r = self.client.post("/chat/", headers=USER, json={
            "agent_id": self.agent_id, "session_id": self.session_id,
            "input": {"name": "resident", "role": "user", "content": [{"type": "text", "text": text}]}})
        assert r.status_code < 300, r.text

    def wake(self) -> None:
        r = self.client.post("/chat/", headers=USER, json={
            "agent_id": self.agent_id, "session_id": self.session_id, "input": None})
        assert r.status_code < 300, r.text

    def interrupt(self) -> None:
        r = self.client.post(f"/sessions/{self.session_id}/interrupt", headers=USER,
                             params={"agent_id": self.agent_id})
        assert r.status_code < 300, r.text

    def delete_session(self) -> None:
        r = self.client.delete(f"/sessions/{self.session_id}", headers=USER, params={"agent_id": self.agent_id})
        assert r.status_code < 300, r.text

    def messages(self) -> list[dict]:
        r = self.client.get(f"/sessions/{self.session_id}/messages", headers=USER,
                            params={"agent_id": self.agent_id, "limit": 200})
        return r.json()["messages"]

    def is_running(self) -> bool:
        r = self.client.get(f"/sessions/{self.session_id}/messages", headers=USER,
                            params={"agent_id": self.agent_id})
        return r.json()["is_running"]

    def bg_tasks(self) -> list:
        return list(self.app.state.background_task_manager.tasks.values())

    def wait(self, pred: Callable[[], bool], timeout: float, what: str = "condition") -> float:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return self.now()
            time.sleep(0.05)
        raise AssertionError(f"timed out waiting for {what} after {timeout}s; "
                             f"requests={[(round(r['t'], 1), r['last_role']) for r in SCRIPT.requests]} "
                             f"ledger={LEDGER.events}")


@contextlib.contextmanager
def make_stack(tmp_path, *, tool_classes=(PartnerBook,), custom_agent_cls=None, extra_agent_middlewares=None):
    SCRIPT.__init__()
    LEDGER.__init__()
    PartnerBookStateInjected.seen_state = []
    OrderRecorder.seen = []
    ProbeExtra.calls = []

    async def tools(user_id, agent_id, session_id):
        return [c() for c in tool_classes]

    with ModelServer() as fake:
        storage = AsyncSQLAlchemyStorage(
            f"sqlite+aiosqlite:///{(tmp_path / 'as.db').as_posix()}",
            engine_kwargs={"connect_args": {"timeout": 30}})
        kwargs: dict[str, Any] = dict(enable_scheduler=False, extra_agent_tools=tools,
                                      custom_subagent_templates=[])
        if custom_agent_cls is not None:
            kwargs["custom_agent_cls"] = custom_agent_cls
        if extra_agent_middlewares is not None:
            kwargs["extra_agent_middlewares"] = extra_agent_middlewares
        app = create_app(storage, InMemoryMessageBus(), LocalWorkspaceManager(basedir=str(tmp_path / "ws")),
                         **kwargs)
        with TestClient(app) as client:
            c = client.post("/credential/", headers=USER, json={"data": {
                "type": "openai_credential", "api_key": "x", "name": "fake", "base_url": fake.base_url}})
            assert c.status_code < 300, c.text
            cid = c.json()["credential_id"]
            a = client.post("/agent/", headers=USER, json={
                "name": "probe", "system_prompt": "You book technicians with partner_book.",
                "react_config": {"max_iters": 6}})
            assert a.status_code < 300, a.text
            aid = a.json()["agent_id"]
            s = client.post("/sessions/", headers=USER, json={
                "agent_id": aid, "name": "p0", "chat_model_config": {
                    "type": "openai_chat", "credential_id": cid, "model": "fake-1", "parameters": {}}})
            assert s.status_code < 300, s.text
            yield Stack(client, app, aid, s.json()["session_id"])
