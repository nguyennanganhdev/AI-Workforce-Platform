"""One platform instance in its own process: `python p0_crash_node.py cfg.json`.

Same wiring as tests/support.make_stack, but over HTTP and with a leader that owns a
side-effect tool. Two nodes started on the same files are "instance 1" and "instance 2".
"""
from __future__ import annotations

import json
import sys

import uvicorn

from awp.app import build_app
from awp.config import ServiceKey, Settings
from awp.guard import Rules
from awp.profiles import AgentProfile
from awp.providers import ModelCatalog, ModelSpec

from p0_crash_helpers import build_tool_class


class CrashPack:
    domain = "test"
    default_leader = "dispatcher"

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.tool_cls = build_tool_class()

    def profiles(self):
        return [AgentProfile(key="dispatcher", name="case-leader", role="leader",
                             mission="the leader of a repair case.", model_tier="strong",
                             tools_allow=["book_plumber"], instructions="Answer in English.")]

    def rules(self):
        return Rules(safe_reply="A person will follow up.")

    def tools(self, rt, binding):
        return [self.tool_cls(self.cfg, binding.case_id)]

    def request_kinds(self):
        return []

    async def deliver_result(self, case, result):
        pass

    async def start(self, rt, intake, tenant):
        pass

    async def stop(self):
        pass


def approval_gate_class(cfg: dict):
    from agentscope.message import ToolCallState
    from agentscope.middleware import MiddlewareBase
    from agentscope.permission import PermissionBehavior, PermissionDecision

    class ApprovalGate(MiddlewareBase):
        """Spec 6.1 in miniature: ASK from a middleware for a tool that needs consent."""

        async def on_check_permission(self, agent, input_kwargs, next_handler):
            call = input_kwargs["tool_call"]
            if call.name == "book_plumber" and call.state != ToolCallState.ALLOWED:
                if cfg.get("gate_hang"):
                    # our own approval row is written here, in the middleware, BEFORE the turn parks
                    import sqlite3
                    con = sqlite3.connect(cfg["awp_db"], timeout=30)
                    con.execute("CREATE TABLE IF NOT EXISTS p0_approvals (tool_call_id TEXT PRIMARY KEY, status TEXT)")
                    con.execute("INSERT OR IGNORE INTO p0_approvals VALUES (?, 'pending')", (call.id,))
                    con.commit()
                    con.close()
                    import asyncio
                    import pathlib
                    pathlib.Path(cfg["side_dir"], "reached_gate").write_text(call.id)
                    await asyncio.sleep(3600)
                return PermissionDecision(behavior=PermissionBehavior.ASK, message="resident must agree")
            return await next_handler(**input_kwargs)

    return ApprovalGate


def main() -> None:
    cfg = json.load(open(sys.argv[1]))
    settings = Settings(
        db_url=f"sqlite+aiosqlite:///{cfg['awp_db']}", agentscope_db_url=f"sqlite+aiosqlite:///{cfg['as_db']}",
        workspace_dir=cfg["workspace"], service_keys={"svc-key": ServiceKey("t1", "test")},
        admin_keys={"adm-key": "t1"}, case_stall_seconds=cfg.get("case_stall_seconds", 900))
    catalog = ModelCatalog([
        ModelSpec(id="strong", provider="openai_compatible", model="fake-strong", tier="strong",
                  base_url=cfg["llm_url"], api_key_env="FAKE_KEY", price_in=2.0, price_out=8.0),
        ModelSpec(id="cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                  base_url=cfg["llm_url"], api_key_env="FAKE_KEY", price_in=0.5, price_out=2.0),
    ], env={"FAKE_KEY": "x"})
    bus = None
    if cfg.get("redis"):
        from agentscope.app.message_bus import RedisMessageBus
        host, port = cfg["redis"]
        bus = RedisMessageBus(host=host, port=port)
    extra = {}
    holder: dict = {}
    if cfg.get("approval"):
        from awp.middleware import middleware_factory
        gate = approval_gate_class(cfg)

        async def factory(user_id, agent_id, session_id):
            base = await holder["f"](user_id, agent_id, session_id)
            return [gate(), *base] if base else base

        extra["extra_agent_middlewares"] = factory
    app = build_app(settings, packs=[CrashPack(cfg)], catalog=catalog, message_bus=bus, **extra)
    if cfg.get("approval"):
        holder["f"] = middleware_factory(app.state.awp.rt)
    uvicorn.run(app, host="127.0.0.1", port=cfg["port"], log_level="warning")


if __name__ == "__main__":
    main()
