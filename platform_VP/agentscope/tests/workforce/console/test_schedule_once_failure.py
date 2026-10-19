"""Once semantics on the existing single-owner scheduler, without a provider."""
from unittest.mock import AsyncMock, patch

from service_scheduler_test import _SchedulerFireTestBase, _make_record


class TestOnceFailure(_SchedulerFireTestBase):
    async def test_dispatch_failure_consumes_once_and_stale_trigger_does_not_repeat(self):
        record = _make_record()
        record.data.once = True
        await self.storage.upsert_schedule(record.user_id, record)
        trigger = self.manager._build_trigger(record)
        with patch("agentscope.app._manager._scheduler._scheduler_manager.deliver_to_inbox",
                   new=AsyncMock(side_effect=RuntimeError("offline dispatch failed"))) as deliver:
            await trigger()
            current = await self.storage.get_schedule(record.user_id, record.id)
            assert not current.data.enabled
            assert current.data.last_fired_at is not None
            assert current.data.last_error == "RuntimeError"
            await trigger()
            assert deliver.await_count == 1
        assert len(await self.storage.list_sessions(record.user_id, record.agent_id)) == 1

    async def test_success_consumes_once_before_dispatch(self):
        record = _make_record()
        record.data.once = True
        await self.storage.upsert_schedule(record.user_id, record)

        async def inspect_persistence(*args, **kwargs):
            current = await self.storage.get_schedule(record.user_id, record.id)
            assert not current.data.enabled
            assert current.data.last_error == "DISPATCH_OUTCOME_PENDING"

        with patch("agentscope.app._manager._scheduler._scheduler_manager.deliver_to_inbox",
                   new=AsyncMock(side_effect=inspect_persistence)) as deliver:
            trigger = self.manager._build_trigger(record)
            await trigger()
            await trigger()
            assert deliver.await_count == 1
        current = await self.storage.get_schedule(record.user_id, record.id)
        assert current.data.last_error == ""

    async def test_failed_consume_never_dispatches(self):
        record = _make_record()
        record.data.once = True
        await self.storage.upsert_schedule(record.user_id, record)
        with patch.object(self.storage, "upsert_schedule", side_effect=RuntimeError("offline store failure")):
            with patch("agentscope.app._manager._scheduler._scheduler_manager.deliver_to_inbox",
                       new=AsyncMock()) as deliver:
                await self.manager._build_trigger(record)()
                deliver.assert_not_awaited()
        assert not await self.storage.list_sessions(record.user_id, record.agent_id)
