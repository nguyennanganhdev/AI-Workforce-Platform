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


class ResponsesApiTest(TestCase):
    def test_openai_uses_the_responses_api_unless_told_otherwise(self) -> None:
        from agentscope.model import OpenAIResponseModel

        with patch.dict(os.environ, {"OPENAI_CHAT_API": ""}):
            self.assertIs(OpenAIResponseModel, OpenAICredential.get_chat_model_class())
        with patch.dict(os.environ, {"OPENAI_CHAT_API": "chat_completions"}):
            self.assertIs(OpenAIChatModel, OpenAICredential.get_chat_model_class())

    def test_the_effort_reaches_reasoning_models_on_the_responses_api(self) -> None:
        from agentscope.model import OpenAIResponseModel

        credential = OpenAICredential(api_key="k")
        leader = OpenAIResponseModel(credential=credential, model="gpt-5.4-mini")
        old = OpenAIResponseModel(credential=credential, model="gpt-4o")
        with patch.dict(os.environ, {"WORKFORCE_REASONING_EFFORT_LEADER": "low"}):
            _apply_reasoning_effort(leader, "leader")
            _apply_reasoning_effort(old, "leader")
        self.assertEqual((True, "low"), (leader.parameters.thinking_enable, leader.parameters.reasoning_effort))
        self.assertEqual((False, None), (old.parameters.thinking_enable, old.parameters.reasoning_effort))


class LunaReasoningPolicyTest(TestCase):
    """Only gpt-6-luna is deployed: every purpose reasons on the Responses API
    at its role's effort, and Chat Completions keeps effort=none."""

    def _luna(self):
        from agentscope.model import OpenAIResponseModel

        return OpenAIResponseModel(credential=OpenAICredential(api_key="k"), model="gpt-6-luna")

    def test_role_defaults(self) -> None:
        from agentscope.app._service._model import apply_reasoning_effort

        env = {f"WORKFORCE_REASONING_EFFORT_{role}": "" for role in ("LEADER", "AGENT", "BUILDER", "JUDGE")}
        with patch.dict(os.environ, env):
            efforts = {}
            for role in ("leader", "agent", "builder", "judge"):
                model = self._luna()
                apply_reasoning_effort(model, role)
                efforts[role] = model.parameters.reasoning_effort
                self.assertTrue(model.parameters.thinking_enable)
        self.assertEqual({"leader": "medium", "agent": "low", "builder": "medium", "judge": "medium"}, efforts)

    def test_env_overrides_a_role(self) -> None:
        with patch.dict(os.environ, {"WORKFORCE_REASONING_EFFORT_LEADER": "high"}):
            model = self._luna()
            _apply_reasoning_effort(model, "leader")
        self.assertEqual("high", model.parameters.reasoning_effort)

    def test_judge_copy_leaves_the_agent_model_alone(self) -> None:
        from agentscope.app._service._chat import _background
        from agentscope.app._service._model import with_reasoning_effort

        with patch.dict(os.environ, {"WORKFORCE_REASONING_EFFORT_JUDGE": "", "WORKFORCE_REASONING_EFFORT_AGENT": "",
                                     "WORKFORCE_BACKGROUND_SERVICE_TIER": "flex"}):
            agent = with_reasoning_effort(self._luna(), "agent")
            judge = with_reasoning_effort(agent, "judge")
            wrapped = _background(agent)
            wrapped_judge = with_reasoning_effort(wrapped, "judge")
        self.assertEqual(("low", "medium"), (agent.parameters.reasoning_effort, judge.parameters.reasoning_effort))
        self.assertIs(agent.client, judge.client)
        self.assertEqual("low", wrapped._model.parameters.reasoning_effort)
        self.assertEqual("medium", wrapped_judge._model.parameters.reasoning_effort)

    def test_get_model_reasons_on_the_responses_api(self) -> None:
        import asyncio
        from types import SimpleNamespace

        from agentscope.app._service._model import get_model
        from agentscope.app.storage import ChatModelConfig
        from agentscope.model import OpenAIResponseModel

        class Access:
            async def resolve_credential(self, user_id, credential_id):
                return SimpleNamespace(data={"type": "openai_credential", "name": "x", "api_key": "k"})

        config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-6-luna", parameters={})
        env = {"WORKFORCE_MODEL_NAME": "gpt-6-luna", "WORKFORCE_REASONING_EFFORT_AGENT": "", "OPENAI_CHAT_API": "responses"}
        with patch.dict(os.environ, env):
            model = asyncio.run(get_model("u", config, Access()))
        self.assertIsInstance(model, OpenAIResponseModel)
        self.assertEqual((True, "low"), (model.parameters.thinking_enable, model.parameters.reasoning_effort))
        self.assertEqual(16384, model.parameters.max_tokens)
