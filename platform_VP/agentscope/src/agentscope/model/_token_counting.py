"""Provider-aware local token counters used before model calls."""

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=64)
def _openai_encoding(model: str) -> tuple[Any, str]:
    """Resolve the model tokenizer, falling back explicitly for new aliases."""

    import tiktoken

    try:
        return tiktoken.encoding_for_model(model), f"tiktoken:{model}"
    except KeyError:
        # o200k_base is the current OpenAI-family general encoding.  The
        # strategy string exposes this fallback in persisted measurements;
        # it is never silently presented as a provider-exact billing count.
        return tiktoken.get_encoding("o200k_base"), "tiktoken:o200k_base-fallback"


def count_openai_text(model: str, text: str) -> int:
    """Count lexical tokens with the tokenizer selected for ``model``."""

    encoding, _strategy = _openai_encoding(model)
    return len(encoding.encode(text, disallowed_special=()))


def openai_token_counting_strategy(model: str) -> str:
    """Return the auditable tokenizer identity used by the local counter."""

    _encoding, strategy = _openai_encoding(model)
    return strategy


__all__ = ["count_openai_text", "openai_token_counting_strategy"]
