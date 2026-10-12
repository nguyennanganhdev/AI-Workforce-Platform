"""A running platform with the REAL engine on the scripted model (slice S3 tests).

`world(tmp_path, script)` builds the app on a fake OpenAI-compatible server, publishes the demo profiles
of tests/support.py for tenant `ta` (the leader may use the two look-up tools), and hands back a `World`:
the usual `Flow` of the request tests plus the fake server's call log and a few polling helpers. The
leader's model answers come from `script(call)` (tests/fake_llm.py `Call`), set per test.
"""
from __future__ import annotations

import contextlib
import re
import threading
import time
from dataclasses import dataclass

from conftest import ADM, _flow, build, build_live, publish
from fake_llm import CALLS, MODE, FakeServer
from support import LookupTicket, PriceList, demo_profiles

from awp.providers import ModelCatalog, ModelSpec

QUIET = {"wf_wait_seconds": 15.0, "wf_rate_per_minute": 0, "wf_ack_seconds": 3.0, "case_stall_seconds": 900}


@dataclass
class World:
    flow: object
    env: object

    @property
    def rt(self):
        return self.env.app.state.awp.rt

    @property
    def engine(self):
        return self.env.app.state.wf.engine

    def sql(self, query, args=()):
        return self.env.sql(query, args)

    def run(self, fn):
        """Run `fn()` (a coroutine function) on the app's own event loop and return its result."""
        return self.env.http.portal.call(fn)

    def state(self, workflow_id: str) -> tuple:
        return self.sql("select state, revision from wf_workflows where id=?", (workflow_id,))[0]

    def wait(self, check, timeout: float = 20.0, what: str = "condition"):
        """Poll `check()` until it returns something truthy."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            got = check()
            if got:
                return got
            time.sleep(0.05)
        raise AssertionError(f"timed out waiting for {what}")

    def wait_state(self, workflow_id: str, state: str, timeout: float = 20.0):
        return self.wait(lambda: self.state(workflow_id)[0] == state and self.state(workflow_id),
                         timeout, f"workflow {workflow_id} to be {state} (is {self.state(workflow_id)})")

    def quiet(self, timeout: float = 20.0) -> None:
        """No job queued or dispatched and no turn running."""
        self.wait(lambda: not self.sql(
            "select 1 from wf_jobs where status in ('queued','dispatched') union all "
            "select 1 from wf_turns where status='running'"), timeout, "the engine to go quiet")

    def messages(self, workflow_id: str) -> list[tuple]:
        return self.sql("select sender, text, request_id from wf_messages where workflow_id=? order by sequence",
                        (workflow_id,))

    def model_calls(self, who: str = "supervisor") -> list[dict]:
        return [c for c in CALLS if f'key="{who}"' in c["sys"] or (who == "supervisor" and "case-leader" in c["sys"])]


def profiles() -> list:
    out = demo_profiles()
    out[0].tools_allow = ["lookup_ticket", "price_list"]
    return out


def publish_profiles(env, leader_tools=(), worker_tools=()) -> None:
    """Publish the demo profiles; a test may grant more tools to the leader and to the technician. Every draft is made
    first: a leader is only published when its team are specialist profiles of the tenant (M4)."""
    made = profiles()
    for p in made:
        if p.key == "supervisor":
            p.tools_allow = [*p.tools_allow, *leader_tools]
        elif p.key == "tech":
            p.tools_allow = [*p.tools_allow, *worker_tools]
        r = env.post("/platform/v1/profiles", p.model_dump(mode="json"), ADM)
        assert r.status_code == 201, r.text
    for p in sorted(made, key=lambda p: p.role == "leader"):  # the specialists, then their leader
        publish(env, p.key)


@contextlib.contextmanager
def world(tmp_path, script=None, route=None, live=False, tools=(), leader_tools=(), worker_tools=(), publish=True, **over):
    """`tools`: factories (rt, binding) -> list of tools every agent gets; `leader_tools` / `worker_tools`: their
    names, granted to the leader's and the technician's profile. `publish=False`: the profiles are already in the
    databases (a second app on the files of the first)."""
    MODE.update(leader="normal", scenario="default", answer_gate=None, script=script, leader_delay=0, leader_gate=None, leader_http=0,
                worker=None, worker_http=0, agents={}, builder=None, eval_leader=None, delay=None)
    with FakeServer() as fake:
        catalog = ModelCatalog([
            ModelSpec(id="strong", provider="openai_compatible", model="fake-strong", tier="strong",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=2.0, price_out=8.0),
            ModelSpec(id="cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=0.5, price_out=2.0),
        ], env={"FAKE_KEY": "x"})

        def wire(app):
            app.state.awp.rt.tool_factories.append(lambda rt, b: [LookupTicket(), PriceList()])
            app.state.awp.rt.tool_factories.extend(tools)

        with (build_live if live else build)(tmp_path, wire=wire, catalog=catalog, **{**QUIET, **over}) as env:
            if publish:
                publish_profiles(env, leader_tools, worker_tools)
            try:
                yield World(_flow(env, **(route or {})), env)
            finally:
                if MODE["leader_gate"] is not None:
                    MODE["leader_gate"].set()
                MODE.update(script=None, leader_delay=0, leader_gate=None, leader_http=0, worker=None, worker_http=0, answer_gate=None,
                            agents={}, builder=None, eval_leader=None, delay=None)
                CALLS.clear()


def hold_leader() -> threading.Event:
    """Hold every model call of the leader until the returned event is set: a gate where a delay would make the test
    depend on how fast the machine is. `world` opens it when it ends, so a failing test cannot leave a turn waiting."""
    gate = MODE["leader_gate"] = threading.Event()
    return gate


def evidence_of(text: str) -> list[str]:
    return re.findall(r"\[evidence (E\d+)\]", text)
