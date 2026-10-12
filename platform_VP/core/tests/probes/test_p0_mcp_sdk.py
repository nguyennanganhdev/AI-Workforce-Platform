"""P0 probe, topic mcp_sdk: what the `mcp` SDK really does against a real FastMCP server over streamable HTTP,
and a PartnerMCP client + PartnerTool that run inside a real agent run on a scripted model.

Timings are printed (-s) and kept loose in assertions: the machine decides the numbers, not the test.
"""
import asyncio
import json
import statistics
import threading
import time
from datetime import timedelta

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError

from p0_mcp_sdk_client import FAILED, OK, PENDING, UNKNOWN, PartnerMCP, leaves
from p0_mcp_sdk_llm import MODE
from p0_mcp_sdk_server import PartnerServer
from p0_mcp_sdk_tool import ADM, SVC, PartnerTool, client_reference, make_mcp_stack

AUTH = {"Authorization": "Bearer partner-secret-1", "X-Tenant": "t1"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(params=[True, False], ids=["stateless", "stateful"])
def server(request):
    with PartnerServer(stateless=request.param) as s:
        yield s


@pytest.fixture()
def stateless_server():
    with PartnerServer(stateless=True) as s:
        yield s


# ---------------------------------------------------------------------------------------------------------
# 1. list_tools: latency, annotations, schemas, cache, headers
# ---------------------------------------------------------------------------------------------------------
def test_list_tools_latency_annotations_schema_and_cache(server):
    async def go():
        t0 = time.perf_counter()
        async with streamablehttp_client(server.url, headers=AUTH) as (r, w, _sid):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                t_init = time.perf_counter() - t0
                t1 = time.perf_counter()
                listed = await sess.list_tools()
                t_list = time.perf_counter() - t1
        by = {t.name: t for t in listed.tools}
        print(f"\n[{'stateless' if server.stateless else 'stateful'}] connect+initialize {t_init*1000:.0f} ms, "
              f"list_tools {t_list*1000:.0f} ms, {len(by)} tools")
        # annotations: only what the server set; a tool with no hint has annotations None
        assert by["lookup_ticket"].annotations.readOnlyHint is True
        assert by["book_plumber"].annotations.readOnlyHint is False
        assert by["structured_only"].annotations is None and by["boom"].annotations is None
        # input schema is plain JSON schema we can hand to the model as is
        assert by["book_plumber"].inputSchema["required"] == ["slot", "client_reference"]
        assert by["sleepy"].inputSchema["properties"]["seconds"]["type"] == "number"
        # output schema exists only for typed returns (str is wrapped as {"result": ...})
        assert by["typed_model"].outputSchema["properties"]["operation_id"]["type"] == "string"
        assert by["structured_only"].outputSchema is None
        assert t_list < 2 and t_init < 5

        # PartnerMCP: a list cache; read_only is True only for readOnlyHint=true
        client = PartnerMCP(server.url, AUTH)
        specs = await client.list_tools()
        again = await client.list_tools()
        assert specs is again and client.stats["list_calls"] == 1
        ro = {s.name: s.read_only for s in specs}
        assert ro["lookup_ticket"] is True
        assert not any(v for k, v in ro.items() if k != "lookup_ticket")   # unannotated => NOT read only
        await client.list_tools(refresh=True)
        assert client.stats["list_calls"] == 2
        assert len(server.list_calls) == 3     # raw session (1) + first PartnerMCP list (1) + refresh (1)

    run(go())


def test_list_cache_survives_a_dead_server_and_fails_loudly_without_cache(stateless_server):
    async def go():
        c = PartnerMCP(stateless_server.url, AUTH, connect_timeout=3)
        first = await c.list_tools()
        stateless_server.stop()
        t0 = time.perf_counter()
        stale = await c.list_tools(refresh=True)            # refresh fails: the old list is kept, not "no tools"
        assert stale is first
        print(f"\nstale list served after {time.perf_counter()-t0:.1f}s of trying")
        fresh = PartnerMCP(stateless_server.url, AUTH, connect_timeout=3)
        from p0_mcp_sdk_client import PartnerListError
        with pytest.raises(PartnerListError):               # no cache: an error the caller sees, not an empty list
            await fresh.list_tools()

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 2. content vs structuredContent
# ---------------------------------------------------------------------------------------------------------
def test_structured_content_vs_content(server):
    async def go():
        async with streamablehttp_client(server.url, headers=AUTH) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                a = await sess.call_tool("structured_only", {"ref": "r1"})
                b = await sess.call_tool("typed_model", {"ref": "r1"})
                c = await sess.call_tool("structured_dict", {"ref": "r1"})
                d = await sess.call_tool("lookup_ticket", {"ticket_id": "T-1"})
        # structured only: content is EMPTY, the data is only in structuredContent
        assert a.content == [] and a.structuredContent["operation_id"] == "op-9"
        # a typed (pydantic) return: both, same data
        assert json.loads(b.content[0].text) == b.structuredContent == {"status": "queued", "operation_id": "op-11"}
        # an untyped dict return: text only, no structuredContent
        assert c.structuredContent is None and json.loads(c.content[0].text)["operation_id"] == "op-10"
        # a str return: text, plus a {"result": text} copy as structuredContent
        assert d.structuredContent == {"result": d.content[0].text}

        client = PartnerMCP(server.url, AUTH)
        ra = await client.call("structured_only", {"ref": "r1"}, kind="action")
        assert ra.outcome == OK and ra.external_job_id == "op-9" and "op-9" in ra.text   # nothing lost
        rb = await client.call("typed_model", {"ref": "r1"}, kind="action")
        assert rb.outcome == PENDING and rb.external_job_id == "op-11"
        assert rb.text.count("op-11") == 1                                              # not shown twice
        rc = await client.call("structured_dict", {"ref": "r1"}, kind="action")
        assert rc.outcome == PENDING and rc.status == "accepted" and rc.external_job_id == "op-10"
        rd = await client.call("lookup_ticket", {"ticket_id": "T-1"})
        assert rd.outcome == OK and rd.text == d.content[0].text                         # str wrapper not doubled
        rbk = await client.call("book_plumber", {"slot": "s", "client_reference": "wf-1"}, kind="action")
        assert rbk.outcome == PENDING and rbk.external_job_id == "op-7781" and "wf-1" in rbk.text
        # tracking 'none': the partner said pending but we are not told to follow it: done from our side
        rn = await client.call("book_plumber", {"slot": "s", "client_reference": "wf-2"}, kind="action",
                               tracking="none")
        assert rn.outcome == OK and rn.status == "pending"

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 3. isError and exceptions
# ---------------------------------------------------------------------------------------------------------
def test_tool_error_is_a_result_not_an_exception(server):
    async def go():
        async with streamablehttp_client(server.url) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                res = await sess.call_tool("boom", {})                      # no exception: isError=True
                assert res.isError is True and "ledger locked" in res.content[0].text
                bad = await sess.call_tool("no_such_tool", {})              # unknown tool: also isError, not an exception
                assert bad.isError is True and "Unknown tool" in bad.content[0].text
                res2 = await sess.call_tool("book_plumber", {"slot": "x"})  # missing arg: validation error
                assert res2.isError is True
                print("missing arg ->", res2.content[0].text[:120])
        client = PartnerMCP(server.url)
        boom_before = len(server.of("boom"))
        r1 = await client.call("boom", {}, kind="action")
        assert (r1.outcome, r1.error, r1.is_error) == (FAILED, "tool_error", True) and "ledger locked" in r1.text
        r2 = await client.call("book_plumber", {"slot": "x"}, kind="action")
        assert r2.outcome == FAILED
        assert len(server.of("boom")) == boom_before + 1                     # an error is never retried
        r3 = await client.call("no_such_tool", {}, kind="action")
        assert r3.outcome == FAILED

    run(go())


def test_sdk_call_tool_raises_after_the_server_ran_when_structured_content_does_not_fit(server):
    """ClientSession.call_tool validates structuredContent against the outputSchema AFTER the call ran."""
    async def go():
        async with streamablehttp_client(server.url, headers=AUTH) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                with pytest.raises(RuntimeError, match="Invalid structured content"):
                    await sess.call_tool("typed_lying", {"ref": "x"})
        assert len(server.of("typed_lying")) == 1               # it ran: the effect happened, the answer was lost
        c = PartnerMCP(server.url, AUTH)
        res = await c.call("typed_lying", {"ref": "y"}, kind="action")      # our send_call does not validate
        assert res.outcome == OK and res.external_job_id == "op-12"
        assert len(server.of("typed_lying")) == 2

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 4. read timeout: it cuts the wait, not the work
# ---------------------------------------------------------------------------------------------------------
def test_read_timeout_cuts_the_wait_but_the_server_keeps_working(server):
    async def go():
        async with streamablehttp_client(server.url, headers=AUTH) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                t0 = time.perf_counter()
                with pytest.raises(McpError) as ei:
                    await sess.call_tool("sleepy", {"seconds": 2.0}, read_timeout_seconds=timedelta(seconds=0.5))
                took = time.perf_counter() - t0
                assert ei.value.error.code == 408 and "Timed out" in str(ei.value)
                assert 0.4 < took < 1.5, took
                row = server.of("sleepy")[0]
                assert row["side_effect"] is True and row["t_end"] is None       # still running at the moment we give up
                await asyncio.sleep(2.0)
                assert row["t_end"] is not None and "cancelled" not in row       # it finished anyway: no cancellation
                assert len(server.of("sleepy")) == 1
                # the session is still usable after a read timeout
                ok = await sess.call_tool("lookup_ticket", {"ticket_id": "T-2"})
                assert ok.isError is False
        print(f"\n[{'stateless' if server.stateless else 'stateful'}] read_timeout 0.5s fired after {took:.2f}s; "
              f"server call completed anyway")

        client = PartnerMCP(server.url, AUTH, call_timeout=0.5)
        res = await client.call("sleepy", {"seconds": 1.5}, kind="action")
        assert (res.outcome, res.error, res.sent, res.attempts) == (UNKNOWN, "timeout", True, 1)
        await asyncio.sleep(1.8)
        assert len(server.of("sleepy")) == 2          # exactly one more server call: nothing was re-sent

    run(go())


def test_without_a_read_timeout_the_sdk_waits_for_as_long_as_the_server_does(stateless_server):
    """call_tool has no default read timeout: only read_timeout_seconds bounds it (the 30 s in HttpMCPConfig
    is the HTTP connect/read timeout of the transport, not a limit on a streamed answer)."""
    async def go():
        async with streamablehttp_client(stateless_server.url, timeout=0.5) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                res = await sess.call_tool("sleepy", {"seconds": 1.5})       # longer than `timeout=0.5`, no error
                assert res.isError is False and json.loads(res.content[0].text)["status"] == "completed"

    run(go())


@pytest.mark.parametrize("stateless,json_response", [(True, False), (False, False), (True, True)],
                         ids=["stateless-sse", "stateful-sse", "stateless-json"])
def test_http_read_timeout_shorter_than_the_call_is_the_dangerous_setting(stateless, json_response):
    """AgentScope's HttpMCPConfig.timeout (default 30) becomes httpx.Timeout(30) for connect AND read, and
    execution_timeout (read_timeout_seconds) defaults to None. Reproduced here with 0.7 s vs a 2 s call."""
    import httpx
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client

    async def go():
        with PartnerServer(stateless=stateless, json_response=json_response) as srv:
            outcome = {}
            try:
                http = create_mcp_http_client(timeout=httpx.Timeout(0.7))
                async with http:
                    async with streamable_http_client(srv.url, http_client=http) as (r, w, _):
                        async with ClientSession(r, w) as sess:
                            await sess.initialize()
                            t0 = time.perf_counter()
                            try:
                                # NO read_timeout_seconds: only our own wait_for bounds this
                                await asyncio.wait_for(sess.call_tool("sleepy", {"seconds": 2}), 4)
                                outcome["result"] = "returned"
                            except asyncio.TimeoutError:
                                outcome["result"] = "HUNG (until our wait_for)"
                            except asyncio.CancelledError:
                                outcome["result"] = "CancelledError leaked, nobody cancelled"
                            except McpError as e:
                                outcome["result"] = f"McpError {e}"
                            outcome["after"] = round(time.perf_counter() - t0, 2)
            except BaseException as e:   # noqa: BLE001
                outcome["on_exit"] = [type(x).__name__ for x in leaves(e)]
            return outcome, srv.of("sleepy")[0]

    outcome, row = run(go())
    print(f"[stateless={stateless} json={json_response}] http read timeout 0.7s, call 2s, no read_timeout_seconds:",
          outcome, "| server finished:", row["t_end"] is not None)
    if json_response:
        assert outcome["result"].startswith("CancelledError") and outcome["after"] < 1.5
        assert outcome["on_exit"] == ["ReadTimeout"]
    else:
        assert outcome["result"].startswith("HUNG")          # SSE: the read timeout is swallowed, the call never returns


# ---------------------------------------------------------------------------------------------------------
# 5. an action runs once
# ---------------------------------------------------------------------------------------------------------
def test_an_action_is_sent_at_most_once(server):
    async def go():
        client = PartnerMCP(server.url, AUTH, call_timeout=0.4)
        ok = await client.call("record_action", {"note": "n1"}, kind="action")
        assert ok.outcome == OK and len(server.of("record_action")) == 1
        slow = await client.call("sleepy", {"seconds": 1.0}, kind="action")             # unknown, not retried
        assert slow.outcome == UNKNOWN and slow.attempts == 1
        failed = await client.call("boom", {}, kind="action")
        assert failed.outcome == FAILED and failed.attempts == 1
        await asyncio.sleep(1.2)
        assert [len(server.of(t)) for t in ("record_action", "sleepy", "boom")] == [1, 1, 1]

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 6. connection reuse vs a new session per call
# ---------------------------------------------------------------------------------------------------------
def test_latency_new_session_per_call_vs_shared_session(server):
    async def timed(client, n):
        out = []
        for i in range(n):
            t = time.perf_counter()
            r = await client.call("lookup_ticket", {"ticket_id": f"T-{i}"})
            assert r.outcome == OK
            out.append((time.perf_counter() - t) * 1000)
        return out

    async def go():
        per_call = PartnerMCP(server.url, AUTH, shared=False, reuse_http=False)
        pooled = PartnerMCP(server.url, AUTH, shared=False, reuse_http=True)
        shared = PartnerMCP(server.url, AUTH, shared=True)
        a = await timed(per_call, 12)
        p = await timed(pooled, 12)
        b = await timed(shared, 12)
        await shared.aclose()
        await pooled.aclose()
        print(f"[{'stateless' if server.stateless else 'stateful'}] lookup latency ms: "
              f"new session + new httpx client per call median {statistics.median(a):.0f} (first {a[0]:.0f}); "
              f"new session, pooled httpx client median {statistics.median(p[1:]):.0f} (first {p[0]:.0f}); "
              f"shared session median {statistics.median(b[1:]):.0f} (first {b[0]:.0f}); "
              f"sessions opened {per_call.stats['sessions_opened']} / {pooled.stats['sessions_opened']} / "
              f"{shared.stats['sessions_opened']}")
        assert statistics.median(p[1:]) < statistics.median(a)           # a pooled client is cheaper
        assert per_call.stats["sessions_opened"] == 12 and shared.stats["sessions_opened"] == 1
        # what one fresh-session call costs on the wire: 3 POSTs (+ a DELETE to end a stateful session)
        server.rpc.clear()
        await PartnerMCP(server.url, AUTH).call("lookup_ticket", {"ticket_id": "w"})
        assert [r["method"] for r in server.rpc] == ["initialize", "notifications/initialized", "tools/call"]
        # the SDK's own call_tool adds a hidden tools/list the first time a tool is used in a session
        server.rpc.clear()
        async with streamablehttp_client(server.url, headers=AUTH) as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                await sess.call_tool("lookup_ticket", {"ticket_id": "w"})
                await sess.call_tool("lookup_ticket", {"ticket_id": "w2"})     # second use of the same tool: cached
        methods = [x["method"] for x in server.rpc]
        print("raw SDK call_tool x2 on one session:", methods)
        assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/call", "tools/call"] or             methods == ["initialize", "notifications/initialized", "tools/call", "tools/list", "tools/call"]
        assert statistics.median(b[1:]) < statistics.median(p[1:])       # reuse is cheaper (3 round trips vs 1)

    run(go())


def test_cached_session_after_server_restart(server):
    """Raw SDK first (what AgentScope's stateful MCPClient would do), then PartnerMCP."""
    async def go():
        cm = streamablehttp_client(server.url, headers=AUTH)
        r, w, sid = await cm.__aenter__()
        sess = ClientSession(r, w)
        await sess.__aenter__()
        await sess.initialize()
        assert (sid() is None) == server.stateless
        await sess.call_tool("lookup_ticket", {"ticket_id": "A"})
        server.restart()
        try:
            res = await sess.call_tool("lookup_ticket", {"ticket_id": "B"}, read_timeout_seconds=timedelta(seconds=5))
            recovered, err = True, None
        except McpError as e:
            recovered, err = False, str(e)
        print(f"\n[{'stateless' if server.stateless else 'stateful'}] raw cached session after restart: "
              f"recovered={recovered} err={err}")
        # stateless servers keep no session: the cached client session just works; stateful ones answer 404
        # "Session terminated" for the old session id, and it never comes back
        assert recovered is server.stateless
        if not server.stateless:
            with pytest.raises(McpError):
                await sess.call_tool("lookup_ticket", {"ticket_id": "C"}, read_timeout_seconds=timedelta(seconds=5))
            assert [c["args"]["ticket_id"] for c in server.of("lookup_ticket")] == ["A"]   # the 404 calls did not run
        try:
            await sess.__aexit__(None, None, None)
            await cm.__aexit__(None, None, None)
        except BaseException:   # noqa: BLE001 - closing a dead session may raise; not the point here
            pass

        # PartnerMCP shared: one transparent reconnect for a lookup, whatever the server mode
        c = PartnerMCP(server.url, AUTH, shared=True)
        assert (await c.call("lookup_ticket", {"ticket_id": "D"})).outcome == OK
        server.restart()
        res = await c.call("lookup_ticket", {"ticket_id": "E"})
        assert res.outcome == OK
        assert res.attempts == (1 if server.stateless else 2)
        assert [x["args"]["ticket_id"] for x in server.of("lookup_ticket")][-2:] == ["D", "E"] or \
               "E" in [x["args"]["ticket_id"] for x in server.of("lookup_ticket")]
        await c.aclose()

    run(go())


def test_an_action_never_rides_a_cached_session(server):
    """Actions always open a session of their own; so a restart in between cannot make one ambiguous."""
    async def go():
        c = PartnerMCP(server.url, AUTH, shared=True)
        await c.call("lookup_ticket", {"ticket_id": "A"})
        opened = c.stats["sessions_opened"]
        server.restart()
        res = await c.call("record_action", {"note": "after restart"}, kind="action")
        assert res.outcome == OK and res.attempts == 1 and c.stats["sessions_opened"] == opened + 1
        assert len(server.of("record_action")) == 1
        await c.aclose()

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 7. headers
# ---------------------------------------------------------------------------------------------------------
def test_static_headers_reach_the_server_on_every_request(server):
    async def go():
        c = PartnerMCP(server.url, AUTH)
        await c.list_tools()
        await c.call("lookup_ticket", {"ticket_id": "H1"})
        await c.call("book_plumber", {"slot": "s", "client_reference": "wf-h"}, kind="action")
        assert [x["auth"] for x in server.list_calls] == ["Bearer partner-secret-1"]
        assert {x["auth"] for x in server.calls} == {"Bearer partner-secret-1"}
        assert {x["x_tenant"] for x in server.calls} == {"t1"}
        methods = {r["method"] for r in server.rpc}
        assert {"initialize", "notifications/initialized", "tools/list", "tools/call"} <= methods
        assert {r["auth"] for r in server.rpc} == {"Bearer partner-secret-1"}    # on EVERY request, not just tools/call
        anon = PartnerMCP(server.url)
        await anon.call("lookup_ticket", {"ticket_id": "H2"})
        assert server.calls[-1]["auth"] is None                 # no header unless we set it

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 8. server down, server dying mid-call
# ---------------------------------------------------------------------------------------------------------
def test_server_down_fails_fast_and_says_not_sent():
    async def go():
        dead = PartnerServer()                                      # never started: connection refused
        c = PartnerMCP(dead.url, AUTH, connect_timeout=5)
        for kind in ("lookup", "action"):
            t0 = time.perf_counter()
            res = await c.call("record_action" if kind == "action" else "lookup_ticket", {"note": "x", "ticket_id": "x"},
                               kind=kind)
            took = time.perf_counter() - t0
            print(f"\nserver down ({kind}): {res.outcome}/{res.error} sent={res.sent} after {took:.2f}s")
            assert (res.outcome, res.error, res.sent) == (FAILED, "connect", False)
            assert took < 6
        # the SDK's own error type, for the record: a ConnectError wrapped in an ExceptionGroup
        try:
            async with streamablehttp_client(dead.url, timeout=5) as (r, w, _):
                async with ClientSession(r, w) as sess:
                    await asyncio.wait_for(sess.initialize(), 10)
        except BaseException as e:   # noqa: BLE001
            assert isinstance(e, BaseExceptionGroup)
            assert type(leaves(e)[0]).__name__ == "ConnectError"

    run(go())


def test_refused_key_and_http_5xx_are_mapped(stateless_server):
    async def go():
        s = stateless_server
        s.require_token = "right-key"
        bad = PartnerMCP(s.url, {"Authorization": "Bearer old-key"})
        r = await bad.call("record_action", {"note": "x"}, kind="action")
        print(f"401: {r.outcome}/{r.error} sent={r.sent}: {r.text}")
        assert (r.outcome, r.error, r.sent) == (FAILED, "auth", False) and not s.of("record_action")
        from p0_mcp_sdk_client import PartnerListError
        with pytest.raises(PartnerListError):
            await PartnerMCP(s.url, {"Authorization": "Bearer old-key"}).list_tools()
        good = PartnerMCP(s.url, {"Authorization": "Bearer right-key"})
        assert (await good.call("lookup_ticket", {"ticket_id": "ok"})).outcome == OK
        s.http_fail["tools/call"] = 500                    # the gateway fails the call itself
        r5 = await good.call("record_action", {"note": "y"}, kind="action")
        print(f"500 on tools/call: {r5.outcome}/{r5.error} sent={r5.sent}")
        assert (r5.outcome, r5.error) == (UNKNOWN, "http") and r5.attempts == 1
        r6 = await good.call("lookup_ticket", {"ticket_id": "z"}, kind="lookup")
        assert r6.outcome == UNKNOWN                       # a lookup is not retried on 5xx either: no hidden loops

    run(go())


@pytest.mark.parametrize("stateless", [True, False], ids=["stateless", "stateful"])
def test_server_killed_mid_call_is_unknown_and_the_total_time_stays_bounded(stateless):
    async def go():
        with PartnerServer(stateless=stateless) as s:
            c = PartnerMCP(s.url, AUTH, call_timeout=2.5)
            threading.Timer(0.4, s.stop).start()
            t0 = time.perf_counter()
            res = await c.call("sleepy", {"seconds": 4}, kind="action")
            took = time.perf_counter() - t0
            print(f"[stateless={stateless}] server killed mid-call: {res.outcome}/{res.error} after {took:.2f}s")
            assert res.outcome == UNKNOWN and res.sent in (True, None)        # never FAILED: we cannot know
            assert res.error in ("timeout", "transport")
            assert took >= 2.3            # the SDK did not notice the dropped stream before the read timeout
            assert took < 2.5 + 0.5 + 0.5, took    # ...and closing a session on a dead server did not add 2 s
            assert len(s.of("sleepy")) == 1

    run(go())


def test_dead_shared_session_does_not_leak_a_cancellederror_to_the_caller():
    """A cached SDK session whose server died crashes its transport task group and cancels the awaiting task
    with CancelledError even though nobody asked it to cancel. PartnerMCP must turn that into a result."""
    async def go():
        s = PartnerServer(stateless=True).start()
        try:
            c = PartnerMCP(s.url, AUTH, shared=True, connect_timeout=3, call_timeout=4)
            assert (await c.call("lookup_ticket", {"ticket_id": "A"})).outcome == OK
            s.stop()
            res = await c.call("lookup_ticket", {"ticket_id": "B"})            # must return, not raise
            assert res.outcome in (FAILED, UNKNOWN)
            s.start()
            res2 = await c.call("lookup_ticket", {"ticket_id": "C"})           # and recover once the server is back
            assert res2.outcome == OK
            await c.aclose()
        finally:
            s.stop()

    run(go())


def test_own_cancellation_is_not_swallowed(stateless_server):
    async def go():
        c = PartnerMCP(stateless_server.url, AUTH, call_timeout=10)
        task = asyncio.create_task(c.call("sleepy", {"seconds": 5}, kind="action"))
        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(go())


# ---------------------------------------------------------------------------------------------------------
# 9. inside a real agent run
# ---------------------------------------------------------------------------------------------------------
def _intake():
    return {"message_id": "m-1", "external_ref": "TICKET-1", "summary": "Pipe leaking in unit A-12-05",
            "description": "Water under the sink since this morning.",
            "facts": [{"key": "unit", "value": "A-12-05", "source": "reported"}]}


def _wait(client, case_id, status="finalized", timeout=60):
    end, case = time.time() + timeout, None
    while time.time() < end:
        case = client.get(f"/platform/v1/cases/{case_id}", headers=SVC).json()
        if case["status"] == status:
            return case
        time.sleep(0.3)
    items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()
    raise AssertionError(f"case stayed {case['status']}; items={items}")


def test_partner_tools_in_an_agent_run_become_evidence(tmp_path):
    with PartnerServer(stateless=True) as srv:
        partner = PartnerMCP(srv.url, AUTH, call_timeout=10)
        seen: list = []
        MODE.update({
            "worker_calls": [("partner_lookup_ticket", {"ticket_id": "T-1001"}),
                             ("partner_book_plumber", {"slot": "2026-10-12 09:00"})],
            "fact_texts": ["Ticket T-1001 is waiting for the plumber",
                           "Plumber booking is pending, reference op-7781"],
            "answer": "Ticket T-1001 is waiting for the plumber. A plumber booking is pending, reference op-7781."})
        with make_mcp_stack(tmp_path, partner, inject={"client_reference": client_reference}, allow_actions=True,
                            on_result=lambda tool, args, res: seen.append((tool.name, args, res.outcome))) as \
                (client, pack, _rt):
            r = client.post("/platform/v1/intake", headers=SVC, json=_intake())
            assert r.status_code == 202, r.text
            case_id = r.json()["case_id"]
            case = _wait(client, case_id)
            items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
            from p0_mcp_sdk_llm import CALLS
            model_calls = list(CALLS)

        assert case["result"]["outcome"] == "resolved" and "op-7781" in case["result"]["answer"]
        # the tool list was fetched once, however many agents were built and steps taken
        assert len(srv.list_calls) == 1, srv.list_calls
        assert len(pack.built) >= 2 and all("partner_lookup_ticket" in names for names in pack.built)
        # each tool result became an evidence item holding the text the partner returned
        ev = {i["data"]["tool"]: i for i in items if i["kind"] == "evidence"}
        assert "waiting for plumber" in ev["partner_lookup_ticket"]["data"]["text"]
        assert "PENDING" in ev["partner_book_plumber"]["data"]["text"] and "op-7781" in ev["partner_book_plumber"]["data"]["text"]
        # and facts cite them
        facts = [i for i in items if i["kind"] == "fact"]
        cited = {e for f in facts for e in f["data"]["evidence"]}
        assert {ev["partner_lookup_ticket"]["ref"], ev["partner_book_plumber"]["ref"]} <= cited
        # the server saw the calls once, with our static header and an injected client_reference the model never saw
        assert [c["tool"] for c in srv.calls] == ["lookup_ticket", "book_plumber"]
        assert srv.of("book_plumber")[0]["args"]["client_reference"].startswith("wf-")
        assert srv.of("book_plumber")[0]["args"]["client_reference"] == client_reference(
            "book_plumber", {"slot": "2026-10-12 09:00"})
        assert {c["auth"] for c in srv.calls} == {"Bearer partner-secret-1"}
        assert [s[2] for s in seen] == ["ok", "pending"]
        worker = [c for c in model_calls if 'key="tech"' in c["sys"]]
        assert worker and "partner_book_plumber" in worker[0]["tools"]
        leader = [c for c in model_calls if 'key="supervisor"' in c["sys"]]
        assert not any(n.startswith("partner_") for c in leader for n in c["tools"])   # profile gate: leader has none
        schema = next(t for t in worker[0]["schemas"] if t["function"]["name"] == "partner_book_plumber")
        assert list(schema["function"]["parameters"]["properties"]) == ["slot"]        # client_reference hidden
        print("\nworker tools:", sorted(worker[0]["tools"]))


def test_action_without_permission_does_not_reach_the_partner(tmp_path):
    """A tool with side effects whose check_permissions says ASK never runs in this headless core."""
    with PartnerServer(stateless=True) as srv:
        partner = PartnerMCP(srv.url, AUTH, call_timeout=10)
        MODE.update({
            "worker_calls": [("partner_lookup_ticket", {"ticket_id": "T-1001"}),
                             ("partner_book_plumber", {"slot": "2026-10-12 09:00"})],
            "fact_texts": ["Ticket T-1001 is waiting for the plumber", ""],
            "answer": "Ticket T-1001 is waiting for the plumber."})
        with make_mcp_stack(tmp_path, partner, inject={"client_reference": client_reference},
                            allow_actions=False) as (client, pack, _rt):
            r = client.post("/platform/v1/intake", headers=SVC, json=_intake())
            case_id = r.json()["case_id"]
            _wait(client, case_id)
            items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
            from p0_mcp_sdk_llm import CALLS
            seen_by_model = [m for c in CALLS for m in c["tool_msgs"]]
        denied = [m for m in seen_by_model if "book" in m.lower() or "permission" in m.lower() or "denied" in m.lower()]
        print("what the agent was told when the action was not permitted:", denied[:1])
        assert denied, seen_by_model
        assert [c["tool"] for c in srv.calls] == ["lookup_ticket"]                     # book_plumber never reached it
        assert not [i for i in items if i["kind"] == "evidence" and i["data"]["tool"] == "partner_book_plumber"]
