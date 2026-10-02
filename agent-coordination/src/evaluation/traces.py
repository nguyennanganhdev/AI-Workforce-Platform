"""Scoped validated decision traces; no private chain-of-thought or credentials."""
from uuid import uuid4
from adapters.backend.messages import fingerprint


class DecisionTraces:
    def __init__(self, records): self.records=records

    async def record(self, state, prompt, decision, error):
        await self.records.put_once('decision_trace',str(uuid4()),{
            'context':state.context.model_dump(mode='json'), 'state_version':state.version,
            'ticket_version':state.ticket_version,'groupchat_version_id':state.groupchat_version_id,
            'prompt_hash':fingerprint(prompt),'decision':decision,'validation_error':error})
