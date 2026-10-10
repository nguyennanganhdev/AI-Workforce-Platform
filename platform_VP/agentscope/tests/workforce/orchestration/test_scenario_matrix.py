"""150 individually collected local scenarios; no production or integration claims."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from _support import FakeCatalog, FakeIdentity, FakeRepository, FakeRuntimeHooks, KEY, SCOPE
from scenario_catalog import CASES
from wf_orchestration_under_test import (
    CapabilityRouter, ConversationService, EvaluationRunner, HandoffService,
    MemberService, MessageService, RunService, SharedStateService, TeamRuntimeAdapter,
)
from wf_orchestration_under_test._messages import shared_context
from wf_orchestration_under_test._mentions import resolve_entity, resolve_recipient
from wf_orchestration_under_test._models import OrchestrationError
from wf_orchestration_under_test.workflows._checkpoint import apply_cause, close_checkpoint
from wf_orchestration_under_test.workflows._policy import continuation, post_status
from wf_orchestration_under_test.partner_events._projection import project_event, encode_sse, validate_cursor
from wf_orchestration_under_test.workflows._ingress import TicketIngress
from test_ingress import FakeJobs, FakePartnerGuard


async def fixture():
    f = SimpleNamespace(repo=FakeRepository(), identity=FakeIdentity(), catalog=FakeCatalog())
    f.hooks = FakeRuntimeHooks(f.repo)
    f.runtime = TeamRuntimeAdapter(identity=f.identity, provision_pinned_group=f.hooks.provision,
                                   send_team_task=f.hooks.send)
    f.router = CapabilityRouter(f.catalog, f.identity)
    f.conversations = ConversationService(f.repo, f.identity)
    f.states = SharedStateService(f.repo, f.identity)
    f.runs = RunService(f.repo, f.identity, f.router, f.runtime)
    f.tasks = HandoffService(f.repo, f.identity, f.runtime, clock=lambda: 1000)
    f.conversation = await f.conversations.create(SCOPE)
    return f


async def start(f, needs=("hotel",), conversation=None):
    conversation = conversation or f.conversation
    return await f.runs.start(SCOPE, conversation.conversation_id, needs,
                              expected_revision=conversation.state_revision)


async def exercise(case):
    f = await fixture()
    d, action = deepcopy(case["input"]), case["action"]
    if action == "conversation":
        if d.pop("read_foreign", False):
            return await f.conversations.read_state({**SCOPE, "manager_account_id": "other"}, f.conversation.conversation_id)
        f.identity.revoked = d.pop("revoked", False)
        before = deepcopy(f.repo.rows)
        try:
            result = await f.conversations.create(SCOPE, **d)
        except OrchestrationError:
            assert f.repo.rows == before
            raise
        assert result.timezone == d.get("timezone", "UTC")
        return result.mode

    if action == "router":
        hotel = next(c for c in f.catalog.items if c["agent_id"] == "Hotel")
        mutation = d.get("mutation")
        if mutation == "draft":
            hotel["status"] = "draft"
        elif mutation == "revoked":
            f.catalog.deployments["Hotel"]["status"] = "revoked"
        elif mutation == "foreign":
            hotel["scope"] = (*KEY[:3], "other")
        elif mutation == "hash":
            hotel["manifest_hash"] = "tampered"
        elif mutation == "version":
            f.catalog.deployments["Hotel"]["active_version_id"] = "Hotel-v9"
        elif mutation == "ambiguous":
            f.catalog.add("Hotel2", "hotel")
        selected, revision = await f.router.select(SCOPE, d.get("needs", ["hotel"]))
        assert revision == "revision-1"
        assert f.hooks.groups == {}
        return sorted(m["agent_id"] for m in selected)

    if action == "facts":
        stored = f.repo.rows[("conversation", KEY, f.conversation.conversation_id)]
        if d.get("expired_proposal"):
            stored.proposals["p"] = {"status": "current", "expires_at": 1000}
            return await f.states.select_proposal(SCOPE, stored.conversation_id, 0, "p", now=1000)
        if d.get("protect") or d.get("invalidate"):
            stored.facts["budget"] = 100
            stored.provenance["budget"] = {"kind": "user", "ref": "original"}
        if d.get("invalidate"):
            stored.proposals["p"] = {"status": "current", "expires_at": 2000}
            stored.selected_refs["proposal_id"] = "p"
        before = deepcopy(f.repo.rows)
        try:
            result = await f.states.patch_facts(SCOPE, stored.conversation_id, 0, d.get("facts", {}),
                source_kind="tool" if d.get("protect") else d.get("source_kind", "user"),
                source_ref=d.get("source_ref", "input-message"))
        except OrchestrationError:
            assert f.repo.rows == before
            raise
        assert result.state_revision == 1
        if d.get("invalidate"):
            assert result.proposals["p"]["status"] == "stale" and result.selected_refs == {}
            return "stale-and-cleared"
        assert all(v == {"kind": "user", "ref": "input-message"} for v in result.provenance.values())
        return result.facts

    if action == "handoff":
        run = await start(f)
        if "limit" in d:
            setattr(f.repo.rows[("run", KEY, run.run_id)], d["limit"], 0)
        sender = {"foreign": "foreign-session", "self": run.members[0]["session_id"]}.get(d.get("sender"), run.leader_session_id)
        before = deepcopy(f.repo.rows)
        try:
            task = await f.tasks.create(SCOPE, run.run_id, sender, d.get("recipient", "Hotel"),
                "x" * d["content_length"] if "content_length" in d else d.get("content", "find hotel"),
                d.get("context_refs", []), timeout_seconds=d.get("timeout_seconds", 60))
        except OrchestrationError:
            assert not f.hooks.deliveries and f.repo.rows == before
            raise
        assert len(f.hooks.deliveries) == 1
        return task["status"]

    if action == "runtime":
        mode = d.get("mode")
        if mode == "retry":
            f.hooks.fail = True
            with pytest.raises(TimeoutError):
                await start(f)
            pending = next(deepcopy(v) for (kind, _, _), v in f.repo.rows.items() if kind == "run")
            f.hooks.fail = False
            recovered = await f.runs.resume_materialization(SCOPE, pending.run_id)
            return recovered.members == pending.members and recovered.group_id == pending.group_id and len(f.hooks.groups) == 1
        first = await start(f)
        if mode in ("isolation", "version"):
            if mode == "version":
                f.catalog.add("Hotel", "hotel", version="v4")
            second = await start(f, conversation=await f.conversations.create(SCOPE))
            if mode == "version":
                return [first.members[0]["version_id"], second.members[0]["version_id"]]
            return first.group_id != second.group_id and first.members[0]["session_id"] != second.members[0]["session_id"]
        if mode == "foreign":
            before = deepcopy(f.hooks.groups)
            try:
                return await f.runtime.materialize({**SCOPE, "area_id": "other"}, first)
            finally:
                assert f.hooks.groups == before
        original = f.runtime.provision
        async def tampered(scope, run, *, idempotency_key):
            result = await original(scope, run, idempotency_key=idempotency_key)
            if d["tamper"] in ("group_id", "leader_session_id"):
                result[d["tamper"]] = "wrong"
            else:
                result["members"][0][d["tamper"]] = "wrong"
            return result
        f.runtime.provision = tampered
        return await f.runtime.materialize(SCOPE, first)

    if action == "recipient":
        run = await start(f, ("hotel", "car") if d.pop("duplicate_name", False) else ("hotel",))
        if len(run.members) == 2:
            for m in run.members:
                m["name"] = "Same"
        conversation = f.conversation
        questions = d.pop("questions", None)
        if questions:
            conversation.pending_questions["q1"] = {"message_id": "m1", "session_id": run.members[0]["session_id"]}
            if questions == "two":
                conversation.pending_questions["q2"] = {"message_id": "m2", "session_id": run.leader_session_id}
            if questions == "foreign":
                conversation.pending_questions["q1"]["session_id"] = "foreign"
        if "message_agent" in d:
            conversation.messages = [{"message_id": "m1", "agent_id": d.pop("message_agent")}]
        if d.pop("foreign_context", False):
            conversation.scope = (*KEY[:3], "other")
        session = resolve_recipient(run, conversation, **d)
        return "leader" if session == run.leader_session_id else next(m["agent_id"] for m in run.members if m["session_id"] == session)

    if action == "entity":
        f.conversation.facts["candidates"] = {"hotel": [{"id": value} for value in d["ids"]]}
        if "selected" in d:
            f.conversation.selected_refs["hotel"] = d["selected"]
        return resolve_entity(f.conversation, "hotel", explicit_ref=d.get("explicit_ref"))["id"]

    if action == "message":
        if not d.get("no_run"):
            run = await start(f)
            if d.get("cancelled"):
                f.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        deliveries = []
        async def deliver(scope, message, *, idempotency_key):
            saved = f.repo.rows[("conversation", KEY, f.conversation.conversation_id)].messages
            assert any(m["message_id"] == message["message_id"] and m["delivery_status"] == "pending" for m in saved)
            deliveries.append(message)
        service = MessageService(f.repo, f.identity, deliver)
        command = dict(client_message_id="x" * d["id_length"] if "id_length" in d else d.get("client_message_id", "m1"),
                       content="x" * d["content_length"] if "content_length" in d else d.get("content", "hello"),
                       target_agent_id=d.get("target_agent_id"))
        try:
            first = await service.send_message(SCOPE, f.conversation.conversation_id, **command)
        except OrchestrationError:
            assert deliveries == []
            raise
        if d.get("retry"):
            if d["retry"] == "changed":
                command["content"] = "changed"
            try:
                repeated = await service.send_message(SCOPE, f.conversation.conversation_id, **command)
            finally:
                assert len(deliveries) == 1
            assert repeated == first
            return "one-delivery"
        assert len(deliveries) == 1
        return first["delivery_status"]

    if action == "context":
        f.conversation.facts = {"destination": "Ha Long", "preferences": ["quiet"]}
        f.conversation.messages = [{"content": "private"}]
        result = shared_context(f.conversation, selected_fact_keys=d["keys"])
        if d.get("mutate"):
            result["preferences"].append("injected")
            return f.conversation.facts["preferences"]
        return result

    if action == "evaluation":
        snapshot = {"scope": SCOPE, "manifest_hash": "hash", "manifest": {"agent": {"name": "Hotel"}}}
        if d.get("snapshot") == "missing_manifest":
            snapshot.pop("manifest")
        elif d.get("snapshot") == "foreign":
            snapshot["scope"] = {**SCOPE, "manager_account_id": "other"}
        calls = []
        async def guard(scope, mode):
            calls.append("guard")
            assert scope == SCOPE and mode == d.get("mode", "mock")
            return None if d.get("guard_none") else {"mode": mode}
        async def invoke(scope, version, case_input, backend_guard):
            calls.append("invoke")
            assert backend_guard["mode"] == d.get("mode", "mock")
            result = {"status": "completed", "transcript": ["answer"], "tool_traces": [], "cost_minor": 0}
            if d.get("result") == "missing_traces":
                result.pop("tool_traces")
            elif d.get("result") == "negative_cost":
                result["cost_minor"] = -1
            elif d.get("result") in ("failed", "cancelled"):
                result["status"] = d["result"]
            return result
        runner = EvaluationRunner(f.identity, invoke, invoke, guard)
        try:
            result = await runner.run_case(SCOPE, snapshot, {"input": "question"}, d.get("mode", "mock"))
        finally:
            if d.get("snapshot") or d.get("mode") == "production":
                assert calls == []
            elif d.get("guard_none"):
                assert calls == ["guard"]
            else:
                assert calls == ["guard", "invoke"]
        return result["status"]

    if action == "member":
        run = await start(f)
        f.catalog.add("Car", "car", batch="other-batch")
        candidate = next(c for c in f.catalog.items if c["agent_id"] == "Car")
        if d.get("mode") == "draft":
            candidate["status"] = "draft"
        service = MemberService(f.repo, f.identity, f.router, f.runtime)
        added = await service.add(SCOPE, run.run_id, candidate, expected_revision=run.revision, reason=d.get("reason", "car required"))
        if d.get("mode") == "duplicate":
            again = await service.add(SCOPE, run.run_id, candidate, expected_revision=added.revision, reason="retry")
            return again == added and len(f.hooks.groups) == 2
        assert added.group_id == run.group_id and added.members[0]["session_id"] == run.members[0]["session_id"]
        return sorted(m["agent_id"] for m in added.members)

    if action == "policy":
        return list(continuation(policy=d.get("policy", {"effect": "side_effect"}),
                                 outcome=d.get("outcome", {}), http_pending=d.get("http_pending", False)))
    if action == "http_status":
        return post_status(d["status"])
    if action in ("checkpoint", "close"):
        checkpoint = {"state": d.get("state", "awaiting_user"), "revision": 1, "fence": 7,
                      "applied_causes": [], "pending_causes": [], "group_id": "g1", "session_ids": ["s1"],
                      "invoke_runtime": False, "pending_hitl": d.get("pending_hitl", False)}
        original = deepcopy(checkpoint)
        if action == "close":
            twice = d.pop("twice", False)
            result = close_checkpoint(checkpoint, **{"expected_revision": 1, **d})
            assert checkpoint == original and not result["invoke_runtime"] and result["next_action"] == "none"
            if twice:
                assert close_checkpoint(result, expected_revision=result["revision"]) == result
                return "idempotent"
            return result["state"]
        cause = {"cause_id": "cause-1", "kind": d.get("kind", "user_reply")}
        result = apply_cause(checkpoint, cause, fence=d.get("fence", 7), expected_revision=d.get("revision", 1))
        assert checkpoint == original and result["group_id"] == "g1" and result["session_ids"] == ["s1"]
        if d.get("duplicate"):
            assert apply_cause(result, cause, fence=7, expected_revision=result["revision"]) == result
            return "idempotent"
        if d.get("pending_hitl"):
            assert result["pending_causes"] == [cause] and not result["invoke_runtime"]
            return "queued-without-runtime"
        assert result["invoke_runtime"] and result["revision"] == 2
        return result["state"]

    if action == "ingress":
        guard, jobs = FakePartnerGuard(), FakeJobs(f.repo)
        ingress = TicketIngress(f.repo, guard, jobs)
        envelope = {"schema_version": "1", "command_type": "start_workflow", "external_request_id": "req-1",
                    "external_management_ref": "management", "external_user_id": "user", "external_ticket_id": "ticket",
                    "external_conversation_id": "chat", "message": {"type": "text", "text": "hello"}}
        envelope.update(d.get("patch", {}))
        if "remove" in d:
            envelope.pop(d["remove"])
        before = deepcopy(f.repo.rows)
        if d.get("mode") == "rollback":
            jobs.fail = True
            with pytest.raises(RuntimeError, match="test crash"):
                await ingress.accept("authenticated-test-actor", envelope)
            assert f.repo.rows == before
            return "empty-storage"
        try:
            first = await ingress.accept(d.get("actor", "authenticated-test-actor"), envelope)
        except OrchestrationError:
            assert f.repo.rows == before
            raise
        if d.get("mode") in ("retry", "conflict"):
            if d["mode"] == "conflict":
                envelope["message"]["text"] = "changed"
            try:
                repeated = await ingress.accept("authenticated-test-actor", envelope)
            finally:
                assert sum(k[0] == "job" for k in f.repo.rows) == 1
            assert first == repeated
            return "same-receipt"
        assert first["http_status"] == 202 and first["next_action"] == "watch_request"
        assert sum(k[0] == "job" for k in f.repo.rows) == 1
        return "accepted-once"

    if action == "event":
        audience = dict(partner_client_id="partner", external_user_id="user", external_ticket_id="ticket", external_conversation_id="chat")
        binding = dict(conversation_id="c1", workflow_id="w1", audience=audience)
        event = dict(event_id="e1", event_type="assistant.message", sequence=10, conversation_id="c1", workflow_id="w1",
                     created_at="2026-10-10T00:00:00Z", payload=dict(message_id="m1", speaker="Hotel", content="answer", credential="test-secret"))
        mode = d.get("mode")
        authorized = {**audience, "external_ticket_id": "other"} if mode == "foreign_audience" else audience
        if mode == "foreign_workflow":
            event["workflow_id"] = "other"
        elif mode == "internal":
            event["event_type"] = "runtime.trace"
        elif mode in ("cursor_boundary", "cursor_expired"):
            return validate_cursor(dict(conversation_id="c1", audience=audience, sequence=10),
                                   conversation_id="c1", audience=audience, retention_floor=10 if mode == "cursor_boundary" else 11)
        projected = project_event(event, binding, authorized_audience=authorized)
        if mode == "sse_injection":
            projected["event_id"] = "e1\nevent: fake"
            return encode_sse(projected)
        assert projected["payload"] == dict(message_id="m1", speaker="Hotel", text="answer")
        assert "test-secret" not in encode_sse(projected)
        return "public-message"
    raise AssertionError(f"Unimplemented case action: {action}")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_scenario(case):
    expected = case["expected"]
    if isinstance(expected, str) and expected.startswith("!"):
        with pytest.raises(OrchestrationError) as error:
            asyncio.run(exercise(case))
        assert error.value.code == expected[1:]
    else:
        assert asyncio.run(exercise(case)) == expected


def test_catalog_has_unique_ids_and_fifty_executable_cases_per_stage():
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert {stage: sum(c["stage"] == stage for c in CASES) for stage in ("G1", "G2", "G3")} == {"G1": 50, "G2": 50, "G3": 50}
