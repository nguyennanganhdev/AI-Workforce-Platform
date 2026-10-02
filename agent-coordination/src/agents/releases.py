"""Consumer release attestation. No actor-visible/latest loader substitution."""
import os
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from groupchat.models import Model
from adapters.backend.messages import fingerprint
from adapters.backend.errors import AdapterError


class ReleasedSession(Model):
    tenant_id: str
    workspace_id: str
    ticket_id: str
    ticket_generation: int = Field(ge=0,strict=True)
    groupchat_version_id: str
    agent_version_id: str
    member_id: str
    binding_id: str
    binding_generation: int = Field(ge=1,strict=True)
    framework_reference: str
    source_run_id: str
    thread_id: str
    evaluated: Literal[True]
    admin_approved: Literal[True]
    published: Literal[True]
    revoked: Literal[False]
    prompt_hash: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    knowledge_grants: list[str]
    capabilities: list[str] = Field(min_length=1)
    model: str = Field(min_length=1)
    runtime: Literal['openbot-chat-completions']
    endpoint: str
    credential_env: str = Field(pattern=r'^[A-Z][A-Z0-9_]*$')
    tool_descriptors: list[dict]
    output_tokens: int = Field(gt=0,le=32768,strict=True)
    development: bool = False
    report_artifact_hash: str | None = None

    @model_validator(mode='after')
    def wire(self):
        url = urlsplit(self.endpoint)
        if url.path != '/ag-ui' or url.query or url.fragment or url.username or url.password:
            raise ValueError('unsupported Openbot endpoint')
        if url.scheme != 'https' and not (self.development and url.scheme=='http' and url.hostname in ('127.0.0.1','localhost')):
            raise ValueError('Openbot requires TLS')
        # Preserve existing Openbot runtime guard; do not silently override its model.
        if self.model.startswith('gpt-5.6-'):
            raise ValueError('model incompatible with current Openbot chat tool loop')
        names = []
        for tool in self.tool_descriptors:
            if set(tool) != {'name','description','parameters'} or not isinstance(tool['parameters'],dict):
                raise ValueError('invalid granted AG-UI tool')
            names.append(tool['name'])
        if len(names) != len(set(names)): raise ValueError('duplicate granted tool')
        return self

    @property
    def digest(self):
        return fingerprint(self.model_dump(mode='json'))

    @property
    def tool_names(self):
        return {t['name'] for t in self.tool_descriptors}

    def validate(self, invocation):
        ctx,p = invocation.context,invocation.participant
        if ((self.tenant_id,self.workspace_id,self.ticket_id,self.ticket_generation) !=
            (ctx.tenant_id,ctx.workspace_id,ctx.ticket_id,ctx.ticket_generation) or
            self.groupchat_version_id != invocation.groupchat_version_id or
            (self.agent_version_id,self.member_id,self.binding_id,self.binding_generation,self.framework_reference,self.source_run_id) !=
            (p.agent_version_id,p.member_id,p.binding_id,p.binding_generation,p.framework_reference,invocation.source_run_id)):
            raise AdapterError('release_session_scope_mismatch')
        if invocation.participant.role == 'report' and (
            'report' not in self.capabilities or not invocation.artifact_hash or
            self.report_artifact_hash != invocation.artifact_hash):
            raise AdapterError('report_release_artifact_mismatch')

    async def headers(self):
        token = os.environ.get(self.credential_env)
        if not token or '\r' in token or '\n' in token:
            raise AdapterError('credentials_unavailable')
        return {'x-openbot-agent-token':token,'Accept':'text/event-stream'}


class ReleaseConsumer:
    """Backend resolver supplies signed/reverified attestations, no invented URL.

    Records retain a pin per operation. Authorization is always rechecked, including
    grant/history revocation; rollback only affects producer resolution for new runs.
    """
    def __init__(self, producer, records):
        self.producer,self.records = producer,records

    async def for_invocation(self, invocation):
        key = fingerprint({'scope':invocation.context.model_dump(mode='json'),'operation':invocation.operation_id})
        raw = await self.producer.resolve_released_session(invocation)
        release = ReleasedSession.model_validate(raw)
        release.validate(invocation)
        await self.records.put_once('thread_owner',fingerprint({'endpoint':release.endpoint,'thread_id':release.thread_id}),
            {'scope':invocation.context.model_dump(mode='json'),'member_id':release.member_id,'source_run_id':release.source_run_id})
        previous = await self.records.get('release_pin',key)
        if previous and previous != release.model_dump(mode='json'):
            raise AdapterError('release_pin_changed')
        await self.records.put_once('release_pin',key,release.model_dump(mode='json'))
        return release

    async def reauthorize(self, invocation, release):
        current = await self.for_invocation(invocation)
        if current.digest != release.digest: raise AdapterError('release_pin_changed')
