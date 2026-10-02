"""Authenticated backend verification -> durable Coordination inbox.

Producer must supply a stable delegated reference, not a raw token. Reference
issuance API is an explicit external dependency; no guessed URL or identity.
"""
import json
from dataclasses import asdict
from adapters.backend.events import PendingDelivery
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint,validate_event,validate_payload,snapshot
from groupchat.reception import ReceptionMessage
from groupchat.models import Context


class DurableIngress:
    def __init__(self, gateway, verifier, validator, inbox, delegation, event_types, workflows=None):
        self.gateway,self.verifier,self.validator,self.inbox,self.delegation = gateway,verifier,validator,inbox,delegation
        self.event_types=dict(event_types)
        self.workflows=workflows

    async def accept(self, kind, raw, authentication):
        wire=snapshot(raw)
        if kind=='reception':
            message=ReceptionMessage.model_validate(wire,strict=True)
            resolution=await self.gateway.resolve(message,authentication)
            context=resolution.verified.context
            identity=message.message_id
            if resolution.verified.message!=message: raise AdapterError('verified_message_mismatch')
            payload={'kind':kind,'wire':wire}
        elif kind=='event':
            validate_event(wire);self.validator.validate('event',wire)
            message_type=self.event_types.get(wire['event_type'])
            if message_type is None: raise AdapterError('event_not_supported')
            # New runs only V2; legacy Reception business inputs are rejected.
            if message_type in ('ticket.submitted','resident.message','completion.responded'):
                raise AdapterError('v1_reception_message_denied')
            validate_payload(message_type,wire['payload'])
            if message_type == 'approval.responded' and wire['payload'].get('stage') == 'resident_plan':
                raise AdapterError('v1_reception_message_denied')
            resolved=await self.verifier.resolve(wire,authentication)
            context=Context.model_validate(resolved.context)
            if context.tenant_id!=wire['tenant_id']: raise AdapterError('scope_mismatch')
            identity=wire['event_id']
            delivery=PendingDelivery(context.tenant_id,identity,fingerprint(wire),'supervisor',message_type,
                context.model_dump(mode='json',exclude_none=True),wire)
            payload={'kind':kind,'wire':wire,'delivery':asdict(delivery)}
        elif kind in ('contribution','report'):
            if self.workflows is None: raise AdapterError('workflow_dependency_unavailable')
            command,_=await self.workflows.verify(kind,wire,authentication)
            if command.payload.operation == 'download': raise AdapterError('download_requires_authenticated_response')
            context,identity=command.context,command.message_id
            payload={'kind':kind,'wire':wire}
        else: raise AdapterError('unsupported_ingress')
        # Binding must authenticate source/audience/expiry/scope and return stable
        # receipt reference for this exact immutable wire, including retries.
        reference=await self.delegation.durable_reference(authentication,context,identity,fingerprint(wire))
        if not isinstance(reference,str) or not reference: raise AdapterError('durable_delegation_unavailable')
        payload['authentication_ref']=reference
        key=json.dumps((context.tenant_id,kind,identity),separators=(',',':'))
        await self.inbox.accept(key,payload)
        return {'id':identity,'durable':True}
