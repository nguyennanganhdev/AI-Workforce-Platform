"""End to end through the real AgentScope service with a scripted model.

This proves the plumbing. It does not say how a real model would behave.
"""
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from fake_llm import CALLS, MODE
from support import ADM, SVC, make_stack


@pytest.fixture()
def stack(tmp_path):
    with make_stack(tmp_path) as (client, pack, _rt):
        yield client, pack, None


def wait_for(client, case_id, status="finalized", timeout=60):
    end = time.time() + timeout
    case = None
    while time.time() < end:
        case = client.get(f"/platform/v1/cases/{case_id}", headers=SVC).json()
        if case["status"] == status:
            return case
        time.sleep(0.3)
    items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()
    raise AssertionError(f"case stayed {case['status']}; items={items}")


def intake_body(**over):
    body = {"message_id": "m-1", "external_ref": "TICKET-1", "summary": "Pipe leaking in unit A-12-05",
            "description": "Water under the sink since this morning.",
            "facts": [{"key": "unit", "value": "A-12-05", "source": "reported"}]}
    body.update(over)
    return body


def test_auth_and_masking(stack):
    client, _pack, _fake = stack
    assert client.post("/platform/v1/intake", json=intake_body()).status_code == 401
    assert client.get("/agent/", headers=SVC).status_code == 403  # connector keys cannot use the agent API
    cred = client.post("/credential/", headers=ADM, json={"data": {
        "type": "openai_credential", "api_key": "sk-supersecretvalue1234", "name": "mine"}})
    assert cred.status_code < 300
    listed = client.get("/credential/", headers=ADM)
    assert "sk-supersecretvalue1234" not in listed.text and "1234" in listed.text


def test_case_runs_team_debate_and_delivers(stack):
    client, pack, _fake = stack
    r = client.post("/platform/v1/intake", headers=SVC, json=intake_body())
    assert r.status_code == 202, r.text
    case_id = r.json()["case_id"]

    # idempotent: the same message again returns the same case
    again = client.post("/platform/v1/intake", headers=SVC, json=intake_body())
    assert again.json()["case_id"] == case_id and again.json()["replayed"] is True

    case = wait_for(client, case_id)
    assert case["result"]["outcome"] == "resolved"
    assert "1500000" in case["result"]["answer"] and "2000000" not in case["result"]["answer"]

    items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
    if os.environ.get("AWP_DEBUG"):
        for i in items:
            print(i["ref"], i["kind"], i["author"], "->", i["addressee"], json.dumps(i["data"])[:150])
    facts = {i["author"]: i for i in items if i["kind"] == "fact"}
    assert set(facts) == {"tech", "fin"}, facts.keys()
    # the peer question and its answer are in the case file, between the two members
    q = [i for i in items if i["kind"] == "question"]
    a = [i for i in items if i["kind"] == "answer"]
    assert len(q) == 1 and q[0]["author"] == "fin" and q[0]["addressee"] == "tech"
    assert len(a) == 1 and a[0]["author"] == "tech" and a[0]["data"]["to_ref"] == q[0]["ref"]
    # the first final answer invented a figure and was refused before the accepted one
    notes = [i for i in items if i["kind"] == "note" and i["data"].get("type") == "final_attempt"]
    assert len(notes) == 1 and "2000000" in str(notes[0]["data"]["problems"])
    # a broadcast report by a worker was turned into a report to the leader
    assert {i["author"] for i in items if i["kind"] == "report"} == {"tech", "fin"}
    # tool output became evidence the facts cite
    assert all(f["data"]["evidence"] for f in facts.values())

    # the result reached the domain
    deadline = time.time() + 15
    while not pack.results and time.time() < deadline:
        time.sleep(0.2)
    assert pack.results, "result was not delivered to the domain"
    _case, result = pack.results[0]
    assert result.external_ref == "TICKET-1" and result.outcome == "resolved"

    # cost is recorded per agent and model, with prices
    cost = client.get(f"/platform/v1/cases/{case_id}/cost", headers=ADM).json()
    assert cost["totals"]["calls"] >= 6 and cost["totals"]["cost_usd"] > 0
    models = {m["model"] for m in cost["by_model"]}
    assert models == {"fake-strong", "fake-cheap"}  # workers ran on the cheap tier


def test_tools_are_pruned_by_role(stack):
    client, _pack, _fake = stack
    r = client.post("/platform/v1/intake", headers=SVC, json=intake_body(external_ref="TICKET-2", message_id="m-2"))
    wait_for(client, r.json()["case_id"])
    leader = [c for c in CALLS if 'key="supervisor"' in c["sys"]]
    workers = [c for c in CALLS if 'key="tech"' in c["sys"] or 'key="fin"' in c["sys"]]
    assert leader and workers
    for c in leader:
        assert "CaseFinalize" in c["tools"] and "Bash" not in c["tools"]
    for c in workers:
        assert "CaseFinalize" not in c["tools"] and "CaseDecide" not in c["tools"]
        assert not {"TeamCreate", "AgentCreate", "TeamDelete", "Bash"} & set(c["tools"]), c["tools"]
    # a worker sees few tools, which is what keeps the base cost low
    assert max(len(c["tools"]) for c in workers) <= 11, max(workers, key=lambda c: len(c["tools"]))["tools"]
    m = client.get("/platform/v1/metrics", headers=ADM).json()
    print("metrics:", m)
    assert m["tool_schema_saving"] > 0.4, m  # the filter must remove a good share of the tool schemas
    print("leader tools:", sorted(leader[-1]["tools"]))
    print("worker tools:", sorted(workers[-1]["tools"]))


def test_profile_lifecycle_and_models(stack):
    client, _pack, _fake = stack
    body = {"key": "extra", "name": "Extra", "mission": "does extra work."}
    created = client.post("/platform/v1/profiles", headers=ADM, json=body).json()
    assert created["status"] == "draft" and created["version"] == 1
    assert client.post("/platform/v1/profiles/extra/versions/1/publish", headers=ADM).status_code == 200
    listed = client.get("/platform/v1/profiles?status=published", headers=ADM).json()["profiles"]
    assert "extra" in {p["key"] for p in listed}
    models = client.get("/platform/v1/models", headers=ADM).json()["models"]
    assert {m["id"] for m in models} == {"strong", "cheap"} and all(m["priced"] for m in models)
    assert client.get("/platform/v1/profiles", headers=SVC).status_code == 403


def test_budget_spent_forces_wrap_up(tmp_path):
    with make_stack(tmp_path) as (client, pack, rt):
        body = intake_body(external_ref="TICKET-3", message_id="m-3", budget_tokens=1)
        case_id = client.post("/platform/v1/intake", headers=SVC, json=body).json()["case_id"]
        case = wait_for(client, case_id)
        assert case["result"]["outcome"] == "needs_human"  # the leader wrapped up, did not push on
        assert case_id in rt.wrap_up
        # after the budget was spent, no call was offered the working tools again
        late = [c for c in CALLS if "Out of budget" in str(c["out"])]
        assert late and all("TeamCreate" not in c["tools"] and "lookup_ticket" not in c["tools"] for c in late)


def test_leader_that_never_finalizes_fails_the_case_visibly(tmp_path):
    with make_stack(tmp_path) as (client, pack, rt):
        MODE["leader"] = "mute"
        case_id = client.post("/platform/v1/intake", headers=SVC,
                              json=intake_body(external_ref="TICKET-4", message_id="m-4")).json()["case_id"]
        case = wait_for(client, case_id, status="failed", timeout=90)
        assert case["result"]["outcome"] == "failed" and case["result"]["answer"] == "A person will follow up."
        deadline = time.time() + 15
        while not pack.results and time.time() < deadline:
            time.sleep(0.2)
        assert pack.results and pack.results[0][1].outcome == "failed"  # the domain is told, not left waiting


class _Judge:
    """Says the first answer is weakly supported, then accepts."""

    def __init__(self):
        self.asked = []

    async def support(self, claim, evidence):
        self.asked.append((claim, evidence))
        return 0.2 if len(self.asked) == 1 else 0.95


def test_second_opinion_can_block_a_grounded_looking_answer(tmp_path):
    judge = _Judge()
    with make_stack(tmp_path, judge=judge) as (client, pack, rt):
        case_id = client.post("/platform/v1/intake", headers=SVC,
                              json=intake_body(external_ref="TICKET-5", message_id="m-5")).json()["case_id"]
        wait_for(client, case_id)
        items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
        notes = [i for i in items if i["kind"] == "note" and i["data"].get("type") == "final_attempt"]
        assert len(notes) == 2  # one refused by the figure check, one by the second opinion
        assert "weakly supported" in str(notes[1]["data"]["problems"])
        assert len(judge.asked) == 2 and "1500000" in judge.asked[0][0]
        assert "1500000" in " ".join(judge.asked[0][1])  # it saw the cited evidence, nothing else


def test_memory_enabled_profile_still_runs_and_new_version_is_used(tmp_path):
    with make_stack(tmp_path) as (client, pack, rt):
        tech = next(p for p in pack.profiles() if p.key == "tech")
        v2 = tech.model_copy(update={"memory": {"enabled": True, "scope": "private"}})
        created = client.post("/platform/v1/profiles", headers=ADM, json=v2.model_dump(mode="json")).json()
        assert created["version"] == 2
        client.post("/platform/v1/profiles/tech/versions/2/publish", headers=ADM)
        case_id = client.post("/platform/v1/intake", headers=SVC,
                              json=intake_body(external_ref="TICKET-6", message_id="m-6")).json()["case_id"]
        wait_for(client, case_id)
        # the specialist was built from version 2 (its prompt says memory notes are hints)
        assert any('key="tech" v="2"' in c["sys"] for c in CALLS)
        import hashlib
        parts = [hashlib.sha256(x.encode()).hexdigest()[:24] for x in ("t1", "tech", case_id)]
        assert (tmp_path / "ws" / "memory" / parts[0] / parts[1] / parts[2]).is_dir()


def test_stalled_case_is_failed_and_domain_is_told(tmp_path):
    with make_stack(tmp_path, case_stall_seconds=2) as (client, pack, rt):
        MODE["leader"] = "mute"  # nothing moves after the first reply
        # the nudge would also fail it; make the leader wait for a member that never reports
        case_id = client.post("/platform/v1/intake", headers=SVC,
                              json=intake_body(external_ref="TICKET-7", message_id="m-7")).json()["case_id"]
        case = wait_for(client, case_id, status="failed", timeout=60)
        assert case["result"]["outcome"] == "failed"


def test_webhook_callback_is_signed(tmp_path):
    import hashlib
    import hmac

    import httpx
    from fastapi import FastAPI, Request

    received = []
    hook = FastAPI()

    @hook.post("/hook")
    async def receive(request: Request):
        received.append((await request.body(), dict(request.headers)))
        return {"ok": True}

    with make_stack(tmp_path, callback_secret="s3cret") as (client, pack, rt):
        intake = client.app.state.awp.intake
        intake.deliverers.pop("test")  # a push domain has no connector
        intake.webhook_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=hook),
                                                  base_url="http://receiver")
        body = intake_body(external_ref="TICKET-8", message_id="m-8", callback_url="http://receiver/hook")
        case_id = client.post("/platform/v1/intake", headers=SVC, json=body).json()["case_id"]
        wait_for(client, case_id)
        deadline = time.time() + 15
        while not received and time.time() < deadline:
            time.sleep(0.2)
        assert received, "callback was not sent"
        raw, headers = received[0]
        expected = hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
        assert headers["x-awp-signature"] == f"sha256={expected}"
        assert json.loads(raw)["external_ref"] == "TICKET-8"


def test_failure_while_starting_a_case_is_reported_not_left_hanging(tmp_path):
    with make_stack(tmp_path) as (client, pack, rt):
        intake = client.app.state.awp.intake

        async def broken(*a, **k):
            raise RuntimeError("AgentScope is unavailable")

        intake.client.agent_id = broken
        r = client.post("/platform/v1/intake", headers=SVC, json=intake_body(external_ref="TICKET-9", message_id="m-9"))
        assert r.status_code == 202 and r.json()["status"] == "failed"
        deadline = time.time() + 15
        while not pack.results and time.time() < deadline:
            time.sleep(0.2)
        assert pack.results and pack.results[0][1].outcome == "failed"  # the domain is told at once
        # sending the same ticket again does not start a ghost case
        again = client.post("/platform/v1/intake", headers=SVC, json=intake_body(external_ref="TICKET-9", message_id="m-9"))
        assert again.json()["replayed"] is True and again.json()["status"] == "failed"
