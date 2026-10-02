"""Draft intent consumer seam; producer wire mapping is pending EXT-02.

Receipts attest immutable draft storage, not business approval or cancellation.
"""
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint


class DraftPublisher:
    def __init__(self, producer): self.producer = producer

    async def dispatch(self, state, action):
        receipt = await self.producer.publish_coordination_intent(state,action)
        self.validate(action,receipt)
        return receipt

    @staticmethod
    def validate(action, receipt):
        if (receipt.get('request_id')!=action.action_id or receipt.get('status') not in ('accepted','completed')
            or receipt.get('payload_hash')!=fingerprint(action.wire) or
            not isinstance(receipt.get('canonical_id'),str) or not receipt['canonical_id'] or
            not isinstance(receipt.get('ticket_version'),str) or not receipt['ticket_version']):
            raise AdapterError('draft_receipt_mismatch',outcome_unknown=True)
        if action.operation == 'plan' and receipt.get('plan_version') != action.wire.get('target_plan_version'):
            raise AdapterError('draft_plan_version_mismatch',outcome_unknown=True)
