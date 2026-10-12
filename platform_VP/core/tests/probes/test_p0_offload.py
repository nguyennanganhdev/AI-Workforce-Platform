"""P0 probe (spec A8): AgentScope ToolOffloadMiddleware against a partner-style ToolBase tool.

Real runs through agentscope.app.create_app (ChatService, WakeupDispatcher, InboxMiddleware and the
offload middleware as ChatService installs it) with a scripted OpenAI-compatible model. Nothing from awp.
Tests marked `slow` take 5-16 s each; deselect with  -m "not slow".
"""
import asyncio

import pytest

from p0_offload_stack import (LEDGER, SCRIPT, OrderRecorder, PartnerBook, PartnerBookCapped,
                              PartnerBookNoOffload, PartnerBookPreWork, PartnerBookStateInjected, ProbeExtra,
                              agent_cls_with, make_stack)

pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnknownMarkWarning")
BG = "running in background"


def tool_results(i: int) -> list[str]:
    return SCRIPT.requests[i]["tool_results"]


def all_text() -> str:
    return " ".join(r["non_system_text"] for r in SCRIPT.requests)


# ------------------------------------------------------------------ (1) 3 s: not offloaded
def test_3s_tool_is_not_offloaded(tmp_path):
    with make_stack(tmp_path) as st:
        SCRIPT.book(3, "3s")
        st.chat()
        t = st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "second model call")
        st.wait(lambda: not st.is_running(), 10, "run to end")
        assert 3.0 <= t < 6.0, t                       # the model waited for the real tool
        assert tool_results(1) == ["BOOKED ref=BK-3s"]  # the real result, verbatim
        assert BG not in all_text()
        assert st.bg_tasks() == []
        assert len(SCRIPT.requests) == 2                # no later wake-up run
        assert LEDGER.at("side_effect_done", "3s") is not None


# ------------------------------------------------------------------ (2) 12 s: offloaded
@pytest.mark.slow
def test_12s_tool_is_offloaded_and_result_comes_back_as_hint(tmp_path):
    with make_stack(tmp_path) as st:
        SCRIPT.book(12, "12s")
        st.chat()
        t_placeholder = st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "placeholder reaching the model")
        # what the model got in place of the result
        placeholder = tool_results(1)[0]
        print("\nPLACEHOLDER at %.2fs:\n%s" % (t_placeholder, placeholder))
        assert 9.5 <= t_placeholder < 11.5, t_placeholder
        assert "partner_book" in placeholder and BG in placeholder and "for over 10.0s" in placeholder
        assert "BOOKED" not in placeholder                   # the real result is NOT in the tool result
        assert "DO NOT" in placeholder and "will be notified automatically" in placeholder
        assert len(st.bg_tasks()) == 1 and st.bg_tasks()[0].tool_name == "partner_book"
        assert LEDGER.at("side_effect_done", "12s") is None  # still running at this point

        # the real result arrives as an inbox hint that wakes the session
        t_hint = st.wait(lambda: len(SCRIPT.requests) >= 3, 20, "hint reaching the model")
        st.wait(lambda: not st.is_running(), 10, "run to end")
        req = SCRIPT.requests[2]
        print("HINT request at %.2fs, roles=%s, last_role=%s\nTEXT=%s" % (
            t_hint, req["roles"], req["last_role"], req["non_system_text"][-420:]))
        assert 11.5 <= t_hint < 15.0, t_hint
        assert "Result:" in req["non_system_text"] and "BOOKED ref=BK-12s" in req["non_system_text"]
        assert "has completed" in req["non_system_text"]
        assert req["last_role"] != "tool"                   # it is a user-side message, not a tool result
        assert LEDGER.at("side_effect_done", "12s") is not None
        assert LEDGER.at("side_effect_done", "12s") <= t_hint + 0.2
        assert st.bg_tasks() == []                           # unregistered when done

        # what the stored history says: the tool result is the placeholder, the real value is in the hint
        stored = str(st.messages())
        assert BG in stored and "BOOKED ref=BK-12s" in stored


# ------------------------------------------------------------------ (2b) what is lost when things are cancelled
@pytest.mark.slow
def test_cancel_run_before_offload_orphans_the_tool(tmp_path):
    """Interrupt the run while the tool is still inside its first 10 s: the tool is not cancelled."""
    with make_stack(tmp_path) as st:
        SCRIPT.book(6, "orph")
        st.chat()
        st.wait(lambda: LEDGER.at("start", "orph") is not None, 10, "tool start")
        st.wait(lambda: st.now() > 2.0, 5)
        st.interrupt()
        st.wait(lambda: not st.is_running(), 10, "run to stop")
        n_req = len(SCRIPT.requests)
        st.wait(lambda: LEDGER.at("side_effect_done", "orph") is not None or LEDGER.at("cancelled", "orph"), 12,
                "tool to end")
        print("\nORPHAN ledger:", LEDGER.events, "bg:", st.bg_tasks())
        assert LEDGER.at("cancelled", "orph") is None                # nobody cancelled the tool
        assert LEDGER.at("side_effect_done", "orph") is not None     # the side effect happened anyway
        assert len(SCRIPT.requests) == n_req == 1                    # and the model never saw the result
        assert BG not in all_text() and "BOOKED" not in str(st.messages())
        assert st.bg_tasks() == []                                   # never registered: not stoppable by ToolStop


@pytest.mark.slow
def test_cancel_run_after_offload_keeps_bg_task_and_result_still_arrives(tmp_path):
    """Interrupt the run (busy with a second tool) after the first tool was offloaded."""
    with make_stack(tmp_path, tool_classes=(PartnerBook,)) as st:
        SCRIPT.steps = {0: [("partner_book", {"seconds": 12, "tag": "a"})],
                        1: [("partner_book", {"seconds": 4, "tag": "b"})]}
        st.chat()
        st.wait(lambda: LEDGER.at("start", "b") is not None, 20, "second tool start (after the placeholder)")
        st.wait(lambda: st.now() > 10.8, 5)
        assert len(st.bg_tasks()) == 1
        st.interrupt()                                               # run cancelled while "a" is in the background
        st.wait(lambda: len(SCRIPT.requests) >= 3, 20, "the hint of 'a' to wake the session")
        st.wait(lambda: LEDGER.at("side_effect_done", "b") is not None, 10, "b to finish on its own")
        st.wait(lambda: not st.is_running(), 10)
        print("\nAFTER-OFFLOAD ledger:", LEDGER.events)
        assert LEDGER.at("cancelled", "a") is None
        assert "BOOKED ref=BK-a" in SCRIPT.requests[-1]["non_system_text"]   # a's result still delivered
        assert LEDGER.at("cancelled", "b") is None                   # b (cancelled run, not offloaded) kept running
        assert "BK-b" not in all_text()                              # ... and its result is lost


@pytest.mark.slow
def test_stopping_the_bg_task_delivers_an_interrupted_hint_not_the_result(tmp_path):
    """What ToolStop / session cancel / CancelDispatcher do: cancel_session_tasks. The toolkit turns the
    CancelledError into an INTERRUPTED tool result, and the offload middleware delivers THAT as the hint."""
    with make_stack(tmp_path) as st:
        SCRIPT.book(12, "stop")
        st.chat()
        st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "placeholder")
        st.wait(lambda: not st.is_running(), 10)
        mgr = st.app.state.background_task_manager
        assert st.client.portal.call(mgr.cancel_session_tasks, st.session_id) == 1
        st.wait(lambda: LEDGER.at("cancelled", "stop") is not None, 5, "tool cancelled")
        st.wait(lambda: len(SCRIPT.requests) >= 3, 5, "wake-up with the interrupted hint")
        st.wait(lambda: not st.is_running(), 10)
        hint = SCRIPT.requests[2]["non_system_text"]
        print("\nSTOP hint tail:", hint[-260:])
        assert "interrupted by the user" in hint and "BOOKED" not in hint
        assert LEDGER.at("side_effect_done", "stop") is None   # the tool body never reached its end


@pytest.mark.slow
def test_process_shutdown_cancels_the_bg_task(tmp_path):
    with make_stack(tmp_path) as st:
        SCRIPT.book(30, "down")
        st.chat()
        st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "placeholder")
        assert BG in str(st.messages())                              # history promises "you will be notified"
        assert len(st.bg_tasks()) == 1
        bus = st.app.state.message_bus
        sid = st.session_id
    # leaving the context = lifespan shutdown = "worker restart"
    print("\nSHUTDOWN ledger:", LEDGER.events)
    assert LEDGER.at("cancelled", "down") is not None
    assert LEDGER.at("side_effect_done", "down") is None
    assert len(SCRIPT.requests) == 2                                 # nothing reached the model again
    from agentscope.app.message_bus._keys import MessageBusKeys
    left = bus._queues.get(MessageBusKeys.inbox(sid)) or []
    print("INBOX left in the (in-memory) bus after shutdown:", [str(e[1])[:200] for e in left])


# ------------------------------------------------------------------ (3) ways around it
def test_extra_agent_middlewares_run_inside_the_offload_not_before_it(tmp_path):
    """extra_agent_middlewares cannot take the clock off: they are appended after ToolOffloadMiddleware."""
    async def extras(user_id, agent_id, session_id):
        return [ProbeExtra()]

    with make_stack(tmp_path, custom_agent_cls=OrderRecorder, extra_agent_middlewares=extras) as st:
        SCRIPT.book(1, "ord")
        st.chat()
        st.wait(lambda: len(SCRIPT.requests) >= 2, 20)
        order = OrderRecorder.seen[0]
        print("\nMIDDLEWARE ORDER:", order)
        assert order.index("ToolOffloadMiddleware") < order.index("ProbeExtra")
        assert ProbeExtra.calls == ["partner_book"]


@pytest.mark.slow
def test_state_injected_flag_bypasses_offload(tmp_path):
    """No extension needed: mark the wrapper tool is_state_injected (the guard in the middleware)."""
    with make_stack(tmp_path, tool_classes=(PartnerBookStateInjected,)) as st:
        SCRIPT.book(12, "inj")
        st.chat()
        t = st.wait(lambda: len(SCRIPT.requests) >= 2, 25, "real result")
        st.wait(lambda: not st.is_running(), 10)
        print("\nSTATE-INJECTED: result at %.2fs, seen_state=%s" % (t, PartnerBookStateInjected.seen_state))
        assert t >= 12.0
        assert tool_results(1) == ["BOOKED ref=BK-inj"]
        assert BG not in all_text() and st.bg_tasks() == [] and len(SCRIPT.requests) == 2
        assert PartnerBookStateInjected.seen_state == ["AgentState"]  # the cost: the tool gets the live state


def test_agent_subclass_changes_threshold_and_exempts_a_tool(tmp_path):
    """custom_agent_cls: swap the installed middleware for a policy wrapper. Threshold 1.5 s for the test."""
    with make_stack(tmp_path, tool_classes=(PartnerBook, PartnerBookNoOffload),
                    custom_agent_cls=agent_cls_with(1.5)) as st:
        # (a) the threshold moved: a 3 s ordinary tool is now offloaded, text says 1.5 s
        SCRIPT.book(3, "thr")
        st.chat()
        st.wait(lambda: len(SCRIPT.requests) >= 2, 10, "placeholder")
        assert BG in tool_results(1)[0] and "for over 1.5s" in tool_results(1)[0]
        st.wait(lambda: len(SCRIPT.requests) >= 3, 10, "hint")
        st.wait(lambda: not st.is_running(), 10)

    (tmp_path / "second").mkdir()
    with make_stack(tmp_path / "second", tool_classes=(PartnerBook, PartnerBookNoOffload),
                    custom_agent_cls=agent_cls_with(1.5)) as st:
        # (b) a tool that declares allow_offload=False is not offloaded even beyond the threshold
        SCRIPT.book(3, "exempt", name="partner_book_nooffload")
        st.chat()
        t = st.wait(lambda: len(SCRIPT.requests) >= 2, 10, "real result")
        st.wait(lambda: not st.is_running(), 10)
        assert t >= 3.0 and tool_results(1) == ["BOOKED ref=BK-exempt"]
        assert BG not in all_text() and st.bg_tasks() == [] and len(SCRIPT.requests) == 2


# ------------------------------------------------------------------ (4) decision A8: cap inside the tool
@pytest.mark.slow
def test_own_cap_below_10s_returns_pending_and_is_not_offloaded(tmp_path):
    with make_stack(tmp_path, tool_classes=(PartnerBookCapped,)) as st:
        SCRIPT.book(12, "cap")
        st.chat()
        t = st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "pending result")
        st.wait(lambda: not st.is_running(), 10)
        print("\nCAPPED: model got at %.2fs: %s" % (t, tool_results(1)[0]))
        assert 8.0 <= t < 9.5
        assert tool_results(1)[0].startswith("PENDING")
        assert BG not in all_text() and st.bg_tasks() == [] and len(SCRIPT.requests) == 2
        # the partner call was abandoned by us (cancelled): the side effect is UNKNOWN to us, not "failed"
        assert LEDGER.at("capped", "cap") is not None and LEDGER.at("cancelled", "cap") is not None
        assert LEDGER.at("side_effect_done", "cap") is None


@pytest.mark.slow
def test_cap_that_forgets_preparation_time_still_gets_offloaded(tmp_path):
    """3 s of preparation + an 8 s cap = 11 s of tool time: the 10 s clock wins and the bg task is created."""
    with make_stack(tmp_path, tool_classes=(PartnerBookPreWork,)) as st:
        SCRIPT.book(30, "pre")
        st.chat()
        t = st.wait(lambda: len(SCRIPT.requests) >= 2, 20, "placeholder")
        print("\nPRE-WORK: model got at %.2fs: %s" % (t, tool_results(1)[0][:80]))
        assert 9.5 <= t < 11.0 and BG in tool_results(1)[0]
        t2 = st.wait(lambda: len(SCRIPT.requests) >= 3, 10, "hint carrying the pending text")
        assert "PENDING after cap" in SCRIPT.requests[2]["non_system_text"] and t2 >= 10.9
