# -*- coding: utf-8 -*-
"""Discord for Workforce: who may approve, secrets at rest, runnable targets.

No Discord connection is opened; interactions and storage are in-process fakes.
"""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

from agentscope.app._service._runnable_agents import ensure_runnable
from agentscope.app.channel import ChannelTypeRegistry, DiscordChannel
from agentscope.app.channel import _secrets as secrets

KEY = "k" * 40


def channel(approvers=()):
    return DiscordChannel(
        "channel-1",
        DiscordChannel.Credentials(bot_token="token", application_id="app"),
        DiscordChannel.Config(approver_user_ids=list(approvers)),
    )


def interaction(user_id):
    return SimpleNamespace(
        user=SimpleNamespace(id=int(user_id)), channel_id=7,
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
        message=SimpleNamespace(edit=AsyncMock()),
    )


class ApprovalTest(IsolatedAsyncioTestCase):
    def test_only_the_requester_or_an_approver_may_decide(self) -> None:
        value = channel(approvers=["300"])
        self.assertTrue(value.may_decide("100", "100"))
        self.assertTrue(value.may_decide("300", "100"))
        self.assertFalse(value.may_decide("200", "100"))
        self.assertFalse(value.may_decide("200", ""))
        self.assertFalse(value.may_decide("", ""))

    async def test_a_strangers_click_is_answered_privately_and_not_emitted(self) -> None:
        value = channel()
        value._emit = AsyncMock()
        click = interaction("200")
        await value._decide(click, "call-1", True, "agent", "session", "100")
        click.response.send_message.assert_awaited_once()
        self.assertTrue(click.response.send_message.await_args.kwargs["ephemeral"])
        value._emit.assert_not_awaited()

        click = interaction("100")
        await value._decide(click, "call-1", True, "agent", "session", "100")
        value._emit.assert_awaited_once()
        self.assertEqual(value._emit.await_args.args[0].tool_call_id, "call-1")


class SecretsTest(TestCase):
    def setUp(self) -> None:
        import os
        self._saved = {k: os.environ.pop(k, None) for k in ("CHANNEL_CREDENTIALS_KEY", "PARTNER_API_KEY_PEPPER")}

    def tearDown(self) -> None:
        import os
        for key, value in self._saved.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def test_bot_token_is_sealed_at_rest_and_opened_for_the_adapter(self) -> None:
        import os
        os.environ["CHANNEL_CREDENTIALS_KEY"] = KEY
        registry = ChannelTypeRegistry([DiscordChannel])
        stored = registry.seal_credentials("discord", {"bot_token": "secret-token", "application_id": "app"})
        self.assertTrue(stored["bot_token"].startswith(secrets.PREFIX))
        self.assertNotIn("secret-token", stored["bot_token"])
        self.assertEqual(stored["application_id"], "app", "the bot id stays readable for the uniqueness index")
        built = registry.create_channel("discord", "c1", stored, {})
        self.assertEqual(built._bot_token, "secret-token")

    def test_without_a_key_values_are_kept_and_legacy_plaintext_still_works(self) -> None:
        registry = ChannelTypeRegistry([DiscordChannel])
        stored = registry.seal_credentials("discord", {"bot_token": "plain", "application_id": "app"})
        self.assertEqual(stored["bot_token"], "plain")
        self.assertEqual(registry.create_channel("discord", "c1", stored, {})._bot_token, "plain")

    def test_sealed_value_without_its_key_fails_loudly(self) -> None:
        import os
        os.environ["CHANNEL_CREDENTIALS_KEY"] = KEY
        stored = ChannelTypeRegistry([DiscordChannel]).seal_credentials("discord", {"bot_token": "t", "application_id": "a"})
        del os.environ["CHANNEL_CREDENTIALS_KEY"]
        with self.assertRaises(RuntimeError):
            secrets.open_credentials(stored)


class RunnableTargetTest(IsolatedAsyncioTestCase):
    async def test_only_the_leader_or_a_published_agent_is_runnable(self) -> None:
        def agent(role, state):
            return SimpleNamespace(data=SimpleNamespace(name="A", system_role=role, lifecycle_state=state))

        for role, state, allowed in (("leader", "draft", True), ("business", "published", True),
                                     ("business", "draft", False), ("business", "withdrawn", False)):
            storage = SimpleNamespace(get_agent=AsyncMock(return_value=agent(role, state)))
            if allowed:
                await ensure_runnable(storage, "u", "a")
            else:
                with self.assertRaises(HTTPException) as ctx:
                    await ensure_runnable(storage, "u", "a")
                self.assertEqual(ctx.exception.status_code, 400)
        with self.assertRaises(HTTPException) as ctx:
            await ensure_runnable(SimpleNamespace(get_agent=AsyncMock(return_value=None)), "u", "a")
        self.assertEqual(ctx.exception.status_code, 404)
