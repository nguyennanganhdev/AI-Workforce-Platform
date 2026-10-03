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
        return {"context": self.context(team_id), "ticket_version": "1", "supervisor_version_id": "supervisor-v1",
                "specialists": self.specialists}

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


def decide(prompt):
    """A planner that follows the Supervisor's guide: give a task, run it, accept its answer."""
    state, catalog = prompt["state"], prompt["catalog"]
    room, agent = state["room"], next(iter(catalog))
    if not room["tasks"]:
        return {"kind": "tasks", "tasks": [{"task_id": "t1", "description": "Xác định nguyên nhân rò nước",
                                            "assignee_agent_version_id": agent}]}
    replies = [m["message_id"] for r in state["terminal_results"].values() if r["turn_status"] == "success"
               for m in r["messages"] if m["task_id"] == "t1" and m["sender"] == r["speaker_agent_version_id"]]
    if replies:
        return {"kind": "complete_task", "task_id": "t1", "result_refs": replies, "assessment": "Đủ căn cứ."}
    return {"kind": "run", "task_id": "t1", "agent_version_id": agent,
            "instruction": "Phân tích nguyên nhân và nêu việc cần làm."}


class Providers:
    """The model provider and the OpenBot, as one HTTP transport that records what it was asked."""

    def __init__(self, *replies, tool_call=None, tools_down=False):
        # What the Bot answers, turn by turn; the last answer repeats.
        self.replies = list(replies) or [ANALYSIS]
        self.decisions, self.bot = [], []
        # A Bot that asks for this tool before it answers, and the tool host it reaches.
        self.tool_call, self.tools_down, self.tool_calls = tool_call, tools_down, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/chat/completions":
            assert request.headers["authorization"] == "Bearer model-key" and body["max_completion_tokens"] > 0
            decision = decide(json.loads(body["messages"][1]["content"]))
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
    # Opening the room and stopping when every task is done need no model: the rules leave no choice.
    assert providers.decisions == ["tasks", "run", "complete_task"]
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
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("paused", "planner:analysis_ready", None)
    assert backend.reports[-1] == ("team-1", "paused", "planner:analysis_ready")
    assert not await runtime.work()


async def test_an_empty_reply_is_a_failed_turn_and_the_task_is_run_again(staffed):
    backend, providers = FakeBackend(message()), Providers("  ", ANALYSIS)
    runtime = staffed(backend, providers)
    await runtime.round()
    # The first turn failed for certain: the room was free again and the Supervisor ran the task once more.
    mirror = backend.mirrors[-1]
    assert mirror["runs"] == [{"run_id": "run-turn-1", "status": "failed"}, {"run_id": "run-turn-2", "status": "succeeded"}]
    assert [m["content"] for m in mirror["messages"]] == [ANALYSIS]
    assert session(runtime)["pause_reason"] == "planner:analysis_ready"


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
    # The tool host is asked under the backend's run of this turn, not under an id the runtime made up.
    assert providers.tool_calls == [{"run_id": "run-turn-1", "tool": "technical__get_active_outage",
                                     "arguments": {"building_id": "building"}}]
    first, second = providers.bot
    assert first["tools"] == [OUTAGE_TOOL] and second["runId"] != first["runId"]
    # What the Bot said before calling the tool goes back as it was written, and the tool's answer follows.
    assistant, result = second["messages"][-2:]
    assert assistant["content"] == "Tôi kiểm tra sự cố đang diễn ra." and assistant["toolCalls"][0]["id"] == "call-1"
    assert json.loads(result["content"])["result"]["data"] == {"outages": [OUTAGE]}
    assert [m["content"] for m in backend.mirrors[-1]["messages"]] == [ANALYSIS]
    assert session(runtime)["pause_reason"] == "planner:analysis_ready"


async def test_a_tool_host_that_does_not_answer_is_told_to_the_agent_not_held_as_unknown(staffed):
    backend = FakeBackend(message())
    backend.tool_descriptors = [OUTAGE_TOOL]
    providers = Providers(tool_call=("technical__get_active_outage", {"building_id": "building"}), tools_down=True)
    runtime = staffed(backend, providers)
    await runtime.round()
    told = json.loads(providers.bot[1]["messages"][-1]["content"])["result"]
    assert told["status"] == "INTERNAL_ERROR" and told["errors"][0]["code"] == "TOOL_UNAVAILABLE"
    state = session(runtime)
    assert (state["pause_reason"], state["action_in_flight"]) == ("planner:analysis_ready", None)


async def test_a_tool_the_version_was_not_granted_is_a_failed_turn(staffed):
    backend, providers = FakeBackend(message()), Providers(tool_call=("technical__get_active_outage", {"building_id": "b"}))
    runtime = staffed(backend, providers)  # no tool descriptor: this version has no tool
    await runtime.round()
    assert providers.tool_calls == []
    state = session(runtime)
    assert (state["phase"], state["pause_reason"], state["action_in_flight"]) == ("paused", "AGENT_FAILURE", None)
