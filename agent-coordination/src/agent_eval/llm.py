"""One structured chat-completions call for the judge and the case generator.

The model is configured apart from the agents under test: the business API resolves its `evaluator`
role, or the worker falls back to EVAL_MODEL_* settings. The judge never reuses the agent's own model call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from vinhomes.models import model_endpoint, output_limit


class ModelError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model_name: str
    base_url: str
    api_key: str = field(repr=False)

    @property
    def profile(self) -> str:
        return f'{self.provider}/{self.model_name}'

    @classmethod
    def from_api(cls, config: dict) -> ModelConfig:
        return cls(config['provider'], config['model_name'], config['base_url'].rstrip('/'), config['api_key'])

    @classmethod
    def from_env(cls, env=None) -> ModelConfig | None:
        import os
        env = os.environ if env is None else env
        name = (env.get('EVAL_MODEL') or '').strip()
        if not name:
            return None
        provider, base, key = model_endpoint('EVAL', env)
        return cls(provider, name, base.rstrip('/'), key) if key else None


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


async def structured(client: httpx.AsyncClient, model: ModelConfig, system: str, user: str, schema_name: str,
                     schema: dict, *, timeout: float = 110, max_tokens: int = 4096) -> tuple[dict, Usage]:
    """The model's JSON object for this schema. Raises ModelError; never returns a partial answer."""
    response_format = ({'type': 'json_schema', 'json_schema': {'name': schema_name, 'schema': schema, 'strict': True}}
                       if model.provider == 'openai' else {'type': 'json_object'})
    body = {'model': model.model_name, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'response_format': response_format, **output_limit(model.provider, max_tokens)}
    try:
        reply = await client.post(model.base_url + '/chat/completions', json=body, timeout=timeout,
                                  headers={'Authorization': 'Bearer ' + model.api_key})
    except httpx.TimeoutException:
        raise ModelError('model_timeout') from None
    except httpx.HTTPError:
        raise ModelError('model_unavailable') from None
    if reply.status_code != 200:
        raise ModelError(f'model_status_{reply.status_code}')
    try:
        data = reply.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage') or {}
        return json.loads(content), Usage(usage.get('prompt_tokens'), usage.get('completion_tokens'))
    except (ValueError, KeyError, IndexError, TypeError):
        raise ModelError('invalid_model_response') from None
