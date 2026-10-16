"""GPT-6 Luna catalog, routing and reasoning request regressions."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from agentscope.app._service._model import get_model
from agentscope.app.storage import ChatModelConfig
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel, OpenAIResponseModel


EFFORTS = ["none", "low", "medium", "high", "xhigh", "max"]
TOOLS = [{
    "type": "function",
    "function": {
        "name": "probe",
        "parameters": {"type": "object", "properties": {}},
    },
}]


class TestOpenAILuna(IsolatedAsyncioTestCase):
    async def _model(self, name="gpt-6-luna", **parameters):
        return await get_model(
            "user",
            ChatModelConfig(
                type="openai_credential", credential_id="credential",
                model=name, parameters=parameters,
            ),
            SimpleNamespace(resolve_credential=AsyncMock(
                return_value=SimpleNamespace(data={
                    "type": "openai_credential", "api_key": "test",
                }),
            )),
        )

    def _mock_api(self, model):
        model.stream = False
        model.client = MagicMock()
        model.client.responses.create = AsyncMock(return_value=object())
        model.client.chat.completions.create = AsyncMock(return_value=object())
        model._parse_completion_response = MagicMock(return_value=object())

    def test_catalog_exposes_only_supported_efforts(self):
        for model_cls in (OpenAIChatModel, OpenAIResponseModel):
            with self.subTest(model_cls=model_cls):
                card = next(c for c in model_cls.list_models() if c.name == "gpt-6-luna")
                properties = card.parameter_schema["properties"]
                self.assertEqual(properties["reasoning_effort"]["enum"], EFFORTS)
                self.assertEqual(properties["reasoning_effort"]["default"], "medium")
                self.assertNotIn("thinking_enable", properties)
                self.assertEqual(card.context_size, 1_050_000)
                self.assertEqual(card.output_size, 128_000)

    async def test_luna_routes_all_efforts_to_responses_with_tools(self):
        for effort in EFFORTS:
            with self.subTest(effort=effort):
                model = await self._model(
                    reasoning_effort=effort, thinking_enable=False,
                    parallel_tool_calls=False,
                )
                self.assertIsInstance(model, OpenAIResponseModel)
                self.assertEqual(model.context_size, 1_050_000)
                self._mock_api(model)
                await model._call_api("gpt-6-luna", [], tools=TOOLS)
                kwargs = model.client.responses.create.call_args.kwargs
                self.assertEqual(kwargs["reasoning"], {"effort": effort})
                self.assertEqual(kwargs["tools"][0]["name"], "probe")
                self.assertFalse(kwargs["parallel_tool_calls"])
                model.client.chat.completions.create.assert_not_awaited()

    async def test_luna_reasoning_removes_incompatible_sampling(self):
        for effort in (None, "low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort):
                model = await self._model(
                    reasoning_effort=effort, temperature=0.4, top_p=0.8,
                )
                self._mock_api(model)
                await model._call_api(
                    "gpt-6-luna", [], top_logprobs=5,
                    include=["message.output_text.logprobs", "reasoning.encrypted_content"],
                )
                kwargs = model.client.responses.create.call_args.kwargs
                for key in ("temperature", "top_p", "top_logprobs"):
                    self.assertNotIn(key, kwargs)
                self.assertEqual(kwargs["include"], ["reasoning.encrypted_content"])

    async def test_luna_none_keeps_sampling(self):
        model = await self._model(reasoning_effort="none", temperature=0.4, top_p=0.8)
        self._mock_api(model)
        await model._call_api("gpt-6-luna", [])
        kwargs = model.client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["reasoning"], {"effort": "none"})
        self.assertEqual(kwargs["temperature"], 0.4)
        self.assertEqual(kwargs["top_p"], 0.8)

    async def test_luna_rejects_unsupported_effort_before_api_call(self):
        for effort in ("minimal", "ultra", "invalid"):
            with self.subTest(effort=effort), self.assertRaises(HTTPException) as error:
                await self._model(reasoning_effort=effort)
            self.assertEqual(error.exception.status_code, 422)

    async def test_other_openai_models_keep_chat_routing(self):
        for name in ("gpt-4o", "custom-model"):
            model = await self._model(name)
            self.assertIsInstance(model, OpenAIChatModel)

    async def test_chat_forwards_explicit_effort_without_thinking_toggle(self):
        for effort in EFFORTS:
            with self.subTest(effort=effort):
                model = OpenAIChatModel(
                    OpenAICredential(api_key="test"), "gpt-6-luna",
                    parameters=OpenAIChatModel.Parameters(reasoning_effort=effort),
                )
                self._mock_api(model)
                await model._call_api("gpt-6-luna", [])
                kwargs = model.client.chat.completions.create.call_args.kwargs
                self.assertEqual(kwargs["reasoning_effort"], effort)
