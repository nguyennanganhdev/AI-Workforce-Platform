"""CaseSay and the workflow form of CaseFinalize, called directly on a workflow's room (slice S3)."""
from __future__ import annotations

import scripts
from enginekit import world

from agentscope.message import ToolResultState

from awp.protocol.say import CaseSay
from awp.protocol.tools import CaseFinalize
from awp.runtime import Binding

REPLY = {"message": {"type": "text", "text": "Tôi rảnh từ 14 giờ."}}
RULES = {"rules": {"safe_reply": "A person will follow up.",
                   "phrase_rules": [{"phrases": ["fixed"], "unless": ["completed"], "reason": "not done unless a system says so"}]}}


class Room:
    """The leader's tools of one workflow, called by hand."""

    def __init__(self, w, wid: str, role: str = "leader") -> None:
        self.w, self.wid = w, wid
        self.case_id = w.sql("select case_id from wf_workflows where id=?", (wid,))[0][0]
        lead = w.run(lambda: w.rt.cases.sessions_of_case(self.case_id))[0]
        self.b = Binding(self.case_id, lead["session_id"], lead["agent_id"], lead["agent_name"], role, "awp:ta")

    def call(self, tool, **kw):
        chunk = self.w.run(lambda: tool(self.w.rt, self.b).call(**kw))
        return chunk.content[0].text, chunk.state

    def say(self, text, expects="none", cites=None):
        return self.call(CaseSay, text=text, expects=expects, cites=cites or [])

    def sent(self) -> list[tuple]:
        return self.w.sql("select text, expects, outcome from wf_messages where workflow_id=? and sender='assistant' "
                          "order by sequence", (self.wid,))


def ok(result) -> bool:
    return result[1] != ToolResultState.ERROR


def test_say_writes_the_message_with_its_event_and_what_it_expects(tmp_path):
    with world(tmp_path, scripts.interactive, route=RULES) as w:
        _, r = w.flow.begin()
        room = Room(w, r["workflow_id"])
        before = w.sql("select count(*) from wf_events where event_type='assistant.message'")[0][0]
        out = room.say("Anything else I can do?", "reply")
        assert ok(out) and "you expect their reply" in out[0]
        assert room.sent()[-1] == ("Anything else I can do?", "reply", None)
        assert w.sql("select count(*) from wf_events where event_type='assistant.message'")[0][0] == before + 1
        # the message and its event share the sequence, so a reader orders them the same way
        mid = w.sql("select sequence from wf_messages where text='Anything else I can do?'")[0][0]
        assert w.sql("select payload from wf_events where sequence=? and event_type='assistant.message'", (mid,))


def test_say_refuses_what_is_wrong_and_writes_nothing(tmp_path):
    with world(tmp_path, scripts.interactive, route=RULES, wf_text_limit=60) as w:
        start, first = w.flow.begin()
        room = Room(w, first["workflow_id"])
        n = len(room.sent())
        for kw, why in (
                (dict(text="Hello", expects="maybe"), "expects must be one of"),
                (dict(text="   "), "empty"),
                (dict(text="x" * 61), "Too long"),
                (dict(text="See this", cites=["E99"]), "Cannot cite"),
                (dict(text="The fee is 2000000 VND."), "Not sent, the resident has seen nothing"),
                (dict(text="Your pipe is fixed."), "not done unless a system says so")):
            out = room.say(**kw)
            assert not ok(out) and why in out[0], (kw, out)
        assert len(room.sent()) == n


def test_say_accepts_a_figure_the_resident_gave_when_it_is_cited(tmp_path):
    with world(tmp_path, scripts.interactive, route=RULES) as w:
        start, first = w.flow.begin()
        second = w.flow.reply(start, first, **REPLY)[0].json()
        room = Room(w, second["workflow_id"])
        assert not ok(room.say("You said 14."))  # the same words, uncited
        assert ok(room.say("You said 14. Is that right?", "reply", cites=["E2"]))  # E2: what the resident wrote
        # the resident's word is a source for figures, never proof that a system did something
        assert not ok(room.say("Your pipe is fixed.", cites=["E2"]))


def test_say_is_for_the_leader_of_a_workflow_only(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, r = w.flow.begin()
        worker = Room(w, r["workflow_id"], role="worker")
        assert "Only the leader" in worker.say("hi")[0]
        # a case with no workflow has no resident to talk to
        case_id = w.run(lambda: w.rt.cases.create_case(tenant="ta", domain="test", external_ref="OLD-1",
                                                       user_id="awp:ta", meta={}))
        old = Room(w, r["workflow_id"])
        old.b = Binding(case_id, "s", "a", "case-leader", "leader", "awp:ta")
        assert "only inside a workflow" in old.say("hi")[0]


def test_say_is_refused_once_the_workflow_is_closed(tmp_path):
    with world(tmp_path, scripts.lookup) as w:
        _, r = w.flow.begin()  # a look-up: closed by itself
        assert r["workflow_state"] == "closed"
        room = Room(w, r["workflow_id"])
        n = len(room.sent())
        out = room.say("One more thing")
        assert not ok(out) and "closed" in out[0] and len(room.sent()) == n


def test_the_answer_of_finalize_is_a_message_and_the_case_stays_open(tmp_path):
    with world(tmp_path, scripts.interactive, route=RULES) as w:
        start, first = w.flow.begin()
        second = w.flow.reply(start, first, **REPLY)[0].json()
        room = Room(w, second["workflow_id"])
        out = room.call(CaseFinalize, answer="You are free from 14.", outcome="needs_human", cites=["E2"],
                        unknowns=["whether a person can come"])
        assert ok(out) and "do not say it is closed" in out[0]
        assert room.sent()[-1] == ("You are free from 14.", "none", "needs_human")
        assert w.sql("select status from awp_cases where id=?", (room.case_id,)) == [("open",)]  # no case closing
        assert w.sql("select count(*) from awp_case_items where kind='final'") == [(1,)]


def test_finalize_guards_the_answer_and_gives_the_safe_reply_after_three_tries(tmp_path):
    with world(tmp_path, scripts.interactive, route=RULES) as w:
        _, r = w.flow.begin()
        room = Room(w, r["workflow_id"])
        assert "outcome must be one of" in room.call(CaseFinalize, answer="x", outcome="done")[0]
        bad = dict(answer="It costs 2000000 VND.", outcome="resolved", cites=["E1"])
        first = room.call(CaseFinalize, **bad)
        assert not ok(first) and "Not accepted (1/3)" in first[0]
        assert "Not accepted (2/3)" in room.call(CaseFinalize, **bad)[0]
        n = len(room.sent())
        third = room.call(CaseFinalize, **bad)  # the third try: the safe reply goes out instead, needs_human
        assert ok(third) and room.sent()[n:] == [("A person will follow up.", "none", "needs_human")]
        assert "2000000" not in " ".join(m[0] for m in room.sent())
        # the count starts again after a final answer
        assert "Not accepted (1/3)" in room.call(CaseFinalize, **bad)[0]
