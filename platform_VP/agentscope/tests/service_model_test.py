# -*- coding: utf-8 -*-
"""Unit tests for :func:`get_model` — the chat model factory."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from agentscope.app._service._model import get_model
from agentscope.app.storage import ChatModelConfig
from agentscope.model import OpenAIChatModel, OpenAIResponseModel

_CREDENTIAL = {"type": "deepseek_credential", "api_key": "test"}


class GetModelContextSizeTest(IsolatedAsyncioTestCase):
    """The factory must forward the model card's ``context_size``."""

    async def test_uses_card_context_size(self) -> None:
        """A matching card's value wins over the class default."""
        access = MagicMock(
            resolve_credential=AsyncMock(
                return_value=SimpleNamespace(data=_CREDENTIAL),
            ),
        )

        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="deepseek",
                credential_id="cred-1",
                model="deepseek-v4-flash",
                parameters={},
            ),
            access,
        )

        self.assertEqual(1000000, model.context_size)

    async def test_keeps_default_for_unknown_model(self) -> None:
        """A model without a card keeps the constructor default."""
        access = MagicMock(
            resolve_credential=AsyncMock(
                return_value=SimpleNamespace(data=_CREDENTIAL),
            ),
        )

        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="deepseek",
                credential_id="cred-1",
                model="my-custom-model",
                parameters={},
            ),
            access,
        )

        self.assertEqual(65536, model.context_size)

    async def test_routes_gpt6_to_responses_for_tool_support(self) -> None:
        """Current GPT-6 agents use the endpoint that supports their tools."""
        access = MagicMock(
            resolve_credential=AsyncMock(
                return_value=SimpleNamespace(
                    data={"type": "openai_credential", "api_key": "test"},
                ),
            ),
        )

        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_credential",
                credential_id="cred-1",
                model="gpt-6.1-sol",
                parameters={"reasoning_effort": "high"},
            ),
            access,
        )

        self.assertIsInstance(model, OpenAIResponseModel)
        self.assertEqual(1_050_000, model.context_size)
        self.assertEqual("high", model.parameters.reasoning_effort)

        pro_model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_credential",
                credential_id="cred-1",
                model="gpt-5.5-pro",
                parameters={},
            ),
            access,
        )
        self.assertIsInstance(pro_model, OpenAIResponseModel)
        self.assertFalse(pro_model.stream)

    async def test_keeps_pre_gpt6_models_on_chat_completions(self) -> None:
        access = MagicMock(
            resolve_credential=AsyncMock(
                return_value=SimpleNamespace(
                    data={"type": "openai_credential", "api_key": "test"},
                ),
            ),
        )

        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_credential",
                credential_id="cred-1",
                model="gpt-5.6-luna",
                parameters={},
            ),
            access,
        )

        self.assertIsInstance(model, OpenAIChatModel)

    def test_lists_current_openai_agent_models(self) -> None:
        names = {card.name for card in OpenAIChatModel.list_models()}

        self.assertTrue(
            {
                "gpt-6-astra",
                "gpt-6.1-sol",
                "gpt-6-sol",
                "gpt-6-luna",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "gpt-5.6-luna",
                "gpt-5.5-pro",
                "gpt-5.5",
                "gpt-5.4-pro",
                "gpt-5.4",
                "gpt-5.4-mini",
                "gpt-5.2-pro",
                "gpt-5.2",
            }.issubset(names),
        )
        self.assertNotIn("gpt-6.1-luna", names)
