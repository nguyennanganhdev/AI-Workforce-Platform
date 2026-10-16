"""The MCP client of a partner tool (slice T1, P0 items 15-20) against a real FastMCP server. No platform, no model."""
from __future__ import annotations

import asyncio

import pytest
from partnerkit import SECRET, Partner, free_port

from awp.workforce import ssrf
from awp.workforce.partner_mcp import PartnerListError, PartnerMCP
from awp.workforce.partner_result import FAILED, OK, PENDING, UNKNOWN, PartnerResult, safe_error


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def client(p: Partner, **kw) -> PartnerMCP:
    return PartnerMCP(p.url, {"Authorization": f"Bearer {SECRET}"}, allow_private=True, **kw)


async def call(p: Partner, tool: str, args: dict, **kw) -> PartnerResult:
    c = client(p)
    try:
        return await c.call(tool, args, **kw)
    finally:
        await c.aclose()


def test_tool_list_is_cached_and_refreshed_only_after_its_time(partner):
    async def go():
        now = [0.0]
        c = PartnerMCP(partner.url, allow_private=True, list_ttl=100, clock=lambda: now[0])
        first = await c.list_tools()
        assert {"lookup_ticket", "book_repair"} <= {s.name for s in first}
        assert next(s for s in first if s.name == "lookup_ticket").read_only is True
        assert next(s for s in first if s.name == "lookup_no_hint").read_only is False  # no hint: not read only
        for _ in range(5):
            await c.list_tools()
        assert partner.lists == 1
        now[0] = 101
        await c.list_tools()
        assert partner.lists == 2
        partner.stop()  # a failing refresh keeps serving the old list
        now[0] = 300
        assert {s.name for s in await c.list_tools()} == {s.name for s in first}
        tried = c.stats["list_calls"]
        for _ in range(3):  # the server is down: the old list is served and it is not asked again at every step
            assert {s.name for s in await c.list_tools()} == {s.name for s in first}
        assert c.stats["list_calls"] == tried
        await c.aclose()
    run(go())


def test_a_strict_listing_fails_when_the_server_is_down_and_leaves_the_old_list_for_everybody_else(partner):
    """A discovery wants the list as it is now or the failure; the agents keep the list they had."""
    async def go():
        c = PartnerMCP(partner.url, allow_private=True)
        first = {s.name for s in await c.list_tools()}
        partner.stop()
        with pytest.raises(PartnerListError):
            await c.list_tools(refresh=True, strict=True)
        assert {s.name for s in await c.list_tools()} == first  # not thrown away by the failed attempt
        assert {s.name for s in await c.list_tools(refresh=True)} == first
        await c.aclose()
    run(go())


def test_no_list_means_an_error_and_no_hammering():
    async def go():
        c = PartnerMCP(f"http://127.0.0.1:{free_port()}/mcp", allow_private=True)
        with pytest.raises(PartnerListError):
            await c.list_tools()
        with pytest.raises(PartnerListError):
            await c.list_tools()
        assert c.stats["list_calls"] == 1  # the second one did not try
        await c.aclose()
    run(go())


def test_a_call_sends_no_hidden_tools_list_and_a_new_session_each_time(partner):
    async def go():
        c = client(partner)
        for i in range(3):
            res = await c.call("lookup_ticket", {"ticket_id": f"T-{i}"}, kind="lookup")
            assert res.outcome == OK and f"T-{i}" in res.text
        assert partner.lists == 0 and partner.rpc.count("tools/call") == 3
        assert partner.rpc.count("initialize") == 3 and c.stats["sessions_opened"] == 3
        await c.aclose()
    run(go())


def test_outcomes_ok_pending_failed_unknown(partner):
    ref = {"client_reference": "cr-1"}
    res = run(call(partner, "book_hotel", {"hotel": "H", "nights": 2, **ref}, kind="action", tracking="events"))
    assert (res.outcome, res.status, res.sent) == (OK, "confirmed", True)
    res = run(call(partner, "book_repair", {"slot": "mon", "client_reference": "cr-2"}, kind="action", tracking="events"))
    assert (res.outcome, res.status, res.external_job_id) == (PENDING, "pending", "JOB-2")
    # tracking none: nobody will follow a pending job, and it is not done either: unknown, for a person to follow
    res = run(call(partner, "book_repair", {"slot": "mon", "client_reference": "cr-3"}, kind="action", tracking="none"))
    assert (res.outcome, res.status, res.error, res.external_job_id) == (UNKNOWN, "pending", "untracked", "JOB-3")
    res = run(call(partner, "rejecting_action", ref, kind="action"))
    assert (res.outcome, res.status) == (FAILED, "rejected")
    # an action whose answer has no readable status may have happened: unknown, not ok
    res = run(call(partner, "no_status_action", {"thing": "x", **ref}, kind="action"))
    assert res.outcome == UNKNOWN and res.error == "protocol"
    # a look-up has no status word: its text is the answer
    assert run(call(partner, "lookup_ticket", {"ticket_id": "T"}, kind="lookup")).outcome == OK


def test_structured_content_is_merged_into_the_text(partner):
    res = run(call(partner, "structured_only", {"ref": "r1", "client_reference": "c"}, kind="action"))
    assert res.outcome == OK and '"booking_id": "B-9"' in res.text


def test_the_error_text_of_the_partner_is_reduced_and_our_headers_never_come_back(partner):
    res = run(call(partner, "broken_action", {"client_reference": "c"}, kind="action"))
    assert res.outcome == FAILED and res.error == "tool_error"
    for leak in ("/srv/partner", "10.1.2.3", SECRET, "db.py"):
        assert leak not in res.text
    assert "ledger locked" in res.text
    assert safe_error("boom\nsecond line with detail", ()) == "boom"
    assert "[redacted]" in safe_error("bad key abcd1234", ("abcd1234",))


def test_the_whole_call_has_one_budget_and_a_timeout_is_unknown(partner):
    partner.delay = 30  # the partner would answer long after the budget: a timeout can only mean the budget ran out
    res = run(call(partner, "book_repair", {"slot": "x", "client_reference": "slow-1"}, kind="action", timeout=1.0))
    assert res.outcome == UNKNOWN and res.error == "timeout"
    assert partner.effects == ["repair"]  # the effect happened; we only did not hear


def test_a_server_that_is_down_fails_before_sending_and_a_5xx_may_have_run():
    res = run(call(Partner(port=free_port()), "lookup_ticket", {"ticket_id": "T"}, kind="action", timeout=3))
    assert (res.outcome, res.error, res.sent) == (FAILED, "connect", False)
    with Partner() as p:
        p.refuse = 503
        res = run(call(p, "book_repair", {"slot": "x", "client_reference": "c"}, kind="action"))
        assert (res.outcome, res.error) == (UNKNOWN, "http")  # never retried: the partner may have run it
        assert p.rpc.count("tools/call") == 1


def test_a_refused_key_fails_without_sending():
    with Partner() as p:
        p.refuse = 401
        res = run(call(p, "book_repair", {"slot": "x", "client_reference": "c"}, kind="action"))
        assert (res.outcome, res.error, res.sent) == (FAILED, "auth", False)


def test_only_a_lookup_whose_session_died_is_tried_again_once(partner):
    async def go():
        for kind, error, expected_calls in (("lookup", "session", 2), ("lookup", "timeout", 1), ("action", "session", 1)):
            c = client(partner)
            seen = []

            async def once(name, args, k, timeout, tracking, _seen=seen, _error=error):
                _seen.append(k)
                if len(_seen) == 1:
                    return PartnerResult(FAILED if _error == "session" else UNKNOWN, "x", error=_error, sent=False)
                return PartnerResult(OK, "fine", sent=True)

            c._once = once
            res = await c.call("t", {}, kind=kind, timeout=8)
            assert len(seen) == expected_calls, (kind, error)
            assert res.attempts == expected_calls
    run(go())


def test_an_answer_over_the_cap_is_refused():
    with Partner() as p:
        async def go():
            c = PartnerMCP(p.url, allow_private=True, max_bytes=5000)
            small = await c.call("huge", {"n": 100}, kind="lookup")
            big = await c.call("huge", {"n": 50000}, kind="lookup")
            act = await c.call("huge", {"n": 50000}, kind="action")
            await c.aclose()
            return small, big, act
        small, big, act = run(go())
        assert small.outcome == OK
        assert (big.outcome, big.error) == (FAILED, "too_large")
        assert (act.outcome, act.error) == (UNKNOWN, "too_large")  # it ran; we cannot read what it said


def test_a_redirect_to_another_origin_is_not_followed():
    with Partner() as target, Partner() as p:
        p.redirect_to = target.url
        res = run(call(p, "book_repair", {"slot": "x", "client_reference": "c"}, kind="action"))
        assert res.outcome == FAILED and res.error == "redirect" and res.sent is False
        assert target.rpc == []  # nothing arrived there


def test_private_addresses_are_refused_at_connection_time_too(partner):
    async def go():
        c = PartnerMCP(partner.url, allow_private=False)
        res = await c.call("lookup_ticket", {"ticket_id": "T"}, kind="lookup")
        with pytest.raises(PartnerListError):
            await PartnerMCP(partner.url, allow_private=False).list_tools()
        await c.aclose()
        return res
    res = run(go())
    assert (res.outcome, res.error, res.sent) == (FAILED, "blocked", False)
    assert partner.rpc == []


@pytest.mark.parametrize("url", [
    "http://localhost/mcp", "http://127.0.0.1/mcp", "http://10.0.0.5/mcp", "http://192.168.1.1/mcp",
    "http://169.254.169.254/latest", "http://[::1]/mcp", "http://[::ffff:127.0.0.1]/mcp", "http://0.0.0.0/mcp",
    "http://db.internal/mcp", "http://printer.local/mcp"])
def test_ssrf_blocks_internal_urls(url):
    with pytest.raises(ssrf.Blocked):
        run(ssrf.check_url(url, False))
    run(ssrf.check_url(url, True))  # the switch for tests and closed networks


@pytest.mark.parametrize("url", ["ftp://example.com/mcp", "file:///etc/passwd", "http://", "https://user:pw@example.com/mcp",
                                 "http://example.com:99999/mcp"])
def test_ssrf_blocks_odd_urls(url):
    with pytest.raises(ssrf.Blocked):
        run(ssrf.check_url(url, True))


def test_a_name_that_resolves_inward_is_blocked(monkeypatch):
    async def go():
        loop = asyncio.get_running_loop()

        async def fake(host, port, **kw):
            return [(2, 1, 6, "", ("127.0.0.1", 0))]
        monkeypatch.setattr(loop, "getaddrinfo", fake)
        await ssrf.check_url("https://rebind.example.com/mcp", False)
    with pytest.raises(ssrf.Blocked, match="public address"):
        run(go())
