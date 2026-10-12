"""The owner's named scenarios, written once and run on one process and on a fleet (tests/workforce/test_owner_scenarios.py).

A scenario talks to "the platform at process i" (`flow(i)`, `provider_at(i)`), reads through the public API (mpkit.Reads)
and asks the partner what it saw (`partner()`). On a fleet (mpkit.World) process i is a real process that the scenario
may kill. `Local` here is the same thing on one process inside the test: every i is that one process, and `restart()`
stops the app and starts another on the same databases.

The leader is the SAME script in both: deploy/demo/fake_model.py `script`, here played through tests/fake_llm.py. The
partner is tests' own MCP server (partnerkit.Partner), which keeps the same counts as the sample one of the fleet.
"""
from __future__ import annotations

import contextlib
import importlib.util
import sys
from pathlib import Path

from enginekit import world
from flowkit import Flow
from mpkit import DEMO, SCHEMA, Reads, booking_tool
from partnerkit import Partner
from t1kit import SETTINGS, configure
from t2kit import Provider


def _demo():
    spec = importlib.util.spec_from_file_location("awp_demo_model", Path(DEMO) / "fake_model.py")
    module = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in the deploy folder
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = keep
    return module


demo = _demo()


def leader(c):
    """The demo script as the leader of a fake_llm world."""
    return demo.script(demo.Call(c.msgs, c.tools))


class Local(Reads):
    """One platform process in the test, with the route, the tool and the provider a scenario needs."""

    def __init__(self, tmp_path, consent: bool = True, **settings) -> None:
        self.tmp, self.settings = tmp_path, {**SETTINGS, **settings}
        self.partner_server = Partner().start()
        self.stack: contextlib.ExitStack | None = None
        self.w = self._open(first=True)
        self.provider = Provider(self.w.env, self.w.flow.client["client_id"], SCHEMA)
        configure(self.w, self.partner_server, [booking_tool(self.provider.id, consent)])
        self._flow = self.w.flow

    def _open(self, first: bool):
        self.stack = contextlib.ExitStack()
        return self.stack.enter_context(world(self.tmp, leader, live=True, publish=first, leader_tools=["book_repair"],
                                              **self.settings))

    def restart(self) -> None:
        """The platform stops (cleanly) and another process starts on the same databases."""
        old = self._flow
        self.stack.close()
        self.w = self._open(first=False)
        self._flow = Flow(self.w.env, old.client, old.key, old.route, self.w.engine, old._n)
        self.provider.env = self.w.env

    def flow(self, i: int = 0) -> Flow:
        return self._flow

    def provider_at(self, i: int = 0) -> Provider:
        return self.provider

    def partner(self) -> dict:
        """The counts of the fleet's sample partner (deploy/demo/fake_mcp.py /stats), from the in-process one."""
        p = self.partner_server
        by_ref: dict[str, int] = {}
        for c in p.of("book_repair"):
            ref = c["args"]["client_reference"]
            by_ref[ref] = by_ref.get(ref, 0) + 1
        return {"side_effects": len(p.effects), "jobs": dict(p.jobs), "book_repair_calls_by_reference": by_ref,
                "side_effects_by_reference": {ref: 1 for ref in p.jobs}, "calls": {"book_repair": len(p.of("book_repair"))}}

    def close(self) -> None:
        try:
            if self.stack is not None:
                self.stack.close()
        finally:
            self.partner_server.stop()
