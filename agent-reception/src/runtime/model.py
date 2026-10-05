"""Chat-completions model adapter for the graph's AsyncModel port.

Every Reception prompt asks for one JSON object, so the request pins JSON output.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
from langchain_core.messages import SystemMessage


class ModelUnavailable(Exception):
    pass


# Token usage of the turn in progress. The model object is shared by concurrent turns, so the
# count lives in the turn's own context rather than on the model.
turn_usage: ContextVar[dict | None] = ContextVar("turn_usage", default=None)


def _count(payload: dict) -> None:
    usage, reported = turn_usage.get(), payload.get("usage")
    if usage is not None and isinstance(reported, dict):
        usage["input_tokens"] += int(reported.get("prompt_tokens") or 0)
        usage["output_tokens"] += int(reported.get("completion_tokens") or 0)
        usage["model_calls"] += 1

# Providers that speak the chat-completions API this runtime sends. Anthropic's own compatibility
# endpoint ignores `response_format`, so a JSON answer is not guaranteed there: for trials only.
PROVIDERS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com",
    "groq": "https://api.groq.com/openai/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


def model_endpoint(role: str, env=None) -> tuple[str, str, str]:
    """The provider, base URL and key of one role (RECEPTION, COORDINATION, ...).

    `<ROLE>_MODEL_PROVIDER` names the provider (default `openai`, or `custom` with its own URL),
    `<ROLE>_MODEL_API_KEY` its key and `<ROLE>_MODEL_BASE_URL` another address. The shared
    OPENAI_API_KEY / OPENAI_BASE_URL are only used for OpenAI: one vendor's key is never sent to
    another vendor's endpoint.
    """
    env = os.environ if env is None else env
    get = lambda name: (env.get(name) or "").strip()
    provider = get(f"{role}_MODEL_PROVIDER").lower() or "openai"
    if provider not in PROVIDERS and provider != "custom":
        raise ValueError(f"{role}_MODEL_PROVIDER must be one of {', '.join(PROVIDERS)} or custom")
    shared = provider == "openai"
    base = get(f"{role}_MODEL_BASE_URL") or (get("OPENAI_BASE_URL") if shared else "") or PROVIDERS.get(provider, "")
    if not base.startswith(("http://", "https://")):
        raise ValueError(f"{role}_MODEL_BASE_URL is required with {role}_MODEL_PROVIDER=custom")
    return provider, base, get(f"{role}_MODEL_API_KEY") or (get("OPENAI_API_KEY") if shared else "")


@dataclass(frozen=True)
class ModelConfig:
    model: str
    api_key: str = field(repr=False)
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 40.0
    provider: str = "openai"

    def __post_init__(self):
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("RECEPTION_MODEL and its API key are required")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Model base URL must be HTTP(S)")


class ChatCompletionsModel:
    def __init__(self, config: ModelConfig, client: httpx.AsyncClient):
        self.config, self.client = config, client

    async def ainvoke(self, messages):
        try:
            response = await self.client.post(
                self.config.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.config.api_key},
                timeout=self.config.timeout_seconds,
                json={
                    "model": self.config.model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system" if isinstance(message, SystemMessage) else "user",
                            "content": message.content,
                        }
                        for message in messages
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            _count(payload)
            content = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            # Never surface provider payloads or credentials to the graph.
            raise ModelUnavailable("MODEL_UNAVAILABLE") from None
        if not isinstance(content, str):
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        return SimpleNamespace(content=content)

    async def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        """One step of a tool-calling conversation; returns the assistant message as the provider gave it."""
        try:
            response = await self.client.post(
                self.config.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.config.api_key},
                timeout=self.config.timeout_seconds,
                json={"model": self.config.model, "messages": messages, "tools": tools,
                      "response_format": {"type": "json_object"},
                      # Luna only supports Chat Completions function calling without reasoning.
                      **({"reasoning_effort": "none"}
                         if self.config.provider == "openai" and self.config.model == "gpt-6-luna" else {})},
            )
            response.raise_for_status()
            payload = response.json()
            _count(payload)
            message = payload["choices"][0]["message"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelUnavailable("MODEL_UNAVAILABLE") from None
        if not isinstance(message, dict):
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        return message
