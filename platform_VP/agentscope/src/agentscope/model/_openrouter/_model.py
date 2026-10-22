# -*- coding: utf-8 -*-
"""The OpenRouter chat model: OpenAI-compatible Chat Completions with a
model list read from OpenRouter itself, since it changes every week."""
import asyncio
import copy
import os
import time
from typing import Any, Literal

import httpx

from .._model_card import ModelCard
from .._openai_chat import OpenAIChatModel
from ..._logging import logger
from ...credential._openrouter import OPENROUTER_BASE_URL

# The picker shows the newest few tool-capable models of each major
# vendor; OpenRouter lists ~400, most of them unusable for agents.
_VENDORS = (
    "openai", "anthropic", "google", "deepseek", "qwen", "x-ai",
    "moonshotai", "z-ai", "minimax", "mistralai", "meta-llama",
)
_PER_VENDOR = 8
_CACHE_TTL = 3600
# Shown when OpenRouter cannot be reached and nothing is cached yet.
_FALLBACK = (
    ("openai/gpt-6.1-sol", "OpenAI: GPT-6.1 Sol"),
    ("anthropic/claude-sonnet-5.5", "Anthropic: Claude Sonnet 5.5"),
    ("google/gemini-3.8-flash", "Google: Gemini 3.8 Flash"),
    ("deepseek/deepseek-v4.1-flash", "DeepSeek: DeepSeek V4.1 Flash"),
    ("qwen/qwen3.8-flash", "Qwen: Qwen3.8 Flash"),
)

_cards: list[ModelCard] = []
_fetched_at = 0.0
_refresh_lock = asyncio.Lock()


def _input_types(modalities: list[str]) -> list[str]:
    types = ["text/plain"]
    if "image" in modalities:
        types += ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if "file" in modalities:
        types.append("application/pdf")
    return types


def _card(entry: dict) -> ModelCard:
    """A model card for one entry of OpenRouter's ``/models``."""
    supported = entry.get("supported_parameters") or []
    context = int(entry.get("context_length") or 0) or 128000
    output = int((entry.get("top_provider") or {}).get("max_completion_tokens") or 0)
    output = output or min(context, 16384)
    schema = OpenAIChatModel.Parameters.model_json_schema()
    properties = copy.deepcopy(schema.get("properties", {}))
    for name in ("thinking_enable", "voice"):
        properties.pop(name, None)
    if "reasoning_effort" not in supported and "reasoning" not in supported:
        properties.pop("reasoning_effort", None)
    if "max_tokens" in properties:
        properties["max_tokens"]["maximum"] = output
    return ModelCard(
        name=entry["id"],
        label=str(entry.get("name") or entry["id"]),
        status="active",
        input_types=_input_types((entry.get("architecture") or {}).get("input_modalities") or []),
        output_types=["text/plain"],
        context_size=context,
        output_size=output,
        parameter_schema={
            "type": "object",
            "properties": properties,
            "required": schema.get("required", []),
        },
        parameters_overrides={},
    )


def _pick(entries: list[dict]) -> list[ModelCard]:
    by_vendor: dict[str, list[dict]] = {}
    for entry in entries:
        model_id = str(entry.get("id") or "")
        vendor = model_id.split("/", 1)[0]
        if (
            vendor in _VENDORS
            and not model_id.endswith(":batch")
            and "tools" in (entry.get("supported_parameters") or [])
            and not entry.get("expiration_date")
        ):
            by_vendor.setdefault(vendor, []).append(entry)
    cards = []
    for vendor in _VENDORS:
        newest = sorted(by_vendor.get(vendor, []), key=lambda e: -float(e.get("created") or 0))
        for entry in newest[:_PER_VENDOR]:
            try:
                cards.append(_card(entry))
            except (ValueError, TypeError, KeyError) as exc:
                logger.debug("Skipping OpenRouter model %s: %s", entry.get("id"), exc)
    return cards


def _fallback_cards() -> list[ModelCard]:
    return [
        _card({"id": model_id, "name": label, "supported_parameters": ["tools"]})
        for model_id, label in _FALLBACK
    ]


class OpenRouterChatModel(OpenAIChatModel):
    """OpenAI Chat Completions against OpenRouter."""

    type: Literal["openrouter_chat"] = "openrouter_chat"
    """The type of the chat model."""

    def __init__(self, *args: Any, client_kwargs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        client_kwargs = dict(client_kwargs or {})
        # OpenRouter's app attribution headers.
        headers = {"X-Title": "AI Workforce Platform"}
        origin = os.getenv("PUBLIC_ORIGIN", "").strip()
        if origin:
            headers["HTTP-Referer"] = origin
        client_kwargs["default_headers"] = {**headers, **(client_kwargs.get("default_headers") or {})}
        super().__init__(*args, client_kwargs=client_kwargs, **kwargs)

    @classmethod
    def list_models(cls, custom_yaml_dir: str | None = None) -> list[ModelCard]:
        """The models from the last :meth:`refresh_models`, or a short
        built-in list before the first one succeeds."""
        return list(_cards) or _fallback_cards()

    @classmethod
    async def refresh_models(cls) -> None:
        """Re-read OpenRouter's model list when the cached one is older
        than an hour. A failure keeps the previous list."""
        global _cards, _fetched_at  # pylint: disable=global-statement
        if time.time() - _fetched_at < _CACHE_TTL:
            return
        async with _refresh_lock:
            if time.time() - _fetched_at < _CACHE_TTL:
                return
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(f"{OPENROUTER_BASE_URL}/models")
                response.raise_for_status()
                cards = _pick(response.json().get("data") or [])
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                logger.warning("Could not read OpenRouter's model list: %s", exc)
                # Retry in five minutes, not on every picker open.
                _fetched_at = time.time() - _CACHE_TTL + 300
                return
            if cards:
                _cards = cards
            _fetched_at = time.time()
