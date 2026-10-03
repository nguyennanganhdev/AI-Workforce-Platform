"""The Vinhomes composition: real Supervisor, real store on disk, a backend that behaves like the API."""
import httpx
import pytest

from adapters.backend.errors import AdapterError
from vinhomes.backend import Backend, Refused
from vinhomes.runtime import Runtime, Store

TENANT = "11111111-1111-5111-a111-111111111111"


def message(ticket="ticket-1", team="team-1", identity="input-1"):
    return dict(schema_version="2.0", message_id=identity, correlation_id="run-reception",
                sent_at="2026-10-03T10:00:00+00:00", message_type="ticket_submitted", message="Vòi nước bếp bị rò",
                tenant_id=TENANT, domain_id="domain", domain_name="Vinhomes", workspace_id="workspace", team_id=team,
                ticket_id=ticket, ticket_code="VH-" + ticket.upper(), ticket_generation=0, ticket_version="1",
                resident=dict(resident_id="resident", resident_name="Cư dân", phone_number="+84900000001"),
                location=dict(location_scope_id="scope", unit_id="unit", unit_number="1201",
                              building_id="building", building_code="S1.01", building_name="Sapphire 1 - S1.01"),
                request=dict(title="Vòi nước rò", description="Vòi nước bếp bị rò từ sáng", request_kind="incident",
                             category_id="technical", priority="normal", severity="minor", is_emergency=False,
                             triage_decision_id=None, handoff_reason="needs_staff"),
                facts=[], file_ids=[], created_at="2026-10-03T09:59:00+00:00")


class FakeBackend:
    """What /internal/coordination/v1 does, in memory. Results are stored by id, like the real one."""

    def __init__(self, *messages):
        self.items = [{"team_id": m["team_id"], "message": m} for m in messages]
        self.results, self.sent, self.reports = {}, [], []
        self.unreachable = self.revoked = self.finished = False
        self.tamper = self.refuse_send = False
        self.lose_reply = None  # "stored": applied but the reply is lost; "dropped": never arrived

    def _check(self):
        if self.unreachable:
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)

    def context(self, team):
        wire = next(i["message"] for i in self.items if i["team_id"] == team)
        return dict(tenant_id=TENANT, principal_id="workspace-principal", initiated_by_user_id="resident",
                    domain_id="domain", workspace_id="workspace", ticket_id=wire["ticket_id"],
                    ticket_generation=0, binding_id="binding-" + team, run_id="run-" + team)

    async def inbox(self, cursor, limit=50):
        self._check()
        start = int(cursor or 0)
        items = self.items[start:start + limit]
        return {"items": items, "next_cursor": str(start + len(items)) if items else cursor}

    async def verify(self, team_id, message_id):
        self._check()
        if self.finished:
            raise Refused(409)
        stored = next(i["message"] for i in self.items if i["message"]["message_id"] == message_id)
        if self.tamper:
            stored = {**stored, "message": "Nội dung khác với bản đã lưu"}
        return {"message": stored, "context": self.context(team_id), "supervisor_run_id": "run-" + team_id}

    async def send(self, wire):
        self._check()
        self.sent.append(wire)
        if self.refuse_send:
            raise Refused(409)
        lost, self.lose_reply = self.lose_reply, None
        if lost != "dropped":
            self.results[wire["message_id"]] = wire
        if lost:
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)
        return {"message_id": wire["message_id"], "status": "accepted", "replayed": False}

    async def view(self, team_id):
        self._check()
        if self.revoked:
            raise Refused(409)
        return {"context": self.context(team_id), "ticket_version": "1", "supervisor_version_id": "supervisor-v1"}

    async def authorize(self, team_id, action_id, channel, operation):
        if self.revoked:
            raise Refused(409)
        return {"authorized": True}

    async def result(self, team_id, message_id):
        self._check()
        return {"found": message_id in self.results, "message_id": message_id, "status": "accepted"}

    async def status(self, team_id, phase, pause_reason, state_version):
        self.reports.append((team_id, phase, pause_reason))
        return {"ok": True}


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def rig(tmp_path):
    clock = Clock()
    path = tmp_path / "state" / "coordination.sqlite3"

    def start(backend):
        return Runtime(backend, Store(path, clock=clock))

    return start, clock


def session(runtime, ticket="ticket-1"):
    return next(s for s in runtime.store.sessions() if s.get("ticket_id") == ticket)


async def test_a_ticket_from_reception_is_accepted_and_handed_to_management(rig):
    start, _ = rig
    backend = FakeBackend(message())
    runtime = start(backend)
    await runtime.round()
    [accepted] = backend.sent
    assert accepted["message_type"] == "accepted" and accepted["supervisor_run_id"] == "run-team-1"
    assert (accepted["team_id"], accepted["ticket_id"], accepted["ticket_version"]) == ("team-1", "ticket-1", "1")
    # Nobody to plan with yet: the session stops with its reason instead of calling a model.
    assert session(runtime) == {
        "ticket_id": "ticket-1", "ticket_generation": 0, "ticket_code": "VH-TICKET-1", "run_id": "run-team-1",
        # Checkpoints: created (0), accepted being sent (1), receipt recorded (2), paused (3).
        "phase": "paused", "pause_reason": "planner:no_specialist_available", "checkpoint_version": 3,
        "results_sent": ["accepted"], "action_in_flight": None}
    assert backend.reports == [("team-1", "paused", "planner:no_specialist_available")]
    assert not await runtime.work()  # the inbox item was acknowledged


async def test_a_message_read_again_or_after_a_restart_is_handled_once(rig):
    start, _ = rig
    backend = FakeBackend(message())
    runtime = start(backend)
    await runtime.round()
    runtime.store.save_cursor("0")  # the backend hands the same message out again
    await runtime.round()
    restarted = start(backend)      # a new process on the same state file
    await restarted.round()
    assert len(backend.sent) == 1 and session(restarted)["results_sent"] == ["accepted"]


async def test_two_tickets_are_two_sessions(rig):
    start, _ = rig
    backend = FakeBackend(message(), message("ticket-2", "team-2", "input-2"))
    runtime = start(backend)
    await runtime.round()
    assert {(m["ticket_id"], m["supervisor_run_id"]) for m in backend.sent} == {
        ("ticket-1", "run-team-1"), ("ticket-2", "run-team-2")}
    assert session(runtime, "ticket-2")["run_id"] == "run-team-2" and len(runtime.store.sessions()) == 2


@pytest.mark.parametrize("lost,sends", [("stored", 1), ("dropped", 2)])
async def test_a_lost_reply_is_reconciled_by_message_id(rig, lost, sends):
    start, clock = rig
    backend = FakeBackend(message())
    backend.lose_reply = lost
    runtime = start(backend)
    await runtime.round()
    assert session(runtime)["action_in_flight"] == "unknown" and session(runtime)["results_sent"] == []
    await runtime.round()           # still inside the retry delay: nothing is sent blindly
    assert len(backend.sent) == 1
    clock.now += 6
    await runtime.round()
    # Stored: the receipt is found and nothing is sent again. Dropped: the unchanged wire goes again.
    assert len(backend.sent) == sends and len({m["message_id"] for m in backend.sent}) == 1
    assert backend.sent[0] == backend.sent[-1]
    assert session(runtime)["results_sent"] == ["accepted"] and session(runtime)["action_in_flight"] is None


async def test_a_refused_result_pauses_the_session_with_the_reason(rig):
    start, _ = rig
    backend = FakeBackend(message())
    backend.refuse_send = True
    runtime = start(backend)
    await runtime.round()
    assert session(runtime)["phase"] == "paused" and session(runtime)["pause_reason"] == "backend_rejected:409"
    assert len(backend.sent) == 1 and backend.results == {}


async def test_a_team_that_lost_its_authority_sends_nothing(rig):
    start, _ = rig
    backend = FakeBackend(message())
    backend.revoked = True
    runtime = start(backend)
    await runtime.round()
    assert backend.sent == []


async def test_a_message_that_differs_from_the_stored_one_is_kept_for_a_person(rig):
    start, _ = rig
    backend = FakeBackend(message())
    backend.tamper = True
    runtime = start(backend)
    await runtime.round()
    assert backend.sent == [] and runtime.store.sessions() == [{"blocked_inbox_items": 1}]


async def test_a_message_for_a_team_that_already_finished_is_obsolete_not_blocked(rig):
    start, _ = rig
    backend = FakeBackend(message())
    backend.finished = True
    runtime = start(backend)
    await runtime.round()
    assert backend.sent == [] and runtime.store.sessions() == [] and not await runtime.work()


async def test_an_unreachable_backend_is_retried_and_nothing_is_lost(rig):
    start, clock = rig
    backend = FakeBackend(message())
    runtime = start(backend)
    await runtime.poll()
    backend.unreachable = True
    await runtime.round()
    assert backend.sent == [] and runtime.store.sessions() == []
    backend.unreachable = False
    clock.now += 16
    await runtime.round()
    assert [m["message_type"] for m in backend.sent] == ["accepted"]


async def test_the_client_tells_a_refusal_from_an_unknown_outcome():
    answers = {"/internal/coordination/v1/inbox": httpx.Response(200, json={"items": [], "next_cursor": None}),
               "/internal/coordination/v1/teams/t/view": httpx.Response(409, json={"detail": "finished"}),
               "/internal/coordination/v1/reception/send": httpx.Response(503)}

    def handler(request):
        if request.url.path.endswith("/results/m"):
            raise httpx.ReadTimeout("lost", request=request)
        assert request.headers["authorization"] == "Bearer " + "t" * 32
        return answers[request.url.path]

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        backend = Backend("http://backend.test", "t" * 32, client)
        assert await backend.inbox(None) == {"items": [], "next_cursor": None}
        with pytest.raises(Refused) as refused:
            await backend.view("t")
        assert refused.value.status == 409 and not refused.value.outcome_unknown
        for call in (backend.send({}), backend.result("t", "m")):
            with pytest.raises(AdapterError) as unknown:
                await call
            assert unknown.value.outcome_unknown
    with pytest.raises(ValueError):
        Backend("http://backend.test", "short", None)
