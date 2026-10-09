"""Model catalog: which models exist, their tier, price and how to build them.

The catalog is data. Prices are *not* invented here: a spec without prices is
recorded as unpriced and its cost shows as 0 with `priced=0` in the ledger, so
a missing price can never pass for a real zero. Fill prices in the YAML file
named by AWP_MODELS_FILE (see `models.example.yaml`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TIERS = ("cheap", "standard", "strong")

# provider -> (credential class name, env var holding the key, credential kwarg for the key)
_PROVIDERS: dict[str, tuple[str, str | None, str]] = {
    "openai": ("OpenAICredential", "OPENAI_API_KEY", "api_key"),
    "openai_compatible": ("OpenAICredential", None, "api_key"),
    "anthropic": ("AnthropicCredential", "ANTHROPIC_API_KEY", "api_key"),
    "dashscope": ("DashScopeCredential", "DASHSCOPE_API_KEY", "api_key"),
    "deepseek": ("DeepSeekCredential", "DEEPSEEK_API_KEY", "api_key"),
    "gemini": ("GeminiCredential", "GEMINI_API_KEY", "api_key"),
    "moonshot": ("MoonshotCredential", "MOONSHOT_API_KEY", "api_key"),
    "minimax": ("MiniMaxCredential", "MINIMAX_API_KEY", "api_key"),
    "volcengine": ("VolcengineCredential", "VOLCENGINE_API_KEY", "api_key"),
    "xai": ("XAICredential", "XAI_API_KEY", "api_key"),
    "ollama": ("OllamaCredential", "OLLAMA_HOST", "host"),
}
# Providers whose `input_tokens` already counts cached tokens (OpenAI-style).
# Anthropic reports cache reads/writes separately from `input_tokens`.
_INPUT_INCLUDES_CACHE = {"anthropic": False}


@dataclass
class ModelSpec:
    id: str
    provider: str
    model: str
    tier: str = "standard"
    base_url: str | None = None
    api_key_env: str | None = None
    context_size: int = 128000
    price_in: float | None = None  # USD per 1M input tokens
    price_out: float | None = None
    price_cache_read: float | None = None
    price_cache_write: float | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def priced(self) -> bool:
        return self.price_in is not None and self.price_out is not None

    @property
    def input_includes_cache(self) -> bool:
        return _INPUT_INCLUDES_CACHE.get(self.provider, True)

    def api_key(self, env: dict | None = None) -> str | None:
        e = os.environ if env is None else env
        name = self.api_key_env or _PROVIDERS[self.provider][1]
        return e.get(name) if name else None

    def available(self, env: dict | None = None) -> bool:
        # Ollama has no key; setting OLLAMA_HOST is the opt-in.
        return bool(self.api_key(env))

    def cost(self, input_tokens: int, output_tokens: int,
             cache_read: int = 0, cache_write: int = 0) -> float:
        if not self.priced:
            return 0.0
        plain_in = input_tokens - (cache_read + cache_write) if self.input_includes_cache else input_tokens
        plain_in = max(plain_in, 0)
        read_price = self.price_cache_read if self.price_cache_read is not None else self.price_in
        write_price = self.price_cache_write if self.price_cache_write is not None else self.price_in
        total = (plain_in * self.price_in + output_tokens * self.price_out
                 + cache_read * read_price + cache_write * write_price)
        return total / 1_000_000


class ModelCatalog:
    def __init__(self, specs: list[ModelSpec], env: dict | None = None) -> None:
        for s in specs:
            if s.provider not in _PROVIDERS:
                raise ValueError(f"unknown provider {s.provider!r} in model {s.id!r}")
            if s.tier not in TIERS:
                raise ValueError(f"unknown tier {s.tier!r} in model {s.id!r}")
        self.specs = {s.id: s for s in specs}
        self._env = env
        self._built: dict[str, Any] = {}

    @classmethod
    def load(cls, path: str | None, env: dict | None = None) -> "ModelCatalog":
        if path and Path(path).is_file():
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
            specs = [ModelSpec(**m) for m in raw.get("models", [])]
            return cls(specs, env)
        return cls([], env)

    def by_name(self, model: str) -> ModelSpec | None:
        for s in self.specs.values():
            if s.model == model:
                return s
        return None

    def pick(self, tier: str) -> ModelSpec | None:
        """First available model of the tier, else the nearest tier up, then down."""
        order = {"cheap": ("cheap", "standard", "strong"),
                 "standard": ("standard", "strong", "cheap"),
                 "strong": ("strong", "standard", "cheap")}[tier]
        for t in order:
            for s in self.specs.values():
                if s.tier == t and s.available(self._env):
                    return s
        return None

    def available(self) -> list[ModelSpec]:
        return [s for s in self.specs.values() if s.available(self._env)]

    def credential(self, spec: ModelSpec):
        """Build the AgentScope credential object for the spec."""
        from agentscope import credential as c

        cls_name, _env, field_name = _PROVIDERS[spec.provider]
        cls = getattr(c, cls_name)
        kwargs: dict[str, Any] = {"name": spec.id}
        if spec.provider == "ollama":
            kwargs["host"] = spec.base_url or spec.api_key(self._env)
        else:
            kwargs[field_name] = spec.api_key(self._env) or "unset"
            if spec.base_url:
                kwargs["base_url"] = spec.base_url
        return cls(**kwargs)

    def build(self, spec: ModelSpec):
        """A chat model instance for the spec (cached)."""
        if spec.id not in self._built:
            cred = self.credential(spec)
            model_cls = type(cred).get_chat_model_class()
            kwargs: dict[str, Any] = {"context_size": spec.context_size}
            if spec.parameters:
                kwargs["parameters"] = model_cls.Parameters(**spec.parameters)
            self._built[spec.id] = model_cls(credential=cred, model=spec.model, **kwargs)
        return self._built[spec.id]

    def credential_payload(self, spec: ModelSpec) -> dict:
        """Body for AgentScope's POST /credential/ (used when creating sessions)."""
        data = self.credential(spec).model_dump(mode="json")
        key = spec.api_key(self._env)
        if key and "api_key" in data:
            data["api_key"] = key
        data.pop("id", None)
        return {"data": data}

    def chat_config(self, spec: ModelSpec, credential_id: str) -> dict:
        return {"type": f"{spec.provider if spec.provider != 'openai_compatible' else 'openai'}_chat",
                "credential_id": credential_id, "model": spec.model,
                "parameters": dict(spec.parameters)}
