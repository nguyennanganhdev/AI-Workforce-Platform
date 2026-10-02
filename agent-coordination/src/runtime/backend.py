"""Producer bindings require explicit evidenced operation contracts.

Transport adapter is real, but there are no fabricated Authority URL defaults.
Schemas/mappers must be furnished by Backend for its frozen wire contract.
"""
from dataclasses import dataclass
from typing import Callable
from adapters.backend.errors import AdapterError
from adapters.backend.events import ResolvedEvent
from supervisor.models import AuthorityView, Reconciliation


@dataclass(frozen=True)
class OperationBinding:
    path: str
    evidence: str
    request_schema: object
    response_schema: object
    encode: Callable
    decode: Callable


class ProducerOperations:
    def __init__(self, origin, bindings, transport, credentials, delegation, *, timeout=15):
        from urllib.parse import urlsplit
        url = urlsplit(origin)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError('backend TLS origin required')
        for binding in bindings.values():
            path = urlsplit(binding.path)
            if (not binding.evidence or not binding.path.startswith('/') or binding.path.startswith('//')
                or path.query or path.fragment or path.netloc or '\\' in binding.path or
                any(x in ('.','..') for x in binding.path.split('/'))):
                raise ValueError('evidenced same-origin route required')
        self.origin,self.bindings,self.transport = origin.rstrip('/'),dict(bindings),transport
        self.credentials,self.delegation,self.timeout = credentials,delegation,timeout

    async def call(self, operation, payload, authentication=None):
        import asyncio,json
        from adapters.backend.client import BackendClient
        binding = self.bindings.get(operation)
        if binding is None: raise AdapterError('operation_not_configured')
        wire = binding.encode(payload)
        binding.request_schema.validate(wire)
        headers = dict(await self.credentials.headers())
        if not headers: raise AdapterError('credentials_unavailable')
        BackendClient._check_headers(headers,{'content-type','accept'})
        # Delegation is resolved from authenticated transport evidence per request.
        proof = dict(await self.delegation.headers(authentication))
        if not proof: raise AdapterError('request_delegation_required')
        BackendClient._check_headers(proof,{'content-type','accept'} | {k.lower() for k in headers})
        headers.update(proof)
        headers.update({'Content-Type':'application/json','Accept':'application/json'})
        try:
            response = await asyncio.wait_for(self.transport.post(self.origin+binding.path,headers=headers,
                    body=json.dumps(wire,allow_nan=False).encode(),timeout=self.timeout),self.timeout)
        except (TimeoutError,OSError):
            raise AdapterError('backend_outcome_unknown',outcome_unknown=True) from None
        if not 200 <= response.status < 300:
            raise AdapterError('backend_rejected' if response.status < 500 else 'backend_outcome_unknown',outcome_unknown=response.status>=500)
        if len(response.body)>1048576: raise AdapterError('invalid_backend_response',outcome_unknown=True)
        try:
            raw = json.loads(response.body)
            binding.response_schema.validate(raw)
            return binding.decode(raw,payload)
        except Exception:
            raise AdapterError('invalid_backend_response',outcome_unknown=True) from None


class BackendAuthority:
    def __init__(self, operations, authentication):
        self.operations,self.authentication = operations,authentication

    async def inspect(self, state):
        view = AuthorityView.model_validate(await self.operations.call('authority.inspect',state,self.authentication))
        if view.context != state.context or view.state_version != state.version:
            raise AdapterError('stale_authority_view')
        if any(not entry.capabilities for entry in view.catalog.values()):
            raise AdapterError('capability_catalog_missing')
        return view

    async def authorize_action(self, state, action):
        response = await self.operations.call('authority.authorize',(state,action),self.authentication)
        if response is not True: raise AdapterError('action_not_authorized')

    async def publish_coordination_intent(self, state, action):
        return await self.operations.call('draft.publish',(state,action),self.authentication)

    async def reconcile(self, state, action):
        # Binding decode MUST verify proof of the current attempt and old-worker
        # suppression before translating not_applied; never reuse previous proof.
        raw = await self.operations.call('authority.reconcile',(state,action),self.authentication)
        if (not isinstance(raw,dict) or raw.get('action_id') != action.action_id or
            raw.get('dispatch_attempt') != action.dispatch_attempt):
            raise AdapterError('reconciliation_attempt_mismatch')
        if raw.get('outcome') == 'not_applied' and raw.get('old_sender_fenced') is not True:
            raise AdapterError('reconciliation_fence_missing')
        return Reconciliation.model_validate({k:v for k,v in raw.items() if k in ('outcome','receipt')})


class BackendEventVerifier:
    def __init__(self, operations): self.operations = operations

    async def resolve(self, event, authentication):
        resolved = await self.operations.call('event.verify',event,authentication)
        from groupchat.models import Context
        ctx = Context.model_validate(resolved)
        if ctx.tenant_id != event['tenant_id']: raise AdapterError('event_not_authorized')
        return ResolvedEvent(ctx.model_dump(mode='json',exclude_none=True))
