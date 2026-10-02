"""D07 consumer seam (C13 proposal until producer freezes lifecycle).

Verified staff supplies actual contribution; agents cannot attest or publish.
"""
from decimal import Decimal
from pydantic import Field, model_validator
from groupchat.models import Model
from adapters.backend.messages import fingerprint
from adapters.backend.errors import AdapterError


class StaffContribution(Model):
    contribution_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    ticket_generation: int = Field(ge=0,strict=True)
    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    work_order_id: str = Field(min_length=1)
    source_message_id: str = Field(min_length=1)
    author_id: str = Field(min_length=1)
    revision: int = Field(ge=1,strict=True)
    evidence_ids: list[str] = Field(min_length=1)
    procedure: str | None = None
    actual_cost: Decimal | None = None
    currency: str | None = Field(default=None,pattern=r'^[A-Z]{3}$')

    @model_validator(mode='after')
    def content(self):
        if self.procedure is not None and not self.procedure.strip(): raise ValueError('empty procedure')
        if self.procedure is None and self.actual_cost is None: raise ValueError('contribution empty')
        if self.actual_cost is None and self.currency is not None: raise ValueError('currency without actual cost')
        if self.actual_cost is not None and (not self.actual_cost.is_finite() or self.actual_cost<0 or not self.currency):
            raise ValueError('invalid actual cost')
        if any(not e for e in self.evidence_ids) or len(set(self.evidence_ids))!=len(self.evidence_ids):
            raise ValueError('invalid evidence IDs')
        return self


class Contributions:
    def __init__(self, producer, records): self.producer,self.records = producer,records

    async def submit(self, raw, authentication):
        value = StaffContribution.model_validate(raw)
        wire = value.model_dump(mode='json')
        proof = await self.producer.verify_staff_contribution(value,authentication)
        if (not proof or proof.get('actor_kind')!='staff' or proof.get('author_id')!=value.author_id or
            proof.get('work_order_id')!=value.work_order_id or proof.get('tenant_id')!=value.tenant_id or
            proof.get('workspace_id')!=value.workspace_id or proof.get('revision')!=value.revision or
            proof.get('payload_hash')!=fingerprint(wire) or
            set(proof.get('verified_evidence_ids',[]))!=set(value.evidence_ids)):
            raise AdapterError('staff_contribution_not_verified')
        if value.revision > 1 and (proof.get('corrects_revision') != value.revision-1 or
                                  proof.get('correction_allowed') is not True):
            raise AdapterError('contribution_correction_denied')
        key = fingerprint({'tenant':value.tenant_id,'id':value.contribution_id,'revision':value.revision})
        old = await self.records.get('contribution_intent',key)
        if old is not None and old != wire: raise AdapterError('conflict')
        receipt = await self.records.get('contribution_receipt',key)
        if receipt: return receipt
        if old:
            # Reconcile current attempt with producer; absent proof stays unknown.
            receipt = await self.producer.reconcile_contribution(value,proof)
            if not receipt: raise AdapterError('contribution_outcome_unknown',outcome_unknown=True)
        else:
            created = await self.records.put_once('contribution_intent',key,wire)
            if created is True:
                receipt = await self.producer.submit_contribution(value,proof)
            else:
                receipt = await self.producer.reconcile_contribution(value,proof)
                if not receipt: raise AdapterError('contribution_outcome_unknown',outcome_unknown=True)
        if (receipt.get('contribution_id')!=value.contribution_id or receipt.get('revision')!=value.revision or
            receipt.get('status') not in ('submitted','review_pending','rejected','changes_requested','published','revoked')):
            raise AdapterError('invalid_contribution_receipt',outcome_unknown=True)
        # published is producer-owned review state, never a Coordination operation.
        await self.records.put_once('contribution_receipt',key,receipt)
        return receipt

    async def request(self, command, authentication):
        """Separate post-work workflow: backend asks real staff, never reopens a run.

        Consumer proposal only. Producer verifies completed work, assigned staff,
        source/version/fence and dispatches its staff request with remote dedup.
        """
        wire = command.model_dump(mode='json')
        proof = await self.producer.authorize_staff_request(command,authentication)
        if (not proof or proof.get('payload_hash') != fingerprint(wire) or
            proof.get('work_outcome') != 'work_completed' or
            proof.get('staff_id') != command.payload.staff_id):
            raise AdapterError('staff_request_not_authorized')
        key = fingerprint({'context':wire['context'],'source':command.source_message_id,
                           'request':wire['payload']})
        receipt = await self.records.get('staff_request_receipt',key)
        if receipt: return receipt
        created = await self.records.put_once('staff_request_intent',key,wire)
        if created is True:
            receipt = await self.producer.request_staff_contribution(command,proof)
        else:
            receipt = await self.producer.reconcile_staff_request(command,proof)
            if not receipt: raise AdapterError('staff_request_outcome_unknown',outcome_unknown=True)
        if (not receipt.get('request_id') or receipt.get('payload_hash') != fingerprint(wire) or
            receipt.get('status') != 'requested'):
            raise AdapterError('staff_request_receipt_mismatch',outcome_unknown=True)
        await self.records.put_once('staff_request_receipt',key,receipt)
        return receipt

    async def status(self, command, authentication):
        proof = await self.producer.authorize_contribution_status(command,authentication)
        if not proof or proof.get('payload_hash') != fingerprint(command.model_dump(mode='json')):
            raise AdapterError('contribution_status_forbidden')
        value = await self.producer.contribution_status(command,proof)
        if (value.get('contribution_id') != command.payload.contribution_id or
            value.get('revision') != command.payload.revision or
            type(value.get('version')) is not int or value['version'] < 1 or
            value.get('status') not in ('submitted','review_pending','rejected','changes_requested','published','revoked') or
            value.get('tenant_id') != command.context.tenant_id or
            value.get('workspace_id') != command.context.workspace_id):
            raise AdapterError('contribution_status_mismatch')
        # Each backend revision/version is immutable. No local knowledge ingestion.
        key = fingerprint({'context':command.context.model_dump(mode='json'),
                           'id':value['contribution_id'],'revision':value['revision'],'version':value['version']})
        await self.records.put_once('contribution_status',key,value)
        return value
