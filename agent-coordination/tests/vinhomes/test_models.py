"""Each role's model has its own provider, address and key; one vendor's key never reaches another."""
import json
from types import SimpleNamespace

import httpx
import pytest

from adapters.backend.errors import AdapterError
from vinhomes import ports
from vinhomes.models import PROVIDERS, model_endpoint, output_limit
from vinhomes.ports import PlannerModel
from vinhomes.runtime import Settings

SHARED = {"OPENAI_API_KEY": "openai-key", "OPENAI_BASE_URL": "https://proxy.example/v1"}


def test_a_role_without_settings_of_its_own_uses_openai_and_the_shared_key():
    assert model_endpoint("COORDINATION", {"OPENAI_API_KEY": "openai-key"}) == ("openai", PROVIDERS["openai"], "openai-key")
    assert model_endpoint("COORDINATION", SHARED) == ("openai", "https://proxy.example/v1", "openai-key")
    assert output_limit("openai", 9) == {"max_completion_tokens": 9}


def test_another_vendor_gets_its_own_address_and_never_the_openai_key():
    env = {**SHARED, "COORDINATION_MODEL_PROVIDER": "Google"}
    assert model_endpoint("COORDINATION", env) == ("google", PROVIDERS["google"], "")
    env["COORDINATION_MODEL_API_KEY"] = "gemini-key"
    assert model_endpoint("COORDINATION", env) == ("google", PROVIDERS["google"], "gemini-key")
    # Another role in the same process is not affected.
    assert model_endpoint("RECEPTION", env) == ("openai", "https://proxy.example/v1", "openai-key")
    assert output_limit("google", 9) == {"max_tokens": 9}


def test_a_custom_endpoint_needs_its_address_and_an_unknown_vendor_is_refused():
    with pytest.raises(ValueError, match="COORDINATION_MODEL_BASE_URL"):
        model_endpoint("COORDINATION", {**SHARED, "COORDINATION_MODEL_PROVIDER": "custom"})
    env = {"COORDINATION_MODEL_PROVIDER": "custom", "COORDINATION_MODEL_BASE_URL": "http://127.0.0.1:11434/v1"}
    assert model_endpoint("COORDINATION", env) == ("custom", "http://127.0.0.1:11434/v1", "")
    with pytest.raises(ValueError, match="COORDINATION_MODEL_PROVIDER"):
        model_endpoint("COORDINATION", {"COORDINATION_MODEL_PROVIDER": "acme"})


def test_the_supervisor_refuses_to_start_a_planner_without_that_vendors_key(monkeypatch):
    for name, value in {"COORDINATION_BACKEND_URL": "http://backend", "COORDINATION_SERVICE_TOKEN": "x" * 32,
                        "COORDINATION_MODEL": "deepseek-flash", "COORDINATION_OPENBOT_URL": "http://127.0.0.1:4200/ag-ui",
                        "MANAGED_AGENT_TOKEN": "bot-token", "OPENAI_API_KEY": "openai-key",
                        "COORDINATION_MODEL_PROVIDER": "deepseek"}.items():
        monkeypatch.setenv(name, value)
    for name in ("COORDINATION_MODEL_API_KEY", "COORDINATION_MODEL_BASE_URL", "OPENAI_BASE_URL", "COORDINATION_MODEL_ANSWERS_AS"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="COORDINATION_MODEL_API_KEY"):
        Settings.from_env()
    monkeypatch.setenv("COORDINATION_MODEL_API_KEY", "deepseek-key")
    settings = Settings.from_env()
    assert (settings.model_provider, settings.model_base_url, settings.model_key) == ("deepseek", PROVIDERS["deepseek"], "deepseek-key")
    assert "deepseek-key" not in repr(settings)


class Budget:
    def for_scope(self, context):
        return self

    async def reserve(self, call, tokens): pass
    async def reconcile(self, call, tokens): pass
    async def retain_unknown(self, call): pass


PROMPT = {"catalog": {"version-1": {}}, "state": {"room": {"tasks": []}, "context": {}}}


async def ask(monkeypatch, *, echo, **options):
    monkeypatch.setattr(ports, "Context", SimpleNamespace(model_validate=lambda value: value))
    seen = []

    def provider(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(200, json={"model": echo, "usage": {"total_tokens": 10},
                                         "choices": [{"message": {"content": '{"kind": "pause", "reason": "x"}'}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        answer = await PlannerModel(Budget(), client, **options).generate(PROMPT)
    return answer, seen


async def test_the_planner_speaks_to_another_vendor_with_its_key_and_its_token_field(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    answer, seen = await ask(monkeypatch, echo="gemini-3.8-flash", model="gemini-3.8-flash", base_url=PROVIDERS["google"],
                             key="gemini-key", provider="google")
    url, authorization, body = seen[0]
    assert url == PROVIDERS["google"] + "/chat/completions" and authorization == "Bearer gemini-key"
    assert body["max_tokens"] == 2048 and "max_completion_tokens" not in body and json.loads(answer)["kind"] == "pause"


async def test_a_vendor_that_answers_under_another_name_is_refused_unless_that_name_is_declared(monkeypatch):
    options = dict(model="deepseek-flash", base_url=PROVIDERS["deepseek"], key="deepseek-key", provider="deepseek")
    with pytest.raises(AdapterError):
        await ask(monkeypatch, echo="deepseek-v4.1-flash", **options)
    answer, _ = await ask(monkeypatch, echo="deepseek-v4.1-flash", answers_as="deepseek-v4", **options)
    assert json.loads(answer)["kind"] == "pause"
