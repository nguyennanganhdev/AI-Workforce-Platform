"""The Vinhomes composition: real Supervisor, real store on disk, a backend that behaves like the API."""
import json

import httpx
import pytest

from adapters.backend.errors import AdapterError
from vinhomes.backend import Backend, Refused
from vinhomes.ports import OpenBot
from vinhomes.runtime import Runtime, Settings, Store

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
        # Published specialists offered for the ticket, who was admitted, and what the room mirrored.
        self.specialists, self.members, self.turns, self.mirrors = [], {}, [], []
        self.release_revoked = False
        self.tool_descriptors = []  # the read tools the member's version was approved with
        self.questions, self.answered = [], []  # asked by management inside a session; outcomes reported
        self.lose_outcome = False  # the next outcome report gets no answer
        # The plan table: one plan per team, kept under the request id that stored it.
        self.plans, self.plan_requests, self.approval_requests = {}, [], []
        self.lose_plan = self.refuse_plan = False
        self.decisions, self.delivered = {}, set()
        self.lose_delivery = False
        self.plan_history = {}
        self.commands, self.controlled = [], []

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
        plan = self.plans.get(team_id)
        version = 2 * plan["target_plan_version"] if plan else 1
        if plan and team_id in self.decisions and self.decisions[team_id]["event"]["payload"]["plan_version"] == plan["target_plan_version"]:
            version += 1
        return {"context": self.context(team_id), "ticket_version": str(version),
                "supervisor_version_id": "supervisor-v1", "specialists": self.specialists,
                "plan": plan and {"plan_id": "plan-" + team_id, "status": plan["status"],
                                  "management_recipient": "management-unit:m1",
                                  "approval_expires_at": "2999-01-01T00:00:00+00:00",
                                  "resident_recipient": "resident", "resident_approval_required": True,
                                  "resident_request_type": "plan_approval_requested",
                                  "resident_request_message": "Anh/chị đồng ý phương án này không?"}}

    async def plan(self, team_id, draft):
        self._check()
        self.plan_requests.append(draft)
        if self.refuse_plan:
            raise Refused(409)
        stored = self.plan_history.setdefault(draft["request_id"], {**draft, "status": "management_pending"})
        self.plans[team_id] = stored
        if (stored["request_id"], stored["payload_hash"]) != (draft["request_id"], draft["payload_hash"]):
            raise Refused(409)
        if self.lose_plan:
            self.lose_plan = False
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)
        return {"request_id": draft["request_id"], "status": "accepted", "payload_hash": draft["payload_hash"],
                "canonical_id": "plan-" + team_id, "ticket_version": str(2 * draft["target_plan_version"]),
                "plan_version": draft["target_plan_version"]}

    async def approval_request(self, team_id, plan_id, request):
        if self.plans[team_id]["status"] != "management_pending":
            raise Refused(409)
        self.approval_requests.append(plan_id)
        self.plans[team_id]["approval"] = request
        return {"status": "accepted", "plan_id": plan_id}

    def decide_plan(self, team="team-1", decision="approve"):
        plan = self.plans[team]
        plan["status"] = "resident_pending" if decision == "approve" else "rejected"
        self.delivered.discard(team)
        event = {"event_id": f"decision-{team}-{plan['target_plan_version']}", "event_type": "approval.responded", "schema_version": "1",
                 "tenant_id": TENANT, "aggregate_id": "plan-" + team, "aggregate_version": plan["target_plan_version"],
                 "occurred_at": "2026-10-04T10:00:00+00:00", "correlation_id": team,
                 "causation_id": plan["approval"]["approval_id"], "payload": {
                     **plan["approval"], "plan_id": "plan-" + team, "stage": "management_plan",
                     "decision": decision, "comment": "Đồng ý" if decision == "approve" else "Cần phương án khác"}}
        self.decisions[team] = {"team_id": team, "plan_id": "plan-" + team,
                                "context": self.context(team), "event": event}

    async def events(self):
        self._check()
        return {"items": [v for k, v in self.decisions.items() if k not in self.delivered]}

    async def management_event(self, team, plan):
        self._check()
        if self.revoked or self.finished:
            raise Refused(409)
        return self.decisions[team]

    async def decision_delivered(self, team, plan):
        if self.lose_delivery:
            self.lose_delivery = False
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)
        self.delivered.add(team)
        return {"ok": True}

    def request_control(self, runtime, operation, version=None):
        self.commands.append({"team_id": "team-1", "context": self.context("team-1"), "command": {
            "request_id": f"control-{len(self.commands)}", "operation": operation, "actor": "management",
            "expected_version": session(runtime)["checkpoint_version"] if version is None else version,
            "status": "queued"}})

    async def controls(self):
        return {"items": [c for c in self.commands if c["command"]["request_id"] not in {r[0] for r in self.controlled}]}

    async def control(self, team, request):
        return next(c for c in self.commands if c["command"]["request_id"] == request)

    async def control_result(self, team, request, result):
        self.controlled.append((request, result))
        return {"ok": True}

    async def admit(self, team_id, agent_version_id):
        offered = next((s for s in self.specialists if s["agent_version_id"] == agent_version_id), None)
        if offered is None:
            raise Refused(409)
        self.members[agent_version_id] = dict(
            agent_version_id=agent_version_id, role=offered["role"], platform_agent_id=offered["agent_id"],
            member_id="member-" + offered["agent_id"], binding_id="binding-" + offered["agent_id"], binding_generation=1,
            framework_agent_id=offered["agent_id"], framework_reference="openbot:binding-" + offered["agent_id"])
        return self.members[agent_version_id]

    async def turn_run(self, team_id, member_id, operation_id):
        self.turns.append(member_id)
        return {"run_id": f"run-turn-{len(self.turns)}"}

    async def release(self, team_id, member_id):
        if self.release_revoked:
            raise Refused(409)
        member = next(m for m in self.members.values() if m["member_id"] == member_id)
        wire = next(i["message"] for i in self.items if i["team_id"] == team_id)
        return dict(tenant_id=TENANT, workspace_id="workspace", ticket_id=wire["ticket_id"], ticket_generation=0,
                    groupchat_version_id="supervisor-v1", agent_version_id=member["agent_version_id"],
                    member_id=member_id, binding_id=member["binding_id"], binding_generation=1,
                    framework_reference=member["framework_reference"], thread_id=f"coordination:{team_id}:{member_id}",
                    evaluated=True, admin_approved=True, published=True, revoked=False, prompt_hash="p", config_hash="c",
                    knowledge_grants=[], capabilities=["technical"], tool_descriptors=self.tool_descriptors,
                    name="Kỹ thuật",
                    instructions="Bạn là agent kỹ thuật của Ban quản lý.")

    async def room(self, team_id, mirror):
        self.mirrors.append(mirror)
        return {"ok": True}

    async def mentions(self):
        self._check()
        waiting = [q for q in self.questions if q["message_id"] not in {a[0] for a in self.answered}]
        return {"items": [{**q, "context": self.context(q["team_id"])} for q in waiting]}

    async def mention_outcome(self, team_id, message_id, status, run_id):
        if self.lose_outcome:
            self.lose_outcome = False
            raise AdapterError("backend_outcome_unknown", retryable=True, outcome_unknown=True)
        self.answered.append((message_id, status, run_id))
        return {"ok": True}

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
        "actions_done": ["accepted"], "action_in_flight": None}
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
    assert len(backend.sent) == 1 and session(restarted)["actions_done"] == ["accepted"]


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
    assert session(runtime)["action_in_flight"] == "unknown" and session(runtime)["actions_done"] == []
    await runtime.round()           # still inside the retry delay: nothing is sent blindly
    assert len(backend.sent) == 1
    clock.now += 6
    await runtime.round()
    # Stored: the receipt is found and nothing is sent again. Dropped: the unchanged wire goes again.
    assert len(backend.sent) == sends and len({m["message_id"] for m in backend.sent}) == 1
    assert backend.sent[0] == backend.sent[-1]
    assert session(runtime)["actions_done"] == ["accepted"] and session(runtime)["action_in_flight"] is None


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


TECHNICAL = dict(agent_version_id="technical-v1", agent_id="technical", name="Kỹ thuật", role="technical",
                 description="Phân tích sự cố điện, nước, điều hòa", service_categories=["technical"], tools=[])
ANALYSIS = "Khả năng cao gioăng vòi bếp hỏng. Cần khóa van nhánh và thay gioăng, khoảng 30 phút."


PLAN = dict(summary="Thay gioăng vòi bếp", steps=["Khóa van nhánh", "Thay gioăng vòi bếp"],
            performer_role="Kỹ thuật viên nước", expected_duration="30 phút", conditions="Cư dân có mặt", cost=None)


def decide(prompt, plans=True):
    """A planner that follows the Supervisor's guide: give a task, run it, accept its answer, propose a plan."""
    state, catalog = prompt["state"], prompt["catalog"]
    room, agent = state["room"], next(iter(catalog))
    if not room["tasks"]:
        return {"kind": "tasks", "tasks": [{"task_id": "t1", "description": "Xác định nguyên nhân rò nước",
                                            "assignee_agent_version_id": agent}]}
    replies = [m["message_id"] for r in state["terminal_results"].values() if r["turn_status"] == "success"
               for m in r["messages"] if m["task_id"] == "t1" and m["sender"] == r["speaker_agent_version_id"]]
    if room["tasks"][0]["status"] == "completed" and plans:
        # Asked for a plan only, and it names a reply that does not exist: the references are not the model's to give.
        assert sorted(ref["$ref"].rsplit("/", 1)[1] for ref in prompt["schema"]["anyOf"]) == ["PauseDecision", "PlanDecision", "QuestionDecision"]
        return {"kind": "plan", "plan": {**PLAN, "result_refs": ["made-up"]}}
    if replies:
        return {"kind": "complete_task", "task_id": "t1", "result_refs": replies, "assessment": "Đủ căn cứ."}
    return {"kind": "run", "task_id": "t1", "agent_version_id": agent,
            "instruction": "Phân tích nguyên nhân và nêu việc cần làm."}


class Providers:
    """The model provider and the OpenBot, as one HTTP transport that records what it was asked."""

    def __init__(self, *replies, tool_call=None, tools_down=False, plans=True):
        self.plans = plans  # False: a model that goes round its finished task instead of planning
        # What the Bot answers, turn by turn; the last answer repeats.
        self.replies = list(replies) or [ANALYSIS]
        self.decisions, self.bot = [], []
        # A Bot that asks for this tool before it answers, and the tool host it reaches.
        self.tool_call, self.tools_down, self.tool_calls = tool_call, tools_down, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/chat/completions":
            assert request.headers["authorization"] == "Bearer model-key" and body["max_completion_tokens"] > 0
            decision = decide(json.loads(body["messages"][1]["content"]), self.plans)
            self.decisions.append(decision["kind"])
            return httpx.Response(200, json={"model": body["model"] + "-2026-03-17", "usage": {"total_tokens": 900},
                                             "choices": [{"message": {"content": json.dumps(decision)}}]})
        if request.url.path == "/internal/technical/v1/call":
            assert request.headers["authorization"] == "Bearer " + TOOLS_TOKEN
            self.tool_calls.append(body)
            if self.tools_down:
                return httpx.Response(503, text="down")
            return httpx.Response(200, json={"status": "OK", "data": {"outages": [OUTAGE]}, "errors": []})
        assert request.url.path == "/ag-ui" and request.headers["x-openbot-agent-token"] == "bot-token"
        # A model that thinks for a while before its first token is not a lost stream.
        assert request.extensions["timeout"]["read"] is None
        self.bot.append(body)
        run = {"threadId": body["threadId"], "runId": body["runId"]}
        if self.tool_call and not any(m["role"] == "tool" for m in body["messages"]):
            name, arguments = self.tool_call
            events = [{"type": "RUN_STARTED", **run}, {"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "assistant"},
                      {"type": "TEXT_MESSAGE_CONTENT", "messageId": "m", "delta": "Tôi kiểm tra sự cố đang diễn ra."},
                      {"type": "TEXT_MESSAGE_END", "messageId": "m"},
                      {"type": "TOOL_CALL_START", "toolCallId": "call-1", "toolCallName": name},
                      {"type": "TOOL_CALL_ARGS", "toolCallId": "call-1", "delta": json.dumps(arguments)},
                      {"type": "TOOL_CALL_END", "toolCallId": "call-1"}, {"type": "RUN_FINISHED", **run}]
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  content="".join(f"data: {json.dumps(e)}\n\n" for e in events).encode())
        events = [{"type": "RUN_STARTED", **run}, {"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "assistant"},
                  {"type": "TEXT_MESSAGE_CONTENT", "messageId": "m",
                   "delta": self.replies[min(len(self.bot), len(self.replies)) - 1]},
                  {"type": "TEXT_MESSAGE_END", "messageId": "m"}, {"type": "RUN_FINISHED", **run}]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content="".join(f"data: {json.dumps(e)}\n\n" for e in events).encode())


TOOLS_TOKEN = "tools-" + "t" * 32
OUTAGE = {"service_type": "water", "status": "in_progress", "reason": "Bảo trì bơm tăng áp"}
OUTAGE_TOOL = {"name": "technical__get_active_outage", "description": "Sự cố đang diễn ra",
               "parameters": {"type": "object", "properties": {"building_id": {"type": "string"}}, "required": ["building_id"]}}


@pytest.fixture
def staffed(tmp_path, monkeypatch):
    """A runtime with a planner model, an OpenBot and a tool host, and a backend that offers one technical agent."""
    monkeypatch.setenv("OPENAI_API_KEY", "model-key")
    monkeypatch.setenv("MANAGED_AGENT_TOKEN", "bot-token")
    settings = Settings(backend_url="http://backend", service_token="x" * 32, model="gpt-5.4-mini",
                        openbot=OpenBot("http://127.0.0.1:4200/ag-ui", "gpt-5.4-mini"),
                        tools_url="http://tools/internal/technical/v1", tools_token=TOOLS_TOKEN)

    def start(backend, providers):
        backend.specialists = [TECHNICAL]
        client = httpx.AsyncClient(transport=httpx.MockTransport(providers))
        return Runtime(backend, Store(tmp_path / "state" / "coordination.sqlite3", clock=Clock()),
                       client=client, settings=settings)

    return start


async def test_the_supervisor_brings_the_category_specialist_into_the_room_and_gets_its_analysis(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    assert [m["message_type"] for m in backend.sent] == ["accepted"]
    assert list(backend.members) == ["technical-v1"] and backend.turns == ["member-technical"]
    # Opening the room needs no model: the rules leave no choice.
    assert providers.decisions == ["tasks", "run", "complete_task", "plan"]
    # The Bot was given the agent's published instructions and the reply format, and no tool.
    [asked] = providers.bot
    assert [c["value"] for c in asked["context"]][0] == "Bạn là agent kỹ thuật của Ban quản lý."
    assert asked["tools"] == [] and asked["threadId"] == "coordination:team-1:member-technical:run-turn-1"
    given = json.loads(asked["messages"][0]["content"])
    assert given["instruction"] == "Phân tích nguyên nhân và nêu việc cần làm."
    assert "Vòi nước bếp bị rò từ sáng" in given["context"][0]["content"]  # the verified ticket, under the room's ACL
    # Management reads the task, the reply and the finished turn through the backend.
    mirror = backend.mirrors[-1]
    assert mirror["tasks"] == [{"task_id": "t1", "description": "Xác định nguyên nhân rò nước",
                                "assignee_agent_version_id": "technical-v1", "status": "completed"}]
    assert [(m["sender_agent_version_id"], m["content"], m["task_id"]) for m in mirror["messages"]] == [
        ("technical-v1", ANALYSIS, "t1")]
    assert mirror["runs"] == [{"run_id": "run-turn-1", "status": "succeeded"}]
    # The plan is stored by the backend, relying on the agent's reply, and waits for management.
    [draft] = backend.plan_requests
    reply = mirror["messages"][0]["message_id"]
    assert draft["plan"] == {**PLAN, "result_refs": [reply], "attachment_ids": []} and draft["ticket_version"] == "1"
    assert draft["target_plan_version"] == 1 and len(draft["payload_hash"]) == 64
    assert backend.approval_requests == ["plan-team-1"]
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("waiting_management", None, None)
    assert state["actions_done"][-2:] == ["plan", "approval.requested"]
    assert backend.reports[-1] == ("team-1", "waiting_management", None)
    assert not await runtime.work()


async def test_a_plan_whose_receipt_was_lost_is_stored_once(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    backend.lose_plan = True
    await runtime.round()
    assert session(runtime)["action_in_flight"] == "unknown" and backend.approval_requests == []
    runtime.store.clock.now += 6
    await runtime.round()
    # The unchanged request goes again under its id; the backend answers with the plan it already holds.
    first, second = backend.plan_requests
    assert first == second and len(backend.plans) == 1 and providers.decisions.count("plan") == 1
    assert session(runtime)["phase"] == "waiting_management" and backend.approval_requests == ["plan-team-1"]


async def test_management_approval_reaches_reception_once_across_a_restart(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.decide_plan()
    backend.lose_delivery = True
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_resident_plan"
    assert [m["message_type"] for m in backend.sent] == ["accepted", "plan_approval_requested"]
    asked = backend.sent[-1]
    assert asked["ticket_version"] == "3" and asked["message"] == "Anh/chị đồng ý phương án này không?"
    runtime = staffed(backend, providers)
    runtime.store.clock.now += 20
    await runtime.round()
    assert backend.delivered == {"team-1"} and len(backend.sent) == 2
    assert providers.decisions == ["tasks", "run", "complete_task", "plan"]


async def test_lost_resident_request_receipt_is_reconciled_without_asking_twice(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.decide_plan()
    backend.lose_reply = "stored"
    await runtime.round()
    assert session(runtime)["action_in_flight"] == "unknown" and not backend.delivered
    runtime.store.clock.now += 6
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_resident_plan" and backend.delivered == {"team-1"}
    assert len(backend.sent) == 2


async def test_management_refusal_requires_a_new_plan_and_two_fresh_approvals(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.decide_plan(decision="reject")
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_management"
    assert [d["target_plan_version"] for d in backend.plan_requests] == [1, 2]
    assert backend.plan_requests[-1]["ticket_version"] == "3"
    assert [m["message_type"] for m in backend.sent] == ["accepted"]
    backend.decide_plan(decision="approve")
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_resident_plan" and backend.sent[-1]["ticket_version"] == "5"


async def test_management_pause_keeps_an_approval_until_resume_then_can_stop_the_session(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.request_control(runtime, "pause")
    await runtime.round()
    assert session(runtime)["phase"] == "paused" and session(runtime)["pause_reason"] == "management_pause"
    backend.decide_plan()
    await runtime.round()
    assert len(backend.sent) == 1
    backend.request_control(runtime, "resume")
    await runtime.round()
    runtime.store.clock.now += 16
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_resident_plan" and len(backend.sent) == 2
    backend.request_control(runtime, "stop")
    await runtime.round()
    assert session(runtime)["phase"] == "cancelled" and backend.controlled[-1][1]["status"] == "applied"
    assert len(backend.sent) == 2  # stopping the session does not cancel the resident's ticket


async def test_a_stale_control_cannot_modify_the_checkpoint(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    version = session(runtime)["checkpoint_version"]
    backend.request_control(runtime, "stop", version=version - 1)
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_management" and session(runtime)["checkpoint_version"] == version
    assert backend.controlled[-1][1]["reason"] == "session_changed"


async def test_an_uncommitted_or_changed_management_decision_is_never_applied(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.decide_plan()
    await runtime.poll()
    backend.decisions["team-1"]["event"]["payload"]["decision"] = "reject"
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_management" and len(backend.sent) == 1
    assert not backend.delivered


async def test_a_plan_the_backend_refuses_stops_the_session_for_a_person(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    backend.refuse_plan = True  # for example: the ticket already has a plan waiting for a decision
    await runtime.round()
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("paused", "backend_rejected:409", None)
    assert backend.plans == {} and backend.approval_requests == []
    assert not await runtime.work()


async def test_a_session_the_model_failed_runs_again_on_its_own(staffed):
    class Outage(Providers):
        """A model provider that answers 503 while `down`."""

        down = True

        def __call__(self, request):
            if request.url.path == "/v1/chat/completions" and self.down:
                return httpx.Response(503, text="overloaded")
            return super().__call__(request)

    backend, providers = FakeBackend(message()), Outage()
    runtime = staffed(backend, providers)
    clock = runtime.store.clock
    await runtime.round()
    assert (session(runtime)["phase"], session(runtime)["pause_reason"]) == ("paused", "model_unavailable")
    # Not at once: the provider is asked again a minute later, then after as long as it has been failing.
    await runtime.round()
    assert providers.decisions == [] and session(runtime)["pause_reason"] == "model_unavailable"
    clock.now += 61
    await runtime.round()
    assert session(runtime)["pause_reason"] == "model_unavailable"
    clock.now += 30
    await runtime.round()  # one minute has not passed since the last failure
    before = session(runtime)["checkpoint_version"]
    providers.down = False
    await runtime.round()
    assert session(runtime)["checkpoint_version"] == before
    clock.now += 61
    await runtime.round()
    # The model is back: the session went on by itself to the plan that waits for management.
    assert providers.decisions[-1] == "plan" and session(runtime)["phase"] == "waiting_management"
    assert not await runtime.work()


async def test_an_outage_longer_than_two_hours_leaves_the_session_for_management(staffed):
    class Outage(Providers):
        down = True

        def __call__(self, request):
            if request.url.path == "/v1/chat/completions" and self.down:
                return httpx.Response(503, text="overloaded")
            return super().__call__(request)

    backend, providers = FakeBackend(message()), Outage()
    runtime = staffed(backend, providers)
    clock = runtime.store.clock
    await runtime.round()
    for _ in range(12):
        clock.now += 1900
        await runtime.round()
    stopped = session(runtime)["checkpoint_version"]
    providers.down = False
    clock.now += 4000
    await runtime.round()
    assert session(runtime)["checkpoint_version"] == stopped and session(runtime)["pause_reason"] == "model_unavailable"


async def test_a_session_paused_for_the_model_before_a_restart_is_tried_again_after_it(staffed):
    class Outage(Providers):
        down = True

        def __call__(self, request):
            if request.url.path == "/v1/chat/completions" and self.down:
                return httpx.Response(503, text="overloaded")
            return super().__call__(request)

    backend, providers = FakeBackend(message()), Outage()
    first = staffed(backend, providers)
    await first.round()
    assert session(first)["pause_reason"] == "model_unavailable"
    # A retry that fails again queues the next one itself; a restart then finds that session already queued.
    first.store.clock.now += 61
    await first.round()
    assert session(first)["pause_reason"] == "model_unavailable"
    providers.down = False
    restarted = staffed(backend, providers)  # the same state file: a new process
    for _ in range(3):
        restarted.store.clock.now += 200
        await restarted.round()
    assert session(restarted)["phase"] == "waiting_management"


async def test_a_session_left_mid_planning_by_a_stopped_process_is_taken_up_again(staffed):
    backend, providers = FakeBackend(message()), Providers()
    first = staffed(backend, providers)
    # The process stops after the session was opened and before the planner was asked anything.
    await first.poll()
    claim = await first.store.claim(first.owner, 60)
    wire = claim.payload["wire"]
    first.teams[(wire["tenant_id"], wire["ticket_id"], wire["ticket_generation"])] = claim.payload["team_id"]
    with first.store.lease_scope(claim):
        state = await first.service.handle_reception(wire, claim.payload["team_id"])
    assert state.phase == "planning"
    await first.store.ack(claim)
    restarted = staffed(backend, providers)
    await restarted.round()
    assert providers.decisions[-1] == "plan" and session(restarted)["phase"] == "waiting_management"


async def test_a_model_that_does_not_plan_leaves_the_analysis_to_management(staffed):
    backend, providers = FakeBackend(message()), Providers(plans=False)
    runtime = staffed(backend, providers)
    await runtime.round()
    # Every task is done and the model answered with something other than a plan: no second round.
    assert providers.decisions == ["tasks", "run", "complete_task", "complete_task"]
    state = session(runtime)
    assert (state["phase"], state["pause_reason"]) == ("paused", "planner:analysis_ready") and backend.plan_requests == []


async def test_an_empty_reply_is_a_failed_turn_and_the_task_is_run_again(staffed):
    backend, providers = FakeBackend(message()), Providers("  ", ANALYSIS)
    runtime = staffed(backend, providers)
    await runtime.round()
    # The first turn failed for certain: the room was free again and the Supervisor ran the task once more.
    mirror = backend.mirrors[-1]
    assert mirror["runs"] == [{"run_id": "run-turn-1", "status": "failed"}, {"run_id": "run-turn-2", "status": "succeeded"}]
    assert [m["content"] for m in mirror["messages"]] == [ANALYSIS]
    assert session(runtime)["phase"] == "waiting_management"


async def test_an_agent_that_keeps_failing_stops_the_session_for_a_person(staffed):
    backend, providers = FakeBackend(message()), Providers("  ")
    runtime = staffed(backend, providers)
    await runtime.round()
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("paused", "AGENT_FAILURE", None)
    assert [r["status"] for r in backend.mirrors[-1]["runs"]] == ["failed"] * 3 and backend.mirrors[-1]["messages"] == []
    assert not await runtime.work()


async def test_a_revoked_version_is_not_invoked(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    backend.release_revoked = True
    await runtime.round()
    assert providers.bot == []  # the backend refused the release before any request to the Bot
    assert [m["message_type"] for m in backend.sent] == ["accepted"]


async def test_without_a_planner_model_a_staffed_ticket_is_still_handed_to_management(rig):
    start, _ = rig
    backend = FakeBackend(message())
    backend.specialists = [TECHNICAL]
    runtime = start(backend)
    await runtime.round()
    assert session(runtime)["pause_reason"] == "planner:planner_model_not_configured" and backend.members == {}


async def test_a_specialist_looks_something_up_with_a_granted_tool_before_it_answers(staffed):
    backend = FakeBackend(message())
    backend.tool_descriptors = [OUTAGE_TOOL]
    providers = Providers(tool_call=("technical__get_active_outage", {"building_id": "building"}))
    runtime = staffed(backend, providers)
    await runtime.round()
    # The tool host is asked under the backend's run of this turn, not under an id the runtime made up,
    # and by the tool's catalogue name rather than the name the model was given.
    assert providers.tool_calls == [{"run_id": "run-turn-1", "tool": "technical.get_active_outage",
                                     "arguments": {"building_id": "building"}}]
    first, second = providers.bot
    assert first["tools"] == [OUTAGE_TOOL] and second["runId"] != first["runId"]
    # What the Bot said before calling the tool goes back as it was written, and the tool's answer follows.
    assistant, result = second["messages"][-2:]
    assert assistant["content"] == "Tôi kiểm tra sự cố đang diễn ra." and assistant["toolCalls"][0]["id"] == "call-1"
    assert json.loads(result["content"])["result"]["data"] == {"outages": [OUTAGE]}
    assert [m["content"] for m in backend.mirrors[-1]["messages"]] == [ANALYSIS]
    assert session(runtime)["phase"] == "waiting_management"


async def test_a_tool_host_that_does_not_answer_is_told_to_the_agent_not_held_as_unknown(staffed):
    backend = FakeBackend(message())
    backend.tool_descriptors = [OUTAGE_TOOL]
    providers = Providers(tool_call=("technical__get_active_outage", {"building_id": "building"}), tools_down=True)
    runtime = staffed(backend, providers)
    await runtime.round()
    told = json.loads(providers.bot[1]["messages"][-1]["content"])["result"]
    assert told["status"] == "INTERNAL_ERROR" and told["errors"][0]["code"] == "TOOL_UNAVAILABLE"
    state = session(runtime)
    assert (state["phase"], state["action_in_flight"]) == ("waiting_management", None)


async def test_a_tool_the_version_was_not_granted_is_a_failed_turn(staffed):
    backend, providers = FakeBackend(message()), Providers(tool_call=("technical__get_active_outage", {"building_id": "b"}))
    runtime = staffed(backend, providers)  # no tool descriptor: this version has no tool
    await runtime.round()
    assert providers.tool_calls == []
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("paused", "AGENT_FAILURE", None)


async def test_management_asks_the_agent_a_follow_up_inside_the_session(staffed):
    backend, providers = FakeBackend(message()), Providers(ANALYSIS, "Không cần khóa van tổng; khóa van góc dưới chậu là đủ.")
    runtime = staffed(backend, providers)
    await runtime.round()
    assert session(runtime)["phase"] == "waiting_management"

    backend.questions = [{"message_id": "question-1", "team_id": "team-1", "agent_id": "technical",
                          "agent_version_id": "technical-v1", "text": "Có cần khóa van tổng không?"}]
    backend.lose_outcome = True
    await runtime.round()
    # The agent answered, but the report of it did not reach the backend: nothing is marked yet.
    assert len(providers.bot) == 2 and backend.answered == []
    runtime.store.clock.now += 20
    await runtime.round()
    # One more turn of the same agent in the same room, under a run of its own; the Supervisor's
    # session is not resumed and no planner decision is spent on it.
    assert providers.decisions == ["tasks", "run", "complete_task", "plan"] and len(providers.bot) == 2
    asked = json.loads(providers.bot[1]["messages"][0]["content"])
    assert asked["instruction"] == "Có cần khóa van tổng không?"
    assert ANALYSIS in json.dumps(asked["messages"], ensure_ascii=False)  # it sees what it said before
    # Tried again: the outcome that was kept is reported, and the agent is not asked a second time.
    assert len(providers.bot) == 2 and backend.answered == [("question-1", "done", "run-turn-2")]
    assert [m["content"] for m in backend.mirrors[-1]["messages"]] == [
        ANALYSIS, "Không cần khóa van tổng; khóa van góc dưới chậu là đủ."]
    assert backend.mirrors[-1]["runs"] == [{"run_id": "run-turn-2", "status": "succeeded"}]
    assert not await runtime.work()


async def test_a_photo_on_a_question_in_a_session_reaches_the_bot_as_a_picture_for_that_turn_only(staffed):
    backend, providers = FakeBackend(message()), Providers(ANALYSIS, "Vết rò ở chân vòi.", "Không cần thay vòi.")
    runtime = staffed(backend, providers)
    await runtime.round()
    backend.questions = [{"message_id": "question-1", "team_id": "team-1", "agent_id": "technical", "agent_version_id": "technical-v1",
                          "text": "Ảnh này rò ở đâu?", "images": [{"name": "vet-ro.png", "mimeType": "image/png", "data": "aGVsbG8="}]}]
    await runtime.round()
    shown = providers.bot[1]["messages"][0]["content"]
    # The adapter's text, unchanged, then the photo as the part the Bot turns into a picture for the model.
    assert [part["type"] for part in shown] == ["text", "image"] and json.loads(shown[0]["text"])["instruction"] == "Ảnh này rò ở đâu?"
    assert shown[1] == {"type": "image", "source": {"type": "data", "value": "aGVsbG8=", "mimeType": "image/png"}}
    assert backend.answered == [("question-1", "done", "run-turn-2")]
    # Nothing is kept after the turn: the next question, with no photo, is one string again.
    assert runtime.releases.attached == {} and runtime.releases.pictures == {}
    backend.questions = [{"message_id": "question-2", "team_id": "team-1", "agent_id": "technical", "agent_version_id": "technical-v1",
                          "text": "Có cần thay vòi không?"}]
    await runtime.round()
    assert isinstance(providers.bot[2]["messages"][0]["content"], str)


async def test_a_question_for_a_session_without_a_room_is_reported_as_failed(staffed):
    backend, providers = FakeBackend(message()), Providers()
    runtime = staffed(backend, providers)
    backend.specialists = []  # nobody was offered, so the Supervisor never opened a room
    await runtime.round()
    backend.questions = [{"message_id": "question-1", "team_id": "team-1", "agent_id": "technical",
                          "agent_version_id": "technical-v1", "text": "Còn rò không?"}]
    await runtime.round()
    assert providers.bot == [] and backend.answered == [("question-1", "failed", None)]
