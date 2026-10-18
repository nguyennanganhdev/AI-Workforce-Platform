"""Reception on OpenAI's Responses API: it reasons, calls tools, and gets its own reasoning back."""
import asyncio
import json

import httpx

from src.runtime.model import ModelConfig, ResponsesModel, chat_model, turn_usage
from src.runtime.service import Settings

TOOL = {"type": "function", "function": {"name": "request_status", "description": "Xem tình trạng.",
                                         "parameters": {"type": "object", "properties": {}, "required": []}}}
REASONING = {"type": "reasoning", "id": "rs_1", "summary": []}
CALL = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "request_status", "arguments": "{}"}


def test_openai_defaults_to_the_responses_api_at_low_effort(monkeypatch):
    for name, value in {"RECEPTION_SERVICE_TOKEN": "x" * 32, "RECEPTION_BACKEND_URL": "http://backend",
                        "RECEPTION_MODEL": "gpt-6-luna", "OPENAI_API_KEY": "k"}.items():
        monkeypatch.setenv(name, value)
    for name in ("RECEPTION_MODEL_PROVIDER", "RECEPTION_MODEL_API", "RECEPTION_REASONING_EFFORT", "RECEPTION_MODEL_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    config = Settings.from_env().model
    assert (config.api, config.reasoning_effort) == ("responses", "low")
    monkeypatch.setenv("RECEPTION_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("RECEPTION_MODEL_API_KEY", "d")
    assert Settings.from_env().model.api == "chat"


def test_a_tool_step_then_the_answer_replays_the_reasoning_items():
    sent = []
    answers = iter([
        {"output": [REASONING, CALL], "usage": {"input_tokens": 100, "output_tokens": 30}},
        {"output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": '{"reply": "Yêu cầu đang được xử lý", "sources": []}'}]}],
         "usage": {"input_tokens": 140, "output_tokens": 12}},
    ])

    def provider(request: httpx.Request) -> httpx.Response:
        sent.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json=next(answers))

    async def turn():
        usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
        token = turn_usage.set(usage)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
                model = chat_model(ModelConfig(model="gpt-6-luna", api_key="k", api="responses"), client)
                assert isinstance(model, ResponsesModel)
                messages = [{"role": "system", "content": "Trả JSON."}, {"role": "user", "content": "Tiến độ sao rồi?"}]
                step = await model.complete(messages, [TOOL])
                messages.append({"role": "assistant", "content": step["content"], "tool_calls": step["tool_calls"],
                                 "_items": step["_items"]})
                messages.append({"role": "tool", "tool_call_id": "call_1", "content": '{"status": "đang xử lý"}'})
                final = await model.complete(messages, [TOOL])
                return step, final, usage
        finally:
            turn_usage.reset(token)

    step, final, usage = asyncio.run(turn())
    assert step["tool_calls"] == [{"id": "call_1", "type": "function",
                                   "function": {"name": "request_status", "arguments": "{}"}}]
    assert json.loads(final["content"])["reply"] == "Yêu cầu đang được xử lý"
    path, first = sent[0]
    assert path == "/v1/responses"
    assert first["reasoning"] == {"effort": "low"} and first["text"] == {"format": {"type": "json_object"}}
    assert first["tools"] == [{"type": "function", **TOOL["function"]}]
    assert first["input"] == [{"role": "system", "content": "Trả JSON."}, {"role": "user", "content": "Tiến độ sao rồi?"}]
    # The second request carries the model's reasoning and call items, then the call's output.
    assert sent[1][1]["input"][2:] == [REASONING, CALL, {"type": "function_call_output", "call_id": "call_1",
                                                         "output": '{"status": "đang xử lý"}'}]
    assert usage == {"input_tokens": 240, "output_tokens": 42, "model_calls": 2}


def test_an_effort_can_be_asked_for_one_step():
    sent = []

    def provider(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            await ResponsesModel(ModelConfig(model="gpt-6-luna", api_key="k", api="responses"), client).complete(
                [{"role": "user", "content": "x"}], [], effort="medium")

    asyncio.run(run())
    assert sent[0]["reasoning"] == {"effort": "medium"} and "tools" not in sent[0]


def test_a_broken_answer_is_model_unavailable_without_provider_details():
    import pytest
    from src.runtime.model import ModelUnavailable

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": "x"}))) as client:
            await ResponsesModel(ModelConfig(model="gpt-6-luna", api_key="k", api="responses"), client).complete([], [])

    with pytest.raises(ModelUnavailable, match="MODEL_UNAVAILABLE"):
        asyncio.run(run())
