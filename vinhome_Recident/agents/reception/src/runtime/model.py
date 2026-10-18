"""Chat-completions model adapter for the graph's AsyncModel port.

Every Reception prompt asks for one JSON object, so the request pins JSON output.
"""

from __future__ import annotations

import asyncio
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
from langchain_core.messages import SystemMessage


# Before the one second try of a model request.
RETRY_SECONDS = 1.0


class ModelUnavailable(Exception):
    pass


# Token usage of the turn in progress. The model object is shared by concurrent turns, so the
# count lives in the turn's own context rather than on the model.
turn_usage: ContextVar[dict | None] = ContextVar("turn_usage", default=None)
turn_model_config: ContextVar[object | None] = ContextVar('turn_model_config', default=None)


def _count(payload: dict) -> None:
    usage, reported = turn_usage.get(), payload.get("usage")
    if usage is not None and isinstance(reported, dict):
        # Chat Completions names them prompt/completion tokens, the Responses API input/output tokens.
        usage["input_tokens"] += int(reported.get("prompt_tokens") or reported.get("input_tokens") or 0)
        usage["output_tokens"] += int(reported.get("completion_tokens") or reported.get("output_tokens") or 0)
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
    # "responses": OpenAI's Responses API, where a model reasons and calls tools in one step.
    # "chat": Chat Completions (other vendors; luna there only calls tools without reasoning).
    api: str = "chat"
    reasoning_effort: str = "low"

    def __post_init__(self):
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("RECEPTION_MODEL and its API key are required")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Model base URL must be HTTP(S)")
        if self.api not in ("chat", "responses"):
            raise ValueError("RECEPTION_MODEL_API must be chat or responses")


class ChatCompletionsModel:
    def __init__(self, config: ModelConfig, client: httpx.AsyncClient):
        self._deployment_config, self.client = config, client

    @property
    def config(self):
        return turn_model_config.get() or self._deployment_config

    async def _post(self, body: dict, path: str = "/chat/completions") -> httpx.Response:
        """One request, sent again once after a rate limit, a server error or a dropped connection."""
        for last in (False, True):
            try:
                response = await self.client.post(
                    self.config.base_url.rstrip("/") + path,
                    headers={"Authorization": "Bearer " + self.config.api_key},
                    timeout=self.config.timeout_seconds, json=body)
            except httpx.TransportError:
                if last:
                    raise
            else:
                if last or (response.status_code != 429 and response.status_code < 500):
                    return response
            await asyncio.sleep(RETRY_SECONDS)

    async def ainvoke(self, messages):
        try:
            response = await self._post({
                "model": self.config.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system" if isinstance(message, SystemMessage) else "user",
                        "content": message.content,
                    }
                    for message in messages
                ],
            })
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

    async def complete(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> dict:
        """One step of a tool-calling conversation; returns the assistant message as the provider gave it.

        `effort` is for the Responses API; Chat Completions has no reasoning with tools here.
        """
        try:
            response = await self._post({
                "model": self.config.model, "messages": messages, "tools": tools,
                "response_format": {"type": "json_object"},
                # Luna only supports Chat Completions function calling without reasoning.
                **({"reasoning_effort": "none"}
                   if self.config.provider == "openai" and self.config.model in {"gpt-5.6-luna", "gpt-6-luna"} else {})})
            response.raise_for_status()
            payload = response.json()
            _count(payload)
            message = payload["choices"][0]["message"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelUnavailable("MODEL_UNAVAILABLE") from None
        if not isinstance(message, dict):
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        return message


def _input_items(messages: list[dict]) -> list[dict]:
    """Chat-shaped messages as Responses API input items.

    An assistant step keeps the provider's own output items (its reasoning, then its calls):
    the API needs them back with the call results to go on reasoning.
    """
    items = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": message["content"]})
        elif role == "assistant" and message.get("_items"):
            items.extend(message["_items"])
        elif role == "assistant" and message.get("tool_calls"):
            if message.get("content"):
                items.append({"role": "assistant", "content": message["content"]})
            items.extend({"type": "function_call", "call_id": call["id"], "name": call["function"]["name"],
                          "arguments": call["function"]["arguments"]} for call in message["tool_calls"])
        else:
            items.append({"role": role, "content": message.get("content") or ""})
    return items


class ResponsesModel(ChatCompletionsModel):
    """The same port over OpenAI's Responses API, where the model reasons before it calls a tool."""

    def _body(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> dict:
        body = {"model": self.config.model, "input": _input_items(messages),
                "reasoning": {"effort": effort or self.config.reasoning_effort},
                "text": {"format": {"type": "json_object"}}}
        if tools:
            body["tools"] = [{"type": "function", **spec["function"]} for spec in tools]
        return body

    async def _respond(self, body: dict) -> dict:
        try:
            response = await self._post(body, "/responses")
            response.raise_for_status()
            payload = response.json()
            _count(payload)
            output = payload["output"]
            if not isinstance(output, list):
                raise TypeError
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelUnavailable("MODEL_UNAVAILABLE") from None
        text = "".join(part.get("text") or "" for item in output if item.get("type") == "message"
                       for part in item.get("content") or [] if part.get("type") == "output_text")
        calls = [{"id": item["call_id"], "type": "function",
                  "function": {"name": item["name"], "arguments": item.get("arguments") or "{}"}}
                 for item in output if item.get("type") == "function_call"]
        return {"role": "assistant", "content": text or None, **({"tool_calls": calls} if calls else {}), "_items": output}

    async def complete(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> dict:
        return await self._respond(self._body(messages, tools, effort))

    async def ainvoke(self, messages):
        answer = await self._respond(self._body([
            {"role": "system" if isinstance(message, SystemMessage) else "user", "content": message.content}
            for message in messages], []))
        if not isinstance(answer["content"], str):
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        return SimpleNamespace(content=answer["content"])


def chat_model(config: ModelConfig, client: httpx.AsyncClient) -> ChatCompletionsModel:
    return (ResponsesModel if config.api == "responses" else ChatCompletionsModel)(config, client)
