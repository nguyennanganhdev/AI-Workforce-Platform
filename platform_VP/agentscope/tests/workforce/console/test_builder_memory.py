"""Measured, durable summary behavior for Agent Builder conversations."""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from fastapi import HTTPException

from agentscope.app._router._workforce_console import (
    _BUILDER_AGENT_ID,
    _BUILDER_MEMORY_KEY,
    _builder_structured_call,
    _BuilderMemorySummary,
    _prepare_builder_memory,
    _record_builder_prompt_measurement,
)
from agentscope.app.storage import ChatModelConfig, SessionConfig, SessionRecord
from agentscope.message import AssistantMsg, UserMsg


class _Storage:
    def __init__(self) -> None:
        self.states = []

    async def update_session_state(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        state: object,
    ) -> None:
        assert (user_id, agent_id, session_id) == (
            "u",
            _BUILDER_AGENT_ID,
            "builder-1",
        )
        self.states.append(state.model_copy(deep=True))


class _Model:
    def __init__(self, *, context_size: int = 5_000, fail: bool = False) -> None:
        self.context_size = context_size
        self.fail = fail
        self.summary_calls = 0
        self.ordinary_calls = 0

    async def count_tokens(self, messages: list, tools: object) -> int:
        text = "".join(message.get_text_content() or "" for message in messages)
        if tools:
            text += json.dumps(tools, ensure_ascii=False)
        return max(1, len(text.encode("utf-8")) // 4)

    async def generate_structured_output(self, messages: list, schema: type) -> object:
        if schema is _BuilderMemorySummary:
            self.summary_calls += 1
            if self.fail:
                raise RuntimeError("summary unavailable")
            payload = json.loads(messages[-1].get_text_content())
            source_ids = [item["message_id"] for item in payload["source_messages"]]
            if payload["previous_summary"]:
                source_ids.append("previous_summary")
            return SimpleNamespace(
                content={
                    "text": "Builder intent and accepted boundaries retained.",
                    "source_message_ids": source_ids,
                },
            )
        self.ordinary_calls += 1
        return SimpleNamespace(content={})


def _session() -> SessionRecord:
    return SessionRecord(
        id="builder-1",
        user_id="u",
        agent_id=_BUILDER_AGENT_ID,
        config=SessionConfig(
            workspace_id="builder-1",
            chat_model_config=ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="model-1",
                parameters={},
            ),
        ),
    )


def _messages() -> list:
    messages = []
    for index in range(30):
        cls = UserMsg if index % 2 == 0 else AssistantMsg
        messages.append(
            cls(
                id=f"builder-message-{index}",
                name="area_manager" if index % 2 == 0 else "agent_builder",
                content=f"builder-history-{index} " + ("detail " * 80),
            ),
        )
    return messages


class TestBuilderMemory(IsolatedAsyncioTestCase):
    async def test_summary_is_builder_local_measured_and_raw_safe(self) -> None:
        storage = _Storage()
        model = _Model()
        session = _session()
        messages = _messages()

        transcript = await _prepare_builder_memory(
            model=model,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            user_id="u",
            session=session,
            messages=messages,
            current="latest correction",
        )

        metadata = session.state.middle_context[_BUILDER_MEMORY_KEY]
        self.assertEqual(model.summary_calls, 1)
        self.assertEqual(metadata["compactions"], 1)
        self.assertGreater(metadata["last_summary_input_tokens"], 0)
        self.assertGreater(metadata["last_summary_output_tokens"], 0)
        self.assertLess(len(metadata["covered_message_ids"]), len(messages))
        self.assertEqual(len(messages), 30)
        self.assertIn("Builder intent and accepted boundaries", transcript)
        self.assertIn("latest correction", transcript)
        self.assertIn("builder-history-29", transcript)

    async def test_summary_failure_keeps_old_summary_and_full_history(self) -> None:
        storage = _Storage()
        model = _Model(fail=True)
        session = _session()
        session.state.summary = "previous safe Builder summary"
        messages = _messages()

        transcript = await _prepare_builder_memory(
            model=model,  # type: ignore[arg-type]
            storage=storage,  # type: ignore[arg-type]
            user_id="u",
            session=session,
            messages=messages,
            current="latest correction",
        )

        metadata = session.state.middle_context[_BUILDER_MEMORY_KEY]
        self.assertEqual(model.summary_calls, 2)
        self.assertEqual(metadata["compaction_failures"], 1)
        self.assertEqual(session.state.summary, "previous safe Builder summary")
        self.assertIn("builder-history-0", transcript)
        self.assertIn("builder-history-29", transcript)

    async def test_builder_prompt_budget_blocks_model_call(self) -> None:
        model = _Model(context_size=100)

        with self.assertRaises(HTTPException) as raised:
            await _builder_structured_call(
                model,  # type: ignore[arg-type]
                [UserMsg(name="area_manager", content="x" * 1_000)],
                _BuilderMemorySummary,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(model.ordinary_calls, 0)

    async def test_builder_prompt_budget_failure_is_auditable(self) -> None:
        storage = _Storage()
        session = _session()

        await _record_builder_prompt_measurement(
            storage,  # type: ignore[arg-type]
            "u",
            session,
            prompt_tokens=950,
            reserved_output_tokens=100,
            model_context_size=1_000,
            budget_exceeded=True,
        )

        metadata = session.state.middle_context[_BUILDER_MEMORY_KEY]
        self.assertEqual(metadata["model_calls_measured"], 1)
        self.assertEqual(metadata["prompt_budget_failures"], 1)
        self.assertEqual(metadata["last_prompt_tokens"], 950)
