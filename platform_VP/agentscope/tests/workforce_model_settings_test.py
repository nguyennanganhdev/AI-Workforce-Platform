"""Per-role model settings: reasoning effort and the private-history cap."""

import os
from unittest import TestCase
from unittest.mock import patch

from agentscope.app._service._chat import _apply_reasoning_effort
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel


def _model() -> OpenAIChatModel:
    return OpenAIChatModel(credential=OpenAICredential(api_key="k"), model="gpt-5.4-mini")


class ReasoningEffortTest(TestCase):
    def test_chat_completions_models_never_get_an_effort(self) -> None:
        # OpenAI: "Function tools with reasoning_effort are not supported for
        # gpt-5.5 in /v1/chat/completions"; every agent here has tools.
        env = {"WORKFORCE_REASONING_EFFORT_LEADER": "low", "WORKFORCE_REASONING_EFFORT_AGENT": "low"}
        with patch.dict(os.environ, env):
            leader, member = _model(), _model()
            _apply_reasoning_effort(leader, "leader")
            _apply_reasoning_effort(member, "business")
        for model in (leader, member):
            self.assertEqual((False, None), (model.parameters.thinking_enable, model.parameters.reasoning_effort))

    def test_unset_keeps_the_provider_default(self) -> None:
        with patch.dict(os.environ, {"WORKFORCE_REASONING_EFFORT_AGENT": ""}):
            model = _model()
            _apply_reasoning_effort(model, "business")
        self.assertFalse(model.parameters.thinking_enable)
        self.assertIsNone(model.parameters.reasoning_effort)


class PrivateContextCapTest(TestCase):
    def test_a_huge_window_still_compresses_at_the_token_cap(self) -> None:
        from agentscope.app._service._chat import _private_context_ratio

        with patch.dict(os.environ, {"WORKFORCE_PRIVATE_CONTEXT_TOKENS": "16000"}):
            # gpt-5.5: 1,050,000 tokens; 80% would be 840k.
            self.assertAlmostEqual(16000 / 1_050_000, _private_context_ratio(1_050_000))
            # A small window keeps its own ratio limit.
            self.assertEqual(0.9, _private_context_ratio(8000))
        with patch.dict(os.environ, {"WORKFORCE_PRIVATE_CONTEXT_TOKENS": "0"}):
            self.assertEqual(0.9, _private_context_ratio(1_050_000))


class BackgroundTierTest(TestCase):
    def test_structured_calls_try_flex_then_fall_back(self) -> None:
        import asyncio

        from agentscope.app._service._chat import _background

        class Model:
            extra_body = {"prompt_cache_key": "k"}
            tiers: list = []

            async def generate_structured_output(self, **_):
                self.tiers.append((self.extra_body or {}).get("service_tier"))
                if (self.extra_body or {}).get("service_tier") == "flex":
                    error = RuntimeError("Resource Unavailable")
                    error.status_code = 429
                    raise error
                return "ok"

        model = Model()
        with patch.dict(os.environ, {"WORKFORCE_BACKGROUND_SERVICE_TIER": "flex"}):
            wrapped = _background(model)
        self.assertEqual("ok", asyncio.run(wrapped.generate_structured_output(messages=[])))
        self.assertEqual(["flex", None], model.tiers)
        self.assertEqual({"prompt_cache_key": "k"}, model.extra_body)  # restored
        with patch.dict(os.environ, {"WORKFORCE_BACKGROUND_SERVICE_TIER": ""}):
            self.assertIs(model, _background(model))

    def test_a_bad_output_is_not_retried_on_the_standard_tier(self) -> None:
        import asyncio

        from agentscope.app._service._chat import _background

        class Model:
            extra_body = None
            calls = 0

            async def generate_structured_output(self, **_):
                self.calls += 1
                raise ValueError("Failed to generate structured output")

        model = Model()
        with patch.dict(os.environ, {"WORKFORCE_BACKGROUND_SERVICE_TIER": "flex"}):
            wrapped = _background(model)
        with self.assertRaises(ValueError):
            asyncio.run(wrapped.generate_structured_output(messages=[]))
        self.assertEqual(1, model.calls)
