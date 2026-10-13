"""Twenty workflows at once (spec section 10, P5), through the real HTTP API with event streams open on every
conversation: on one process with SQLite, and on two real processes with PostgreSQL and Redis (marker `multiproc`,
skipped without AWP_TEST_PG_URL and AWP_TEST_REDIS_URL). Scripted model, sample partner: this measures the platform's own
bookkeeping under concurrency, not a model.

The numbers of a run are printed (`pytest -s`) and, when AWP_LOAD_REPORT names a file, appended to it as JSON lines.
"""
from __future__ import annotations

import json
import os

import httpx
import pytest

from conftest import ADM
from loadkit import Lane, drive, letters, numbers, verify
from mpkit import Fleet, World, booking_tool, needs_fleet
from ownerkit import Local
from t1kit import configure

LANES = 20
REFS = ("BQL-OP1-A", "BQL-OP1-B")


def report(name: str, out: dict) -> None:
    line = json.dumps({"run": name, **out})
    print("\nLOAD " + line)
    path = os.environ.get("AWP_LOAD_REPORT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def stuck(w, lanes) -> None:
    """For a lane that did not finish: what the platform holds about it (printed; `verify` then fails with the lanes)."""
    for lane in lanes:
        wid = lane.ids.get("workflow")
        if lane.error is None or not wid:
            continue
        print(f"STUCK {lane.name}: {lane.error!r}")
        for what, query in (("workflow", "select state, attention_reason, revision from wf_workflows where id=?"),
                            ("jobs", "select kind, status, attempts from wf_jobs where workflow_id=? order by created_at"),
                            ("approvals", "select status, decided_at, resumed_at, used_at from wf_approvals where workflow_id=?"),
                            ("turns", "select trigger, msg_id, status from wf_turns where workflow_id=? order by started_at"),
                            ("operations", "select status, normalized_status from wf_operations where workflow_id=?")):
            print(f"  {what}: {w.sql(query, (wid,))}")


def all_closed(http, expect: int) -> None:
    """The operator's view: every workflow of the run is closed, none needs a person."""
    listed = http.get("/platform/v1/wf/workflows", headers=ADM, params={"limit": 200}).json()["workflows"]
    assert len(listed) == expect and {w["state"] for w in listed} == {"closed"}, [(w["workflow_id"], w["state"], w.get("attention_reason")) for w in listed]


@pytest.mark.slow
def test_twenty_workflows_at_once_on_one_process_do_not_mix_and_all_settle(tmp_path):
    # the settings of a deployment where they matter here: the contract's 25 s wait, 600 requests a minute and 20 streams per key
    x = Local(tmp_path, wf_wait_seconds=25.0, wf_rate_per_minute=600, wf_max_streams=20, sweep_every=2.0)
    try:
        w, f = x.w, x.flow()
        second = w.env.active_route(f.client["client_id"], f.key["api_key"], ref=REFS[1])  # the same partner, another office
        configure(w, x.partner_server, [booking_tool(x.provider.id)], route_id=second["route_id"])
        # a partner's client waits longer than the platform's 25 s (contract 6.2: "the client's timeout must be larger")
        http = httpx.Client(base_url=w.env.http.base_url, timeout=60)
        lanes = [Lane(letters(i), REFS[i % 2], http, http, f.key["api_key"], x.provider) for i in range(LANES)]
        total = drive(lanes)
        stuck(w, lanes)
        verify(lanes, x.partner())
        all_closed(w.env.http, LANES)
        w.quiet()  # nothing queued, nothing running
        assert w.sql("select count(*) from wf_operations where status <> 'completed'")[0][0] == 0
        out = numbers(lanes, total)
        report("sqlite, one process", out)
        assert total < 180, out  # about 45 s on a quiet machine; the suite runs it next to seven other workers
        http.close()
    finally:
        x.close()


@needs_fleet
@pytest.mark.multiproc
def test_twenty_workflows_at_once_on_two_processes_do_not_mix_and_all_settle(tmp_path):
    fleet = Fleet(tmp_path, AWP_WF_RATE_PER_MINUTE="600", AWP_WF_MAX_STREAMS="20", AWP_DB_POOL_SIZE="10", AWP_DB_MAX_OVERFLOW="10")
    try:
        first = fleet.start_api(wait=False)
        fleet.ready(first)
        fleet.start_api()
        x = World(fleet, wait_seconds=25.0)
        second = x.env.active_route(x.client["client_id"], x.key["api_key"], ref=REFS[1], wait_seconds=25.0)
        rid = second["route_id"]
        assert x.env.http.put(f"/platform/v1/wf/routes/{rid}/mcp", headers=ADM, json={"servers": [
            {"name": "p", "url": fleet.mcp.url + "/mcp", "headers": {}}]}).status_code == 200
        assert x.env.http.put(f"/platform/v1/wf/routes/{rid}/tools", headers=ADM,
                              json={"tools": [booking_tool(x.provider.id)]}).status_code == 200
        api = [httpx.Client(base_url=p.url, timeout=60) for p in fleet.api]
        # a lane's commands go to one process, its stream is read from the other, its provider's events go to either
        lanes = [Lane(letters(i), REFS[i % 2], api[i % 2], api[(i + 1) % 2], x.key["api_key"], x.provider_on((i // 2) % 2))
                 for i in range(LANES)]
        total = drive(lanes)
        verify(lanes, fleet.partner())
        all_closed(api[0], LANES)
        out = numbers(lanes, total)
        report("postgresql + redis, two processes", out)
        assert total < 180, out
    finally:
        fleet.close()
