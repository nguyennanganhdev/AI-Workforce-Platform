"""Reception's model has its own provider, address and key; the OpenAI key stays with OpenAI."""
import asyncio
import json

import httpx
import pytest

from src.runtime.model import PROVIDERS, ChatCompletionsModel, model_endpoint
from src.runtime.service import Settings

BASE = {"RECEPTION_SERVICE_TOKEN": "x" * 32, "RECEPTION_BACKEND_URL": "http://backend", "RECEPTION_MODEL": "gemini-3.8-flash",
        "OPENAI_API_KEY": "openai-key"}
OWN = ("RECEPTION_MODEL_PROVIDER", "RECEPTION_MODEL_API_KEY", "RECEPTION_MODEL_BASE_URL", "OPENAI_BASE_URL")


def environment(monkeypatch, **values):
    for name in OWN:
        monkeypatch.delenv(name, raising=False)
    for name, value in {**BASE, **values}.items():
        monkeypatch.setenv(name, value)


def test_without_settings_of_its_own_reception_uses_openai_and_the_shared_key(monkeypatch):
    environment(monkeypatch)
    model = Settings.from_env().model
    assert (model.provider, model.base_url, model.api_key) == ("openai", PROVIDERS["openai"], "openai-key")


def test_another_vendor_needs_its_own_key_and_never_gets_the_openai_key(monkeypatch):
    environment(monkeypatch, RECEPTION_MODEL_PROVIDER="google")
    with pytest.raises(ValueError):
        Settings.from_env()
    environment(monkeypatch, RECEPTION_MODEL_PROVIDER="google", RECEPTION_MODEL_API_KEY="gemini-key")
    model = Settings.from_env().model
    assert (model.provider, model.base_url, model.api_key) == ("google", PROVIDERS["google"], "gemini-key")
    assert "gemini-key" not in repr(model)


def test_a_custom_endpoint_needs_its_address_and_an_unknown_vendor_is_refused():
    with pytest.raises(ValueError, match="RECEPTION_MODEL_BASE_URL"):
        model_endpoint("RECEPTION", {"RECEPTION_MODEL_PROVIDER": "custom", "OPENAI_BASE_URL": "https://proxy.example/v1"})
    with pytest.raises(ValueError, match="RECEPTION_MODEL_PROVIDER"):
        model_endpoint("RECEPTION", {"RECEPTION_MODEL_PROVIDER": "acme"})


def test_the_tool_step_goes_to_the_configured_vendor_with_its_key(monkeypatch):
    environment(monkeypatch, RECEPTION_MODEL_PROVIDER="deepseek", RECEPTION_MODEL_API_KEY="deepseek-key", RECEPTION_MODEL="deepseek-flash")
    seen = []

    def provider(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers["authorization"], json.loads(request.content)["model"]))
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "{}"}}]})

    async def turn():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            await ChatCompletionsModel(Settings.from_env().model, client).complete([{"role": "user", "content": "xin chào"}], [])

    asyncio.run(turn())
    assert seen == [(PROVIDERS["deepseek"] + "/chat/completions", "Bearer deepseek-key", "deepseek-flash")]


def test_registered_model_is_isolated_per_concurrent_turn_and_resets():
    from src.runtime.model import ModelConfig, turn_model_config
    seen = []
    def provider(request):
        seen.append((str(request.url), request.headers['authorization'], json.loads(request.content)['model']))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{}'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            model = ChatCompletionsModel(ModelConfig(model='deployment',api_key='deployment-key'),client)
            async def turn(name):
                token = turn_model_config.set(ModelConfig(model=name,api_key=name+'-key',base_url='https://'+name+'.example/v1',provider='custom'))
                try:
                    await asyncio.sleep(0)
                    await model.complete([{'role':'user','content':'hello'}],[])
                finally:
                    turn_model_config.reset(token)
            await asyncio.gather(turn('first'),turn('second'))
            await model.complete([{'role':'user','content':'hello'}],[])
            assert turn_model_config.get() is None
    asyncio.run(run())
    assert sorted(seen) == sorted([
        ('https://first.example/v1/chat/completions','Bearer first-key','first'),
        ('https://second.example/v1/chat/completions','Bearer second-key','second'),
        ('https://api.openai.com/v1/chat/completions','Bearer deployment-key','deployment'),
    ])


def test_luna_can_call_a_tool_with_chat_completions(monkeypatch):
    environment(monkeypatch, RECEPTION_MODEL="gpt-6-luna")

    def provider(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # Luna's Chat Completions API refuses function calling at its default reasoning effort.
        if body.get("tools") and body.get("reasoning_effort") != "none":
            return httpx.Response(400, json={"error": {"param": "reasoning_effort"}})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None,
            "tool_calls": [{"id": "read-1", "type": "function", "function": {"name": "test_read", "arguments": "{}"}}]}}]})

    async def turn():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            reply = await ChatCompletionsModel(Settings.from_env().model, client).complete(
                [{"role": "user", "content": "Read the test value."}],
                [{"type": "function", "function": {"name": "test_read", "parameters": {"type": "object", "properties": {}}}}],
            )
            assert reply["tool_calls"][0]["function"]["name"] == "test_read"

    asyncio.run(turn())


def test_a_rate_limit_or_a_server_error_is_tried_once_more_and_no_longer(monkeypatch):
    import src.runtime.model as model_module
    from src.runtime.model import ModelConfig, ModelUnavailable

    monkeypatch.setattr(model_module, "RETRY_SECONDS", 0)
    answer = {"choices": [{"message": {"role": "assistant", "content": "{}"}}]}

    def scripted(*statuses):
        left = list(statuses)

        def handler(request):
            status = left.pop(0)
            return httpx.Response(status, json=answer if status == 200 else {"error": "x"})

        return handler, left

    async def complete(*statuses):
        handler, left = scripted(*statuses)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = ModelConfig(model="m", api_key="k", base_url="https://model.test/v1")
            try:
                return await ChatCompletionsModel(config, client).complete([{"role": "user", "content": "x"}], []), left
            except ModelUnavailable:
                return None, left

    assert asyncio.run(complete(429, 200)) == (answer["choices"][0]["message"], [])
    assert asyncio.run(complete(503, 200))[0] is not None
    # Twice in a row: the turn fails rather than keeping the resident waiting.
    assert asyncio.run(complete(429, 429, 200)) == (None, [200])
    # A refused key is not retried.
    assert asyncio.run(complete(401, 200)) == (None, [200])
