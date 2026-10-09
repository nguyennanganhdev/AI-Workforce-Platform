"""Only catalog-approved native AgentScope adapters. No global provider environment mutation."""

import inspect

from .security import decrypt


def create_model(spec: dict, encrypted_secret: str = ""):
    from agentscope import credential as credentials
    from agentscope import model as models

    key = decrypt(encrypted_secret) if encrypted_secret else ""
    common = {
        "model": spec["model"],
        "stream": False,
        "max_retries": 0,
        "context_size": spec["context_tokens"],
    }
    adapter = spec["adapter"]
    base_url = spec.get("base_url") or None
    timeout = {"max_retries": 0, "timeout": 60.0}
    if adapter in {"openai", "openai-responses"}:
        cls = models.OpenAIChatModel if adapter == "openai" else models.OpenAIResponseModel
        return cls(
            **common,
            credential=credentials.OpenAICredential(api_key=key or "local", base_url=base_url),
            parameters=cls.Parameters(max_tokens=spec["max_output_tokens"]),
            client_kwargs=timeout,
        )
    if adapter == "anthropic":
        cls = models.AnthropicChatModel
        return cls(
            **common,
            credential=credentials.AnthropicCredential(api_key=key, base_url=base_url),
            parameters=cls.Parameters(max_tokens=spec["max_output_tokens"]),
            client_kwargs=timeout,
        )
    if adapter == "dashscope":
        cls = models.DashScopeChatModel
        return cls(
            **common,
            credential=credentials.DashScopeCredential(api_key=key, base_url=base_url)
            if base_url
            else credentials.DashScopeCredential(api_key=key),
            parameters=cls.Parameters(max_tokens=spec["max_output_tokens"]),
            client_kwargs=timeout,
        )
    if adapter == "gemini":
        cls = models.GeminiChatModel
        from google.genai import types

        return cls(
            **common,
            credential=credentials.GeminiCredential(api_key=key),
            parameters=cls.Parameters(max_tokens=spec["max_output_tokens"]),
            client_kwargs={
                "http_options": types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1),
                    timeout=60000,
                    base_url=base_url,
                )
            },
        )
    if adapter == "ollama":
        cls = models.OllamaChatModel
        return cls(
            **common,
            credential=credentials.OllamaCredential(host=base_url),
            parameters=cls.Parameters(max_tokens=spec["max_output_tokens"]),
            client_kwargs={"timeout": 60.0},
        )
    raise ValueError("Unsupported adapter")


async def close_model(model):
    client = getattr(model, "client", None)
    if getattr(client, "aio", None):
        await client.aio.aclose()
    close = getattr(client, "close", None) or getattr(client, "aclose", None)
    if close:
        result = close()
        if inspect.isawaitable(result):
            await result
