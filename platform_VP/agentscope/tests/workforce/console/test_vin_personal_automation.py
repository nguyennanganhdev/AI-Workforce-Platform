"""C09 consumers use real SQL leases with fake chat, Redis and Discord IO."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update

from vin_fixtures import authority as authority  # noqa: F401
from storage_redis_knowledge_base_test import make_storage
from utils import FakeWorkspaceManager
from agentscope.app._manager import SchedulerManager
from agentscope.app._service._discord_identity import _identity_id
from agentscope.app._service._personal_jobs import PersonalJobWorker, enqueue_channel, ledger, personal_job
from agentscope.app.channel import ChannelEvent, DiscordChannel
from agentscope.app.storage import AgentData, AgentRecord, ChannelRecord, RoutingConfig, ChannelBinding, SessionSettings, ChatModelConfig, ScheduleData, ScheduleRecord
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._service import now
from agentscope.app.workforce.foundation._tables import durable_jobs
from agentscope.app.workforce.foundation.event_delivery import JobLeaseLostError
from agentscope.message import AssistantMsg, TextBlock
from agentscope.agent import ContextConfig, ReActConfig
from agentscope.types import ReplyFinishedReason


@pytest_asyncio.fixture
async def automation(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = make_storage()
    storage.vin_platform_service = authority
    async with authority.engine.begin() as db:
        await db.run_sync(durable_jobs.create)
    context = await authority.context("alice")
    await authority.automation_put(context, _identity_id(context), "channel", {"state": "verified", "discord_user_id": "100", "verified_at": 1})
    agent = AgentRecord(id="leader", user_id="alice", data=AgentData(name="Leader", system_role="leader", context_config=ContextConfig(), react_config=ReActConfig()))
    await storage.upsert_agent("alice", agent)
    channel = ChannelRecord(id="private-channel", user_id="alice", channel_type="discord", credentials={"application_id": "99", "bot_token": "offline-only"},
        platform_config={"owner_user_id": "100", "allowed_user_ids": ["100"]}, routing=RoutingConfig(bindings=[ChannelBinding(agent_id="leader")]),
        session=SessionSettings(chat_model_config={"type": "openai_credential", "credential_id": "fixture", "model": "fixture", "parameters": {}}))
    await storage.upsert_channel(channel, "99")
    record = ScheduleRecord(id="schedule-one", user_id="alice", agent_id="leader", data=ScheduleData(name="Fixture once", description="Tóm tắt fixture",
        cron_expression="* * * * *", timezone="UTC", once=True, chat_model_config=ChatModelConfig(type="openai_credential", credential_id="fixture", model="fixture", parameters={}),
        deliver_channel_id=channel.id, deliver_chat_id="77"))
    await storage.upsert_schedule("alice", record)
    calls, deliveries = [], []
    async def run(user, session, agent_id, input_msg):
        from agentscope.app.vin_platform._context import execution_context
        assert personal_job.get() is not None
        assert execution_context.get().initiator_user_id == user
        assert execution_context.get().billing_subject_id == user
        calls.append((user, session, input_msg))
        await storage.upsert_message(user, session, AssistantMsg(name="assistant", content="Fixture đã xử lý", finished_reason=ReplyFinishedReason.COMPLETED,
            metadata={"personal_job_id": personal_job.get().job_id}))
    async def deliver(body):
        deliveries.append(body)
        return {"state": "delivered", "message_id": "fixture-message"}
    client = SimpleNamespace(send_saved_private=AsyncMock(side_effect=deliver))
    chat = SimpleNamespace(run=AsyncMock(side_effect=run), _message_bus=SimpleNamespace(queue_drain=AsyncMock(return_value=[])),
        _channel_clients=SimpleNamespace(get=AsyncMock(return_value=client)))
    workspaces = FakeWorkspaceManager()
    manager = SchedulerManager(storage, SimpleNamespace(publish=AsyncMock()), workspaces)
    yield SimpleNamespace(storage=storage, authority=authority, context=context, record=record, channel=channel,
        manager=manager, worker=PersonalJobWorker(storage, chat, workspaces), chat=chat, client=client, calls=calls, deliveries=deliveries)
    await storage._client.aclose()


@pytest.mark.asyncio
async def test_once_enqueue_two_nodes_runs_once_with_ledger_and_separate_outbox(automation):
    a = automation
    # Both timer owners saw the same enabled snapshot.
    await asyncio.gather(a.manager._build_trigger(a.record)(), a.manager._build_trigger(a.record)())
    assert not (await a.storage.get_schedule("alice", a.record.id)).data.enabled
    assert len(await a.authority.jobs.list(a.context, "schedule-run")) == 1
    await a.worker.run_one()
    assert len(a.calls) == 1 and a.calls[0][0] == "alice"
    assert a.deliveries == []
    runs = (await ledger(a.storage, "alice", "schedule-run", a.record.id))["items"]
    assert runs[0]["outcome"] == "succeeded" and runs[0]["session_id"]
    assert runs[0]["deliveries"][0]["status"] == "pending"
    await a.worker.run_one()
    assert len(a.deliveries) == len(a.calls) == 1
    await a.manager._build_trigger(a.record)()
    assert not await a.worker.run_one()
    assert (await ledger(a.storage, "bob", "schedule-run", a.record.id))["items"] == []


@pytest.mark.asyncio
async def test_failed_model_once_is_never_automatically_repeated(automation):
    a = automation
    a.chat.run.side_effect = RuntimeError("offline fake run failure")
    await a.manager._build_trigger(a.record)()
    await a.worker.run_one()
    assert a.chat.run.await_count == 1
    await a.manager._build_trigger(a.record)()
    assert not await a.worker.run_one()
    run = (await a.authority.jobs.list(a.context, "schedule-run"))[0]
    assert run.status == "failed" and not (await a.storage.get_schedule("alice", a.record.id)).data.enabled


@pytest.mark.asyncio
async def test_delivery_retry_uses_exact_saved_body_and_no_new_model_call(automation):
    a = automation
    await a.manager._build_trigger(a.record)()
    await a.worker.run_one()
    a.client.send_saved_private.side_effect = PlatformError("DELIVERY_TRANSPORT_UNAVAILABLE", 503)
    await a.worker.run_one()
    failed = (await a.authority.jobs.list(a.context, "delivery"))[0]
    assert failed.status == "pending" and failed.attempt == 1
    first = a.client.send_saved_private.await_args.args[0].copy()
    async with a.authority.engine.begin() as db:
        await db.execute(update(durable_jobs).where(durable_jobs.c.id == failed.job_id).values(not_before=now()))
    a.client.send_saved_private.side_effect = None
    a.client.send_saved_private.return_value = {"state": "delivered", "message_id": "fixture-retry"}
    await a.worker.run_one()
    assert a.client.send_saved_private.await_args.args[0] == first
    assert len(a.calls) == 1
    delivery = (await a.authority.jobs.list(a.context, "delivery"))[0]
    assert delivery.status == "succeeded" and delivery.fencing_token > failed.fencing_token


@pytest.mark.asyncio
async def test_expired_run_claim_rejects_stale_worker_without_rerunning(automation):
    a = automation
    await a.manager._build_trigger(a.record)()
    stale = await a.authority.jobs.claim("crashed-worker")
    async with a.authority.engine.begin() as db:
        await db.execute(update(durable_jobs).where(durable_jobs.c.id == stale.job_id).values(lease_expires_at=now() - timedelta(seconds=1)))
    assert not await a.worker.run_one()
    assert not a.calls
    with pytest.raises(JobLeaseLostError):
        await a.authority.jobs.complete(stale, "crashed-worker", {})
    run = (await a.authority.jobs.list(a.context, "schedule-run"))[0]
    assert run.error["code"] == "OUTCOME_UNKNOWN"


@pytest.mark.asyncio
async def test_duplicate_discord_event_is_one_private_run_and_revocation_blocks_delivery(automation):
    a = automation
    event = ChannelEvent(channel_id=a.channel.id, channel_user_id="100", chat_id="77", channel_message_id="500",
        content=[TextBlock(text="Fixture hỏi tiến độ")], metadata={"chat_type": "dm"})
    first = await enqueue_channel(a.storage, a.channel, event)
    again = await enqueue_channel(a.storage, a.channel, event.model_copy(update={"received_at": "changed"}))
    assert first.job_id == again.job_id
    await a.worker.run_one()
    assert len(a.calls) == 1
    rows = await a.authority.automation_list(a.context, "channel")
    row = rows[0]
    await a.authority.automation_put(a.context, row["id"], "channel", {"state": "revoked"}, row["revision"])
    await a.worker.run_one()
    assert not a.deliveries
    a.client.send_saved_private.assert_not_awaited()
    with pytest.raises(PlatformError, match="DISCORD_IDENTITY_REQUIRED"):
        await enqueue_channel(a.storage, a.channel, event.model_copy(update={"channel_message_id": "501"}))


@pytest.mark.asyncio
async def test_wrong_dm_recipient_and_guild_rejected_before_model(automation):
    a = automation
    for user, kind in (("200", "dm"), ("100", "guild")):
        with pytest.raises(PlatformError, match="PRIVATE_CHANNEL_DENIED"):
            await enqueue_channel(a.storage, a.channel, ChannelEvent(channel_id=a.channel.id, channel_user_id=user, chat_id="77",
                channel_message_id="500", content=[TextBlock(text="blocked")], metadata={"chat_type": kind}))
    assert not a.calls


@pytest.mark.asyncio
async def test_discord_saved_send_verifies_dm_and_nonce_on_transport():
    channel = DiscordChannel("private", DiscordChannel.Credentials(bot_token="offline-token", application_id="99"),
        DiscordChannel.Config(allowed_user_ids=["100"]), private_account=True)
    calls = []
    def transport(request):
        if request.method == "GET":
            return httpx.Response(200, json={"type": 1, "recipients": [{"id": "100"}]})
        import json
        body = json.loads(request.content)
        calls.append(body)
        assert body["nonce"] == "stable-nonce" and body["enforce_nonce"] is True and body["allowed_mentions"] == {"parse": []}
        return httpx.Response(200, json={"id": "saved-message"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        channel._saved_http_client = client
        result = await channel.send_saved_private({"chat_id": "77", "recipient_id": "100", "body": "fixture body", "nonce": "stable-nonce"})
    assert result == {"state": "delivered", "message_id": "saved-message"} and len(calls) == 1


@pytest.mark.asyncio
async def test_worker_cancels_on_lost_heartbeat_without_outbox(automation, monkeypatch):
    from agentscope.app._service import _personal_jobs
    a = automation
    monkeypatch.setattr(_personal_jobs, "HEARTBEAT_SECONDS", 0.01)
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def blocked(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    a.chat.run.side_effect = blocked
    await a.manager._build_trigger(a.record)()
    # Revoke the active fence at heartbeat using the real SQL repository.
    from agentscope.app.vin_platform._jobs import PersonalJobs
    heartbeat = PersonalJobs.heartbeat
    async def lost(jobs, job, worker_id, **kwargs):
        # Synchronize the fault with the operation we intend to cancel. Under
        # load the first 10ms tick can precede context_for(), which otherwise
        # tests startup scheduling rather than cancellation of an active run.
        await asyncio.wait_for(started.wait(), timeout=5)
        async with jobs.authority.engine.begin() as db:
            await db.execute(update(durable_jobs).where(durable_jobs.c.id == job.job_id).values(fencing_token=job.fencing_token + 1))
        return await heartbeat(jobs, job, worker_id, **kwargs)
    monkeypatch.setattr(PersonalJobs, "heartbeat", lost)
    await a.worker.run_one()
    assert started.is_set() and cancelled.is_set()
    assert await a.authority.jobs.list(a.context, "delivery") == []


@pytest.mark.asyncio
async def test_repair_after_saved_checkpoint_enqueues_same_outbox_without_model(automation, monkeypatch):
    from agentscope.app._service import _personal_jobs
    a = automation
    enqueue = _personal_jobs.enqueue_deliveries
    monkeypatch.setattr(_personal_jobs, "enqueue_deliveries", AsyncMock(side_effect=RuntimeError("crash after checkpoint")))
    await a.manager._build_trigger(a.record)()
    await a.worker.run_one()
    run = (await a.authority.jobs.list(a.context, "schedule-run"))[0]
    assert run.result["deliveries"] and not await a.authority.jobs.list(a.context, "delivery")
    monkeypatch.setattr(_personal_jobs, "enqueue_deliveries", enqueue)
    await _personal_jobs.repair_delivery(a.storage, "alice", "schedule-run", a.record.id, run.job_id)
    await _personal_jobs.repair_delivery(a.storage, "alice", "schedule-run", a.record.id, run.job_id)
    assert len(await a.authority.jobs.list(a.context, "delivery")) == 1
    await a.worker.run_one()
    assert len(a.calls) == len(a.deliveries) == 1
