"""Which provider, address and key a role's model uses.

Each role names its own: the Supervisor's planner is COORDINATION, the specialists' Bot is
COORDINATION_OPENBOT (resolved by the launcher, which starts the Bot). Reception keeps the same
rule in agent-reception/src/runtime/model.py.
"""
import os

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
    """The provider, base URL and key of one role.

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


def output_limit(provider: str, tokens: int) -> dict:
    """OpenAI's current models refuse `max_tokens`; the other providers only know that name."""
    return {"max_completion_tokens" if provider == "openai" else "max_tokens": tokens}
