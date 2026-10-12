"""Partner tools end to end on the real engine and the scripted model (slice T1): what each outcome of a tool does
to the operation row, the evidence, the workflow and the words the model is told. Scripted model, a real MCP server."""
from __future__ import annotations

import json
import logging
import re

import pytest
import t1kit
from enginekit import evidence_of, world
from fake_llm import CALLS, MODE
from partnerkit import SECRET, Partner
from scripts import TICKET, say
from t1kit import SETTINGS, TOOLS, act, configure, event_types, ops, tool_texts


def texts(body: dict) -> list[str]:
    return [m["text"] for m in body["result"]["messages"]]


def everything_the_model_saw() -> str:
    return json.dumps([c.get("shape") for c in CALLS], ensure_ascii=False)


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def test_contract_13_4_a_pending_action_waits_for_the_partner_and_a_replayed_post_calls_it_once(tmp_path, partner):
    script = act("partner_repair", {"slot": "mon"}, "I asked for a plumber for Monday; it is pending.")
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert (first["request_status"], first["workflow_state"], first["next_action"]) == (
            "completed", "waiting_external_event", "watch_events")
        assert texts(first) == ["I asked for a plumber for Monday; it is pending."]
        assert first["ticket_id"].startswith("tkt_")  # the first action made the ticket (A5)
        [op] = ops(w)
        assert (op["status"], op["partner_status"], op["job"], op["tool"]) == ("pending", "pending", "JOB-1", "partner_repair")
        [call] = partner.calls  # the reference was put into the partner's own argument
        assert call["args"]["client_reference"] == op["reference"] and call["auth"] == f"Bearer {SECRET}"
        shown = [x for x in tool_texts() if x.startswith("PENDING:")]
        assert shown and "JOB-1" in shown[0] and "do not say it is done" in shown[0] and "[evidence E" in shown[0]
        kinds = event_types(w, first["conversation_id"])
        assert kinds.index("ticket.created") < kinds.index("operation.status_changed") < kinds.index("assistant.message")
        events = w.flow.history(first["conversation_id"], limit=500).json()["items"]
        [made] = [e for e in events if e["event_type"] == "ticket.created"]
        assert made["ticket_id"] == first["ticket_id"] and made["payload"]["ticket_id"] == first["ticket_id"]
        [changed] = [e for e in events if e["event_type"] == "operation.status_changed"]
        assert changed["payload"] == {"operation_id": op["id"], "status": "pending", "tool": "partner_repair",
                                      "client_reference": op["reference"], "external_job_id": "JOB-1"}
        assert changed["ticket_id"] == first["ticket_id"]
        assert events[-1]["payload"]["state"] == "waiting_external_event" and events[-1]["payload"]["revision"] == first["workflow_revision"]
        # the response is lost; the partner's backend sends the same POST again (contract 13.9, first row)
        again = w.flow.post(start)
        assert again.status_code == 200 and again.json() == first
        assert len(partner.calls) == 1 and len(partner.effects) == 1 and len(ops(w)) == 1


def test_contract_13_2_a_booking_confirmed_at_once_needs_no_tracking(tmp_path, partner):
    script = act("partner_hotel", {"hotel": "Sunrise", "nights": 2}, "Your hotel is in place. Please check the details.")
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_confirmation", "confirm_close")
        [op] = ops(w)
        assert (op["status"], op["partner_status"]) == ("completed", "confirmed")
        kinds = event_types(w, first["conversation_id"])
        assert "ticket.created" in kinds and kinds.count("operation.status_changed") == 1
        states = [e["payload"]["state"] for e in w.flow.history(first["conversation_id"], limit=500).json()["items"]
                  if e["event_type"] == "workflow.status_changed"]
        assert "waiting_external_event" not in states  # no event channel and no timer for a confirmed booking
        assert w.sql("select count(*) from wf_jobs where kind='provider_wake'") == [(0,)]
        assert partner.of("book_hotel")[0]["args"]["client_reference"] == op["reference"]
        shown = [x for x in tool_texts() if "booking_id" in x]
        assert shown and not shown[0].startswith("PENDING")
        c = w.flow.close({"workflow_id": first["workflow_id"], "workflow_revision": first["workflow_revision"]}, start)[0]
        assert c.status_code == 200 and c.json()["state"] == "closed"


def test_only_what_the_partner_confirmed_may_be_called_done_to_the_resident(tmp_path, partner):
    """The guard lets the leader say 'booked' on the strength of a result that says so: a confirmed booking carries the
    partner's status word, a pending one does not, and the leader is refused if it claims more than it has."""
    def pending_booked(c):
        turn = c.after_user()
        if turn.called("partner_repair") == 0:
            return [("partner_repair", {"slot": "mon"})]
        ev = evidence_of(" ".join(turn.results("partner_repair")))
        said = turn.called("CaseSay")
        if said == 0:
            return say("The visit has been booked.", "none", ev[:1])
        if said == 1 and turn.results("CaseSay")[0].startswith("Not sent"):
            return say("The visit is pending.", "none", ev[:1])
        return "Said."

    with world(tmp_path, pending_booked, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert texts(first) == ["The visit is pending."]
        assert any(x.startswith("Not sent") for x in tool_texts())  # the claim was refused before the resident saw it
    (tmp_path / "b").mkdir()
    with world(tmp_path / "b", act("partner_hotel", {"hotel": "Sunrise", "nights": 2}, "Your hotel has been booked."),
               **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert texts(first) == ["Your hotel has been booked."]
        assert any("<platform-verified>" in x and "status: confirmed" in x for x in tool_texts())


def test_a_lookup_is_synchronous_evidence_and_makes_no_operation_and_no_ticket(tmp_path, partner):
    def script(c):
        turn = c.after_user()
        if turn.called("partner_lookup") == 0:
            return [("partner_lookup", {"ticket_id": "T-1001"})]
        ev = evidence_of(" ".join(turn.results("partner_lookup")))
        if turn.called("CaseFinalize") == 0:
            return [("CaseFinalize", {"answer": TICKET, "outcome": "resolved", "cites": ev[:1]})]
        return "Done."
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"], first["ticket_id"]) == ("closed", "none", None)
        assert ops(w) == [] and "ticket.created" not in event_types(w, first["conversation_id"])
        assert partner.of("lookup_ticket")[0]["args"] == {"ticket_id": "T-1001"}


def test_a_refused_action_is_failed_without_evidence_and_the_resident_is_told_only_that(tmp_path, partner):
    script = act("partner_reject", {}, "The partner could not take the request. Shall I try another way?", "reply", cite=False)
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        assert (first["workflow_state"], first["next_action"]) == ("awaiting_user", "submit_reply")
        [op] = ops(w)
        assert (op["status"], op["partner_status"]) == ("failed", "rejected")
        shown = [x for x in tool_texts() if x.startswith("FAILED:")]
        assert shown and "no technician available" in shown[0] and "[evidence" not in shown[0]
        assert w.sql("select count(*) from awp_case_items where kind='evidence' and author!='resident'") == [(0,)]
        assert "operation.status_changed" in event_types(w, first["conversation_id"])


def test_what_the_partner_says_when_it_breaks_is_reduced_before_the_model_reads_it(tmp_path, partner):
    script = act("partner_broken", {}, "The partner had a problem; nothing was done.", "reply", cite=False)
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        w.flow.begin()
        [op] = ops(w)
        assert op["status"] == "failed"
        shown = [x for x in tool_texts() if x.startswith("FAILED:")]
        assert shown and "ledger locked" in shown[0]
        for leak in ("/srv/partner", "10.1.2.3", SECRET, "db.py"):
            assert leak not in shown[0] and leak not in everything_the_model_saw()
        [call] = partner.calls
        assert call["tool"] == "broken_action"  # it did reach the partner; only its words are reduced


def test_an_answer_in_structured_content_only_is_read_and_is_evidence(tmp_path, partner):
    script = act("partner_structured", {"ref": "r1"}, "The reservation is in place. Is that right?", "confirmation")
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        [op] = ops(w)
        assert (op["status"], op["partner_status"]) == ("completed", "confirmed")
        shown = [x for x in tool_texts() if "B-9" in x]
        assert shown and "[evidence E" in shown[0]
        assert first["workflow_state"] == "awaiting_confirmation"


def test_an_action_that_answers_without_a_status_may_have_happened_so_it_is_unknown(tmp_path, partner):
    script = act("partner_nostatus", {"thing": "x"}, "I could not confirm that; a person will check.", "none", cite=False)
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        [op] = ops(w)
        assert op["status"] == "unknown"
        assert first["workflow_state"] == "needs_attention" and first["next_action"] == "resolve_attention"


def test_a_timeout_is_unknown_never_failed_and_the_workflow_needs_a_person(tmp_path, partner):
    partner.delay = 6
    script = act("partner_slow", {"seconds": 6}, "I could not confirm that the request went through; a person will check.",
                 "none", cite=False)
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        [op] = ops(w)
        assert op["status"] == "unknown"  # written by the tool itself, before its answer reached the model
        shown = [x for x in tool_texts() if x.startswith("UNKNOWN:")]
        assert shown and "Do not retry" in shown[0] and "[evidence" not in shown[0]
        assert (first["workflow_state"], first["next_action"]) == ("needs_attention", "resolve_attention")
        assert w.sql("select attention_reason from wf_workflows") == [("operation_unknown",)]
        events = w.flow.history(first["conversation_id"], limit=500).json()["items"]
        [attention] = [e for e in events if e["event_type"] == "workflow.needs_attention"]
        assert attention["payload"]["reason"] == "operation_unknown"
        assert [e["payload"]["status"] for e in events if e["event_type"] == "operation.status_changed"] == ["unknown"]
        assert len(partner.of("slow_action")) == 1 and partner.effects == ["slow"]
        assert "running in background" not in everything_the_model_saw()  # the tool never became a background task


def test_an_unknown_operation_with_a_status_query_is_asked_about_and_the_leader_is_woken(tmp_path, partner):
    partner.delay = 6
    tools = [t1kit.lookup(), t1kit.action("partner_repair_q", "book_repair", tracking="status_query",
                                          status_tool="repair_status", call_timeout=1.5)]

    def script(c):
        if "<provider-event" in c.last_user:
            if c.after_user().called("CaseSay") == 0:
                return say("Your repair visit is finished. Is everything right?", "confirmation",
                           [re.search(r'evidence="(E\d+)"', c.last_user).group(1)])
            return "Said."
        return act("partner_repair_q", {"slot": "tue"}, "I could not confirm the request yet; I will keep checking.", "none", cite=False)(c)

    with world(tmp_path, script, **TOOLS, **SETTINGS, wf_status_poll_seconds=0.5, wf_op_grace_seconds=0.5) as w:
        configure(w, partner, tools)
        start, first = w.flow.begin()
        [op] = ops(w)
        assert op["status"] == "unknown" and first["workflow_state"] == "waiting_external_event"  # a status query can settle it
        partner.status_of[op["reference"]] = "completed"
        w.wait_state(first["workflow_id"], "awaiting_confirmation", timeout=30)
        [op] = ops(w)
        assert (op["status"], op["partner_status"]) == ("completed", "completed")
        assert w.messages(first["workflow_id"])[-1][1] == "Your repair visit is finished. Is everything right?"
        assert len(partner.of("book_repair")) == 1 and partner.of("repair_status")  # asked, never sent again
        kinds = event_types(w, first["conversation_id"])
        assert kinds.count("operation.status_changed") == 2  # unknown, then completed


def test_only_the_tools_a_route_declares_exist_and_a_lookup_must_be_read_only(tmp_path, partner, caplog):
    declared = [t1kit.lookup(), t1kit.lookup("partner_nohint", "lookup_no_hint", read_only=False),
                t1kit.action("partner_hotel", "book_hotel", tracking="none")]

    def script(c):
        turn = c.after_user()
        if turn.called("partner_repair") == 0:
            return [("partner_repair", {"slot": "mon"})]
        return say("Noted.", "none") if turn.called("CaseSay") == 0 else "Said."

    with caplog.at_level(logging.WARNING, logger="awp.workforce"):
        with world(tmp_path, script, leader_tools=t1kit.NAMES + ["partner_nohint"], **SETTINGS) as w:
            configure(w, partner, declared)
            w.flow.begin()
            offered = set(CALLS[0]["tools"])
            assert {"partner_lookup", "partner_hotel"} <= offered
            assert not offered & {"partner_repair", "partner_nohint", "book_repair", "broken_action", "book_hotel", "lookup_ticket_x"}
            assert any("must be read only" in r.message and "partner_nohint" in r.message for r in caplog.records)
            assert any("ToolNotFoundError" in x for x in tool_texts())  # asking for one that is not declared
            assert partner.calls == []


def lead_with_tech(c):
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "team", "description": "check"})]
    if c.called("AgentCreate") == 0:
        return [("AgentCreate", {"name": "tech", "description": "checks", "subagent_type": "tech", "prompt": "Look up T-1."})]
    facts = re.findall(r"\b(F\d+) tech:", c.blob)
    if facts and not c.after_user().called("CaseSay"):
        return say("Ticket T-1 was looked up.", "reply", facts[:1])
    return "Waiting."


def tech_looks_up(seen: dict):
    def script(c):
        seen.setdefault("offered", c.names)
        if c.called("partner_lookup") == 0:
            return [("partner_lookup", {"ticket_id": "T-1"})]
        ev = evidence_of(" ".join(c.results("partner_lookup")))
        if ev and c.called("CaseFact") == 0:
            return [("CaseFact", {"text": "Ticket T-1 is waiting for the plumber", "evidence": ev[:1]})]
        if c.called("TeamSay") == 0:
            return [("TeamSay", {"content": "Looked it up." if ev else "I could not look it up.", "to": None})]
        seen["result"] = c.results("partner_lookup")
        return "Reported."
    return script


def test_a_specialist_has_a_partner_tool_only_when_its_own_profile_lists_it(tmp_path, partner):
    (tmp_path / "with").mkdir()
    (tmp_path / "without").mkdir()
    seen: dict = {}
    with world(tmp_path / "with", lead_with_tech, leader_tools=[], worker_tools=["partner_lookup"], **SETTINGS) as w:
        configure(w, partner)
        MODE["worker"] = tech_looks_up(seen)
        start, first = w.flow.begin()
        assert first["workflow_state"] == "awaiting_user", w.sql("select attention_reason from wf_workflows")
        assert "partner_lookup" in seen["offered"] and "[evidence E" in seen["result"][0]
        assert len(partner.of("lookup_ticket")) == 1
        assert not any("partner_lookup" in n for n in CALLS[0]["tools"])  # the leader's profile does not list it
    partner.calls.clear()
    seen.clear()
    with world(tmp_path / "without", lead_with_tech, leader_tools=[], worker_tools=[], **SETTINGS) as w:
        configure(w, partner)
        MODE["worker"] = tech_looks_up(seen)
        w.flow.begin()
        assert "partner_lookup" not in seen["offered"]
        assert "ToolNotFoundError" in seen["result"][0] or "not available to you" in seen["result"][0]
        assert partner.calls == []  # a tool the profile does not grant never runs, for anyone


def test_a_leader_whose_profile_does_not_list_a_partner_tool_cannot_call_it(tmp_path, partner):
    def leader(c):
        turn = c.after_user()
        if turn.called("partner_hotel") == 0:
            return [("partner_hotel", {"hotel": "Sunrise", "nights": 1})]
        return say("Noted.", "none") if turn.called("CaseSay") == 0 else "Said."
    with world(tmp_path, leader, leader_tools=["partner_lookup"], **SETTINGS) as w:
        configure(w, partner)
        w.flow.begin()
        assert "partner_lookup" in CALLS[0]["tools"] and "partner_hotel" not in CALLS[0]["tools"]
        assert any("ToolNotFoundError" in x or "not available to you" in x for x in tool_texts())
        assert partner.calls == [] and ops(w) == []


def test_the_tool_list_is_read_from_the_partner_once_for_all_agents_and_turns(tmp_path, partner):
    script = act("partner_hotel", {"hotel": "Sunrise", "nights": 1}, "Your hotel is in place.", "none")
    with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        start, first = w.flow.begin()
        w.flow.reply(start, first)
        w.quiet()
        assert len(CALLS) >= 3  # several model steps in several turns, each assembling its agent again
        assert partner.lists == 1


def test_two_routes_never_see_each_others_tools(tmp_path, partner):
    def script(c):
        turn = c.after_user()
        return say("Noted.", "none") if turn.called("CaseSay") == 0 else "Said."
    with world(tmp_path, script, leader_tools=t1kit.NAMES + ["other_lookup"], **SETTINGS) as w:
        configure(w, partner, [t1kit.lookup(), t1kit.action("partner_hotel", "book_hotel", tracking="none")])
        other = w.env.active_route(w.flow.client["client_id"], w.flow.key["api_key"], ref="OTHER-REF")
        configure(w, partner, [t1kit.lookup("other_lookup")], route_id=other["route_id"])
        w.flow.begin()
        w.flow.begin(external_management_ref="OTHER-REF")
        mine, theirs = CALLS[0]["tools"], CALLS[-1]["tools"]
        assert {"partner_lookup", "partner_hotel"} <= set(mine) and "other_lookup" not in mine
        assert "other_lookup" in theirs and not {"partner_lookup", "partner_hotel"} & set(theirs)


def test_nothing_secret_reaches_a_log_a_response_an_event_or_the_database(tmp_path, partner, caplog):
    script = act("partner_broken", {}, "The partner had a problem; nothing was done.", "reply", cite=False)
    # Libraries log at DEBUG what the partner sends back, and this partner echoes our header on purpose, so the
    # libraries are listened to at INFO (what a deployment runs); our own code at DEBUG.
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="awp")
    if True:
        with world(tmp_path, script, **TOOLS, **SETTINGS) as w:
            rid = configure(w, partner)
            start, first = w.flow.begin()
            conv = first["conversation_id"]
            views = [w.env.http.get(f"/platform/v1/wf/routes/{rid}/{x}", headers=t1kit.ADM).text for x in ("mcp", "tools")]
            views.append(w.env.http.get("/platform/v1/wf/operations", headers=t1kit.ADM).text)
            views.append(w.env.http.get(f"/platform/v1/wf/workflows/{first['workflow_id']}", headers=t1kit.ADM).text)
            views.append(json.dumps(first))
            views.append(json.dumps(w.flow.history(conv, limit=500).json()))
            views.append(json.dumps(w.flow.snapshot(conv).json()))
            views.append(w.env.dump())
            views.append(everything_the_model_saw())
            views.append(caplog.text)
    assert caplog.text, "the log was captured"
    for text in views:
        assert SECRET not in text
    # the header exists for the partner, sealed in our database
    assert partner.calls[0]["auth"] == f"Bearer {SECRET}"
