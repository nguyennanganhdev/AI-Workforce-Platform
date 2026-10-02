"""Chat-completions model adapter for the graph's AsyncModel port.

Every Reception prompt asks for one JSON object, so the request pins JSON output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
from langchain_core.messages import SystemMessage


class ModelUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ModelConfig:
    model: str
    api_key: str = field(repr=False)
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 40.0

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
            content = response.json()["choices"][0]["message"]["content"]
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
                      "response_format": {"type": "json_object"}},
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelUnavailable("MODEL_UNAVAILABLE") from None
        if not isinstance(message, dict):
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        return message
