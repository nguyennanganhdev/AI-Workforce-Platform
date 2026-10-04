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
