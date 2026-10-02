"""Explicit service/provider configuration; no model substitution or tool overrides."""
import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, SecretStr, model_validator
from groupchat.models import Model


class ProviderConfig(Model):
    provider: Literal['openai-compatible']
    model: str = Field(min_length=1)
    base_url: str
    key_env: str = Field(pattern=r'^[A-Z][A-Z0-9_]*$')
    allowed_models: list[str] = Field(min_length=1)
    api: Literal['chat-completions'] = 'chat-completions'
    timeout: float = Field(gt=0, le=120, allow_inf_nan=False)
    output_tokens: int = Field(gt=0, le=32768, strict=True)
    input_bytes: int = Field(gt=0, le=2000000, strict=True)
    hard_cost_required: bool = False
    mode: Literal['development', 'production'] = 'production'

    @model_validator(mode='after')
    def compatible(self):
        if self.hard_cost_required:
            raise ValueError('provider token/price upper-bound attestation unavailable')
        url = urlsplit(self.base_url)
        if (url.scheme != 'https' and not (self.mode == 'development' and url.scheme == 'http' and url.hostname in ('127.0.0.1','localhost'))):
            raise ValueError('provider origin requires TLS')
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('invalid provider URL')
        if self.model not in self.allowed_models:
            raise ValueError('model not allowed')
        return self

    def pin(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class ServiceConfig(Model):
    mode: Literal['development','production'] = 'production'
    ingress_token_env: str = 'COORDINATION_INGRESS_TOKEN'
    factory: str | None = None
    supervisor: ProviderConfig | None = None
    host: str = '127.0.0.1'
    port: int = Field(default=4300,gt=0,le=65535)
    max_body_bytes: int = Field(default=1048576,gt=0,le=4194304)

    @model_validator(mode='after')
    def config_valid(self):
        if self.mode == 'production' and self.supervisor and self.supervisor.mode != 'production':
            raise ValueError('development model override forbidden in production')
        if self.factory:
            import re
            if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*',self.factory) or any(
                part in ('tests','support') for part in self.factory.split(':')[0].split('.')):
                raise ValueError('trusted production composition factory required')
        return self
