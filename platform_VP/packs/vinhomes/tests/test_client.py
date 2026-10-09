import asyncio

import httpx
import pytest

from awp_vinhomes import Conflict, Rejected, Unavailable, VinhomesClient, mapping
from fake_vinhomes import TICKET, doc, stack, submitted
from helpers import ATTRS, current, result

run = asyncio.run


def body_for(state, **over):
    return mapping.result_message(ATTRS, result(**over), current(version=state.version))


def test_it_signs_in_as_the_platform_client():
    async def go():
        async with stack() as (state, client):
            await client.inbox()
            assert state.auth_seen == [("platform", "Bearer ics_test")]
            bad = VinhomesClient("http://x", "wrong", transport=client._http._transport)
            with pytest.raises(Rejected) as e:
                await bad.inbox()
            assert e.value.status == 401 and e.value.code == "UNAUTHENTICATED" and not e.value.retryable
            await bad.aclose()
    run(go())


def test_inbox_pages_by_cursor():
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(i, "information_provided") for i in range(1, 6)]
            first = await client.inbox(None, 2)
            assert [m["message_id"] for m in first["items"]] == ["m-1", "m-2"]
            second = await client.inbox(first["next_cursor"], 10)
            assert [m["message_id"] for m in second["items"]] == ["m-3", "m-4", "m-5"]
            empty = await client.inbox(second["next_cursor"], 10)
            assert empty["items"] == [] and empty["next_cursor"] == second["next_cursor"]
    run(go())


def test_get_case_and_unknown_case():
    async def go():
        async with stack() as (state, client):
            data = await client.get_case(TICKET)
            assert data["ticket"]["version"] == 7 and data["ticket_generation"] == 0
            with pytest.raises(Rejected) as e:
                await client.get_case("00000000-0000-0000-0000-000000000000")
            assert e.value.status == 404
    run(go())


def test_posting_a_result_twice_is_harmless():
    async def go():
        async with stack() as (state, client):
            body = body_for(state)
            first = await client.post_result(TICKET, body, body["message_id"])
            again = await client.post_result(TICKET, {**body, "sent_at": "2031-01-01T00:00:00+00:00"}, body["message_id"])
            assert first["replayed"] is False and again["replayed"] is True
            assert len(state.results) == 1
    run(go())


def test_a_stale_snapshot_is_a_conflict_and_is_not_retried_by_the_client():
    async def go():
        async with stack() as (state, client):
            body = body_for(state)
            state.version += 1  # the ticket moved on
            with pytest.raises(Conflict) as e:
                await client.post_result(TICKET, body, body["message_id"])
            assert e.value.status == 409 and "stale" in e.value.message
            assert state.result_posts == 1  # one request, no blind second try
    run(go())


def test_validation_errors_say_which_field():
    async def go():
        async with stack() as (state, client):
            body = body_for(state)
            body["ticket_version"] = "seven"
            with pytest.raises(Rejected) as e:
                await client.post_result(TICKET, body, "k1")
            assert e.value.status == 422 and "ticket_version" in e.value.message
    run(go())


def test_server_trouble_is_retryable_and_so_is_a_dead_network():
    async def go():
        async with stack() as (state, client):
            state.fail = [503, 429]
            for status in (503, 429):
                with pytest.raises(Unavailable) as e:
                    await client.inbox()
                assert e.value.status == status and e.value.retryable
            await client.inbox()  # recovered

        def dead(request):
            raise httpx.ConnectError("no route")
        offline = VinhomesClient("http://nowhere", "s", transport=httpx.MockTransport(dead))
        with pytest.raises(Unavailable) as e:
            await offline.inbox()
        assert e.value.retryable and "ConnectError" in e.value.message
        await offline.aclose()
    run(go())


def test_the_idempotency_key_is_checked_before_sending():
    async def go():
        async with stack() as (state, client):
            with pytest.raises(ValueError):
                await client.post_result(TICKET, {}, "")
            with pytest.raises(ValueError):
                await client.post_plan(TICKET, {}, "k" * 161)
            assert state.result_posts == 0 and state.plan_posts == 0
    run(go())


def test_plan_and_knowledge_calls():
    async def go():
        async with stack() as (state, client):
            plan = await client.post_plan(TICKET, {"ticket_version": 7, "summary": "Thay gioăng", "steps": ["a", "b"]}, "k-1")
            assert plan["status"] == "management_pending"
            with pytest.raises(Conflict):  # a second plan while one waits
                await client.post_plan(TICKET, {"ticket_version": 7, "summary": "Khác", "steps": ["a"]}, "k-2")
            state.knowledge["resident"] = [doc("policy:1", "Giờ thi công", "Từ 8 giờ đến 17 giờ")]
            pack = await client.knowledge_pack("resident")
            assert pack["documents"][0]["title"] == "Giờ thi công" and not pack["unchanged"]
            same = await client.knowledge_pack("resident", since=pack["version"])
            assert same["unchanged"] and same["documents"] == []
    run(go())


def test_from_env_needs_a_url_and_a_secret():
    with pytest.raises(ValueError):
        VinhomesClient.from_env({"VINHOMES_API_URL": "http://x"})
    c = VinhomesClient.from_env({"VINHOMES_API_URL": "http://x/", "VINHOMES_CLIENT_SECRET": "ics_1"})
    assert c.client_id == "platform"
    run(c.aclose())
