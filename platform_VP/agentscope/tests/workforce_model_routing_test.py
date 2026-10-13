"""Leader model override and opt-in prompt cache key."""

from types import SimpleNamespace

import pytest

from agentscope.app._service._chat import _apply_prompt_cache_key, _role_model_config
from agentscope.app.storage import ChatModelConfig


def _config() -> ChatModelConfig:
    return ChatModelConfig(
        type="openai_credential",
        credential_id="cred",
        model="gpt-mini",
        parameters={},
    )


def test_leader_uses_configured_strong_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFORCE_LEADER_MODEL_NAME", "gpt-strong")

    assert _role_model_config(_config(), "leader").model == "gpt-strong"
    assert _role_model_config(_config(), "business").model == "gpt-mini"


def test_without_override_every_role_keeps_session_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKFORCE_LEADER_MODEL_NAME", raising=False)

    assert _role_model_config(_config(), "leader").model == "gpt-mini"


def test_prompt_cache_key_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    model = SimpleNamespace(extra_body={"keep": 1})
    monkeypatch.delenv("WORKFORCE_PROMPT_CACHE_KEY", raising=False)
    _apply_prompt_cache_key(model, "agent-1")
    assert model.extra_body == {"keep": 1}

    monkeypatch.setenv("WORKFORCE_PROMPT_CACHE_KEY", "true")
    _apply_prompt_cache_key(model, "agent-1")
    assert model.extra_body == {"keep": 1, "prompt_cache_key": "workforce:agent-1"}
