"""Approval gate for Workforce v1 (spec 6.1), as a minimal reusable piece, plus a probe harness.

Reusable (the parts a real implementation copies):
  ApprovalGate           middleware: on_check_permission asks for tools that need consent and
                         never asks twice; on_reply notes whether the turn parked.
  canonical / args_hash  canonical JSON of tool input and its sha256.
  confirm_event_from_record(rec, confirmed)
                         builds UserConfirmResultEvent from the STORED tool call only
                         (nothing from the client, never `rules`).

Probe-only: ApprovalStore is in memory (the real one is wf_approvals), Charge/Refund tools,
build_probe_app and the Probe driver around the REST API.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from agentscope.app import create_app
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.event import ConfirmResult, ReplyEndEvent, RequireUserConfirmEvent, UserConfirmResultEvent
from agentscope.message import TextBlock, ToolCallBlock, ToolCallState, ToolResultState
from agentscope.middleware import MiddlewareBase
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk
from pydantic import Field


# ----------------------------------------------------------------- reusable: hashing and event

def canonical(raw: str | dict) -> str:
    """Canonical JSON (sorted keys, no spaces) of tool input given as a JSON string or dict."""
    value = json.loads(raw) if isinstance(raw, str) else raw
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def args_hash(raw: str | dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(raw).encode()).hexdigest()


def confirm_event_from_record(rec: "Approval", confirmed: bool) -> UserConfirmResultEvent:
    """The resume event, built only from what we stored when we parked.

    AgentScope overwrites tool_call.name/input with the event's values, so these must come from
    our row, never from the caller. `rules` is deliberately left out: a business approval must not
    become a standing allow-rule in the session's permission context.
    """
    block = ToolCallBlock.model_validate(rec.tool_call)
    block = block.model_copy(update={"input": rec.arguments})
    return UserConfirmResultEvent(
        reply_id=rec.reply_id,
        confirm_results=[ConfirmResult(confirmed=confirmed, tool_call=block)])


# ----------------------------------------------------------------- store (probe: in memory)

@dataclass
class Approval:
    id: str
    session_id: str
    agent_id: str
    agent_name: str
    reply_id: str
    tool_call: dict          # ToolCallBlock.model_dump(mode="json") at the time of ASK
    tool_call_id: str
    tool_name: str
    arguments: str           # canonical JSON
    arguments_hash: str
    status: str = "pending"  # pending | approved | rejected


class ApprovalStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.rows: dict[tuple[str, str], Approval] = {}
        self.checks: list[dict] = []     # every on_check_permission seen by a gate
        self.turns: list[dict] = []      # every on_reply seen by a gate
        self.executed: list[dict] = []   # tool bodies that actually ran

    def get_or_create(self, session_id: str, call: ToolCallBlock, agent: Any, agent_id: str) -> tuple[Approval, bool]:
        """Unique on (session_id, tool_call.id): asking again returns the same row."""
        key = (session_id, call.id)
        with self._lock:
            if key in self.rows:
                return self.rows[key], False
            args = canonical(call.input)
            row = Approval(id="appr_" + uuid.uuid4().hex[:12], session_id=session_id, agent_id=agent_id,
                           agent_name=agent.name, reply_id=agent.state.reply_id,
                           tool_call=call.model_dump(mode="json"), tool_call_id=call.id,
                           tool_name=call.name, arguments=args, arguments_hash=args_hash(args))
            self.rows[key] = row
            return row, True

    def find(self, session_id: str, tool_call_id: str) -> Approval | None:
        return self.rows.get((session_id, tool_call_id))

    def pending(self) -> list[Approval]:
        return [r for r in self.rows.values() if r.status == "pending"]

    def decide(self, rec: Approval, approve: bool) -> None:
        rec.status = "approved" if approve else "rejected"


# ----------------------------------------------------------------- reusable: the gate

class ApprovalGate(MiddlewareBase):
    """Ask for consent on the named tools, even in dont_ask; never ask twice for the same call."""

    def __init__(self, store: ApprovalStore, agent_id: str, session_id: str,
                 consent: set[str] = frozenset({"Charge"})) -> None:
        self.store, self.agent_id, self.session_id, self.consent = store, agent_id, session_id, set(consent)

    async def on_check_permission(self, agent, input_kwargs, next_handler):
        call: ToolCallBlock = input_kwargs["tool_call"]
        if call.name not in self.consent:
            return await next_handler(**input_kwargs)
        seen = {"session": self.session_id, "call": call.id, "name": call.name, "state": str(call.state)}
        self.store.checks.append(seen)
        rec = self.store.find(self.session_id, call.id)

        if call.state == ToolCallState.ALLOWED:
            # Resumed after a decision. Run only what we approved: the row says approved AND the
            # arguments are the ones we showed. (AgentScope copies the event's input into the call.)
            if rec and rec.status == "approved" and args_hash(call.input) == rec.arguments_hash:
                seen["decision"] = "pass"
                return await next_handler(**input_kwargs)
            seen["decision"] = "deny"
            return PermissionDecision(behavior=PermissionBehavior.DENY,
                                      message="no matching approval for this call")

        row, _created = self.store.get_or_create(self.session_id, call, agent, self.agent_id)
        if row.status == "rejected":
            seen["decision"] = "deny"
            return PermissionDecision(behavior=PermissionBehavior.DENY, message="the resident declined")
        seen["decision"] = "ask"
        seen["approval"] = row.id
        return PermissionDecision(behavior=PermissionBehavior.ASK, message=f"approval {row.id} pending")

    async def on_reply(self, agent, input_kwargs, next_handler) -> AsyncGenerator:
        inputs = input_kwargs.get("inputs")
        turn = {"session": self.session_id, "input": type(inputs).__name__, "events": [], "end": None,
                "parked": False, "last_item": None, "error": None, "done": False}
        self.store.turns.append(turn)
        try:
            async for item in next_handler(**input_kwargs):
                turn["events"].append(type(item).__name__)
                turn["last_item"] = type(item).__name__
                if isinstance(item, ReplyEndEvent):
                    turn["end"] = str(item.finished_reason)
                if isinstance(item, RequireUserConfirmEvent):
                    turn["parked"] = True
                yield item
        except BaseException as e:
            turn["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            turn["done"] = True


# ----------------------------------------------------------------- probe tools

class _MoneyP(ParamsBase):
    amount: int = Field(description="Amount")
    note: str = Field(default="", description="Note")


class Charge(ToolBase):
    """A tool with a side effect. Its own check_permissions says ALLOW; only the gate asks."""
    name = "Charge"
    description = "Charge the resident."
    input_schema = _MoneyP.model_json_schema()
    is_read_only = False
    is_concurrency_safe = False

    def __init__(self, store: ApprovalStore) -> None:
        self.store = store

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="tool says ok")

    async def call(self, amount: int, note: str = ""):
        self.store.executed.append({"tool": "Charge", "amount": amount, "note": note})
        return ToolChunk(content=[TextBlock(text=f"charged {amount}")], state=ToolResultState.SUCCESS)


class Refund(Charge):
    """Control: asks by itself (engine path), no gate. In dont_ask the engine turns that into DENY."""
    name = "Refund"
    description = "Refund the resident."

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ASK, message="tool wants a human")

    async def call(self, amount: int, note: str = ""):
        self.store.executed.append({"tool": "Refund", "amount": amount, "note": note})
        return ToolChunk(content=[TextBlock(text=f"refunded {amount}")], state=ToolResultState.SUCCESS)


# ----------------------------------------------------------------- probe harness

def build_probe_app(tmp_path, store: ApprovalStore, before: list | None = None):
    """`before`: extra middlewares placed ahead of the gate in the list (to test ordering)."""
    storage = AsyncSQLAlchemyStorage(f"sqlite+aiosqlite:///{(tmp_path / 'as.db').as_posix()}",
                                     engine_kwargs={"connect_args": {"timeout": 30}})
    bus = InMemoryMessageBus()
    workspaces = LocalWorkspaceManager(basedir=str(tmp_path / "ws"))

    async def mws(user_id: str, agent_id: str, session_id: str) -> list:
        return [*(before or []), ApprovalGate(store, agent_id, session_id)]

    async def tools(user_id: str, agent_id: str, session_id: str) -> list:
        return [Charge(store), Refund(store)]

    return create_app(storage, bus, workspaces, enable_scheduler=False, title="p0-ask-park",
                      extra_agent_middlewares=mws, extra_agent_tools=tools, custom_subagent_templates=[])


USER = "awp:probe"
H = {"X-User-ID": USER}


class Probe:
    """Drives the app through its REST surface, the way AgentScopeClient does."""

    def __init__(self, client, base_url: str, store: ApprovalStore, app) -> None:
        self.c, self.base_url, self.store, self.app = client, base_url, store, app
        self._cred: str | None = None

    def tail_events(self, sid: str) -> list[dict]:
        """Start listening to the session's live event channel (what the SSE stream relays).

        Returns a list that fills as events are published. Subscribe before the action under test:
        the channel keeps no history for late subscribers.
        """
        from agentscope.app.message_bus import MessageBusKeys
        got: list[dict] = []
        ready = threading.Event()

        async def run():
            async for payload in self.app.state.message_bus.subscribe(
                    MessageBusKeys.session_events(sid), on_ready=ready.set):
                got.append(payload)

        self.c.portal.start_task_soon(run)
        assert ready.wait(10), "subscription did not start"
        return got

    def _credential(self) -> str:
        if self._cred is None:
            from agentscope import credential as cr
            cred = cr.OpenAICredential(name="fake", api_key="x", base_url=self.base_url).model_dump(mode="json")
            cred.pop("id", None)
            r = self.c.post("/credential/", headers=H, json={"data": cred})
            assert r.status_code < 300, r.text
            self._cred = r.json()["credential_id"]
        return self._cred

    def new_session(self, system_prompt: str = "You are a probe agent.", name: str = "leader",
                    mode: str = "dont_ask") -> tuple[str, str]:
        r = self.c.post("/agent/", headers=H, json={"name": name, "system_prompt": system_prompt,
                                                    "react_config": {"max_iters": 8}})
        assert r.status_code < 300, r.text
        aid = r.json()["agent_id"]
        r = self.c.post("/sessions/", headers=H, json={
            "agent_id": aid, "name": name,
            "chat_model_config": {"type": "openai_chat", "credential_id": self._credential(),
                                  "model": "fake-model", "parameters": {}}})
        assert r.status_code < 300, r.text
        sid = r.json()["session_id"]
        r = self.c.patch(f"/sessions/{sid}", headers=H, params={"agent_id": aid}, json={"permission_mode": mode})
        assert r.status_code < 300, r.text
        return aid, sid

    def say(self, aid: str, sid: str, text: str):
        return self.c.post("/chat/", headers=H, json={
            "agent_id": aid, "session_id": sid,
            "input": {"name": "resident", "role": "user", "content": [{"type": "text", "text": text}]}})

    def chat_event(self, aid: str, sid: str, event):
        return self.c.post("/chat/", headers=H, json={
            "agent_id": aid, "session_id": sid, "input": event.model_dump(mode="json")})

    def status(self, aid: str, sid: str) -> str:
        r = self.c.get(f"/sessions/{sid}/status", headers=H, params={"agent_id": aid})
        assert r.status_code == 200, r.text
        return r.json()["status"]

    def wait_status(self, aid: str, sid: str, want: str, timeout: float = 30.0) -> str:
        end, st = time.time() + timeout, ""
        while time.time() < end:
            st = self.status(aid, sid)
            if st == want:
                return st
            time.sleep(0.1)
        raise AssertionError(f"session stayed {st!r}, wanted {want!r}")

    def settle(self, aid: str, sid: str, timeout: float = 30.0) -> str:
        """Wait until the session is not running; return its parked-or-idle status."""
        end = time.time() + timeout
        while time.time() < end:
            st = self.status(aid, sid)
            if st != "running":
                return st
            time.sleep(0.1)
        raise AssertionError("session kept running")

    def messages(self, aid: str, sid: str) -> list[dict]:
        r = self.c.get(f"/sessions/{sid}/messages", headers=H, params={"agent_id": aid, "limit": 200})
        assert r.status_code == 200, r.text
        return r.json()["messages"]

    def stored_session(self, aid: str, sid: str):
        async def go():
            return await self.app.state.storage.get_session(USER, aid, sid)
        return self.c.portal.call(go)

    def wait_for(self, cond, timeout: float = 30.0, what: str = "condition"):
        end = time.time() + timeout
        while time.time() < end:
            v = cond()
            if v:
                return v
            time.sleep(0.1)
        raise AssertionError(f"timed out waiting for {what}")
