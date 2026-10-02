"""D07/D08 orchestration, Coordination consumer proposal v1 (not C13/C14 API).

Producer verifies exact wire, actor, source, current scope/version and remote
apply fence. Missing producer/delegation/release evidence fails closed. Independent
workflows never mutate Supervisor lifecycle or reopen a completed ticket.
"""
import json
from typing import Annotated, Literal, Union
from uuid import uuid5, NAMESPACE_URL

from pydantic import Field, model_validator
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from groupchat.models import Context, Id, Model, Text
from groupchat.ports import Invocation
from runtime.contributions import StaffContribution


class StaffRequest(Model):
    operation: Literal['request']
    staff_id: Id
    task_id: Id
    work_order_id: Id
    requested_fields: list[Literal['procedure','actual_cost']] = Field(min_length=1)
    message: Text

    @model_validator(mode='after')
    def unique_fields(self):
        if len(set(self.requested_fields)) != len(self.requested_fields): raise ValueError('duplicate fields')
        return self


class StaffSubmit(Model):
    operation: Literal['submit']
    contribution: StaffContribution


class StaffStatus(Model):
    operation: Literal['status']
    contribution_id: Id
    revision: int = Field(ge=1,strict=True)


class ReportSubmit(Model):
    operation: Literal['submit']
    config: dict


class ReportPrepare(Model):
    operation: Literal['prepare']
    report_request_id: Id
    config: dict


class ReportAction(Model):
    operation: Literal['run','status','export','cancel']
    report_request_id: Id


class ReportDownload(Model):
    operation: Literal['download']
    artifact_id: Id
    report_request_id: Id


StaffPayload = Annotated[Union[StaffRequest,StaffSubmit,StaffStatus],Field(discriminator='operation')]
ReportPayload = Annotated[Union[ReportSubmit,ReportPrepare,ReportAction,ReportDownload],Field(discriminator='operation')]


class WorkflowCommand(Model):
    schema_version: Literal['coordination-workflow-proposal-1']
    message_id: Id
    context: Context
    ticket_version: Id
    source_message_id: Id


class ContributionCommand(WorkflowCommand):
    payload: StaffPayload

    @model_validator(mode='after')
    def scope(self):
        if self.payload.operation == 'submit':
            value = self.payload.contribution
            for field in ('tenant_id','workspace_id','ticket_id','ticket_generation','run_id'):
                if getattr(value,field) != getattr(self.context,field): raise ValueError('contribution scope mismatch')
            if value.source_message_id != self.source_message_id: raise ValueError('contribution source mismatch')
        return self


class ReportCommand(WorkflowCommand):
    payload: ReportPayload


class WorkflowProof(Model):
    context: Context
    message_id: Id
    source_message_id: Id
    ticket_version: Id
    payload_hash: Id
    fence: int = Field(ge=0,strict=True)
    actor_kind: Literal['staff','supervisor','management']
    actor_id: Id
    authorization_reference: Id
    remote_fence_enforced: Literal[True]


class Workflows:
    def __init__(self, authority, records, *, contributions=None, reports=None, remote=None):
        self.authority,self.records = authority,records
        self.contributions,self.reports,self.remote = contributions,reports,remote

    async def request_after_work(self, state, delivery, authentication, ingress):
        """Trusted Supervisor work observer feeds the independent D07 workflow.

        Producer resolves eligibility/assigned staff/source/version, and returns a
        stable request command or explicit None if its policy asks no contribution.
        Durable enqueue precedes the original work input ACK; restart reuses IDs.
        """
        if self.contributions is None: raise AdapterError('workflow_dependency_unavailable')
        producer = self.contributions.producer
        resolve = getattr(producer,'staff_request_for_work',None)
        if not callable(resolve): raise AdapterError('staff_request_trigger_unavailable')
        if delivery.message_type != 'work.completed' or not state.result:
            raise AdapterError('staff_request_work_required')
        key = fingerprint({'context':state.context.model_dump(mode='json'),'event_id':delivery.event_id})
        decision = await self.records.get('staff_work_decision',key)
        if decision is None:
            wire = await resolve(state,delivery,authentication)
            decision = {'wire':wire}
            await self.records.put_once('staff_work_decision',key,decision)
        wire = decision['wire']
        if wire is None: return None  # durable explicit backend policy, never local inference
        command=ContributionCommand.model_validate_json(json.dumps(wire),strict=True)
        if command.context != state.context or command.payload.operation != 'request':
            raise AdapterError('staff_request_trigger_mismatch')
        return await ingress.accept('contribution',wire,authentication)

    async def verify(self, kind, wire, authentication, *, fence=0):
        if self.authority is None: raise AdapterError('workflow_authority_unavailable')
        if kind == 'contribution' and self.contributions is not None:
            command = ContributionCommand.model_validate_json(json.dumps(wire),strict=True)
        elif kind == 'report' and self.reports is not None:
            command = ReportCommand.model_validate_json(json.dumps(wire),strict=True)
        else: raise AdapterError('workflow_dependency_unavailable')
        required = ['verify_workflow','workflow_authentication']
        if kind == 'report' and command.payload.operation == 'run': required.append('report_invocation')
        if any(not callable(getattr(self.authority,name,None)) for name in required):
            raise AdapterError('workflow_authority_unavailable')
        producer = self.contributions.producer if kind == 'contribution' else self.reports.producer
        methods = {
            'contribution':{
                'request':('authorize_staff_request','request_staff_contribution','reconcile_staff_request'),
                'submit':('verify_staff_contribution','submit_contribution','reconcile_contribution'),
                'status':('authorize_contribution_status','contribution_status')},
            'report':{
                'submit':('authorize_report','create_report_request','reconcile_report_request'),
                'prepare':('authorize_report','fetch_report_snapshot'),
                'run':('authorize_report_request','persist_report_result','reconcile_report_result'),
                'status':('authorize_report_request','report_status'),
                'export':('authorize_report_request','export_report','reconcile_report_export'),
                'cancel':('authorize_report_request','cancel_report','reconcile_report_cancel'),
                'download':('authorize_report_artifact','stream_report_artifact')}}
        if any(not callable(getattr(producer,name,None)) for name in methods[kind][command.payload.operation]):
            raise AdapterError('workflow_dependency_unavailable')
        raw = await self.authority.verify_workflow(kind,command,wire,authentication,fence)
        try: proof = WorkflowProof.model_validate(raw,strict=True)
        except ValueError: raise AdapterError('workflow_not_authorized') from None
        if (proof.context != command.context or proof.message_id != command.message_id or
            proof.source_message_id != command.source_message_id or proof.ticket_version != command.ticket_version or
            proof.payload_hash != fingerprint(wire) or proof.fence != fence):
            raise AdapterError('workflow_proof_mismatch')
        if kind == 'contribution' and command.payload.operation == 'submit':
            if proof.actor_kind != 'staff' or proof.actor_id != command.payload.contribution.author_id:
                raise AdapterError('staff_contribution_not_verified')
        elif kind == 'contribution' and command.payload.operation == 'request':
            if proof.actor_kind not in ('supervisor','management'): raise AdapterError('staff_request_forbidden')
        elif kind == 'report' and proof.actor_kind != 'management':
            raise AdapterError('report_management_required')
        return command,proof

    async def execute(self, kind, wire, authentication, *, fence):
        command,proof = await self.verify(kind,wire,authentication,fence=fence)
        if command.payload.operation == 'download': raise AdapterError('download_requires_authenticated_response')
        delegated = await self.authority.workflow_authentication(proof,authentication)
        if delegated is None: raise AdapterError('workflow_delegation_unavailable')
        key = fingerprint({'kind':kind,'context':wire['context'],'message_id':command.message_id})
        # Conflict before replay; reauthorization above still checks revoke/version.
        await self.records.put_once('workflow_wire',key,wire)
        saved = await self.records.get('workflow_receipt',key)
        operation = command.payload.operation
        reports = self.reports.for_context(command.context) if kind == 'report' else None
        if kind == 'report':
            if operation in ('submit','prepare'):
                authorization = await reports.producer.authorize_report(command.payload.config,delegated)
            else:
                authorization = await reports.producer.authorize_report_request(command.payload.report_request_id,delegated)
            if (not authorization or authorization.get('workspace_id') != command.context.workspace_id or
                authorization.get('tenant_id') != command.context.tenant_id):
                raise AdapterError('report_scope_mismatch')
        # Mutating consumers reauthorize before their own receipt replay, including
        # release/evidence/artifact revocation. Never bypass them via this journal.
        if saved and operation == 'status':
            if kind == 'contribution':
                status_proof=await self.contributions.producer.authorize_contribution_status(command,delegated)
                if not status_proof or status_proof.get('payload_hash') != fingerprint(command.model_dump(mode='json')):
                    raise AdapterError('contribution_status_forbidden')
            return saved
        if kind == 'contribution':
            if operation == 'request': result = await self.contributions.request(command,delegated)
            elif operation == 'submit': result = await self.contributions.submit(command.payload.contribution,delegated)
            else: result = await self.contributions.status(command,delegated)
        elif operation == 'submit':
            result = await reports.submit(command.payload.config,command.source_message_id,delegated)
        elif operation == 'prepare':
            result = await reports.prepare(command.payload.config,delegated,
                expected_request=command.payload.report_request_id,expected_workspace=command.context.workspace_id,
                require_snapshot_pin=True)
            if (result.get('report_request_id') != command.payload.report_request_id or
                result.get('workspace_id') != command.context.workspace_id): raise AdapterError('report_snapshot_scope_mismatch')
        elif operation == 'run': result = await self._report_run(command,delegated,fence,reports)
        elif operation == 'export':
            snapshot_key,_,_ = await reports.pinned(command.payload.report_request_id,delegated,require_snapshot_pin=True)
            if not await self.records.get('report_result_receipt',snapshot_key): raise AdapterError('report_result_required')
            result = await reports.export(command.payload.report_request_id,delegated)
        elif operation == 'cancel':
            cancel_key = fingerprint({'tenant':command.context.tenant_id,'workspace':command.context.workspace_id,
                                      'request':command.payload.report_request_id})
            await self.records.put_once('report_cancel_request',cancel_key,{'requested':True})
            result = await reports.cancel(command.payload.report_request_id,delegated)
            # Backend owns confirmation. Request acknowledgement isn't completion.
            if result['status'] != 'cancelled': return None
        else: result = await reports.status(command.payload.report_request_id,delegated)
        await self.records.put_once('workflow_receipt',key,result)
        return result

    async def _report_run(self, command, delegated, fence, reports):
        if self.remote is None: raise AdapterError('report_remote_unavailable')
        request_id = command.payload.report_request_id
        cancel_key = fingerprint({'tenant':command.context.tenant_id,'workspace':command.context.workspace_id,'request':request_id})
        if await self.records.get('report_cancel_request',cancel_key):
            raise AdapterError('report_cancel_requested')
        _,saved,authorization = await reports.pinned(request_id,delegated,require_snapshot_pin=True)
        if authorization['workspace_id'] != command.context.workspace_id: raise AdapterError('report_scope_mismatch')
        narrative = self.reports.artifacts.narrative(saved['snapshot'],saved['config'],authorization)
        instruction = json.dumps({'instruction':'Return AgentOutput.content as JSON containing snapshot_id and narrative exactly '
            'as provided. Optional commentary is advisory only. Do not recalculate metrics or change lineage.',
            'snapshot_id':saved['snapshot']['snapshot_id'],'narrative':narrative,
            'report_prompt':self.reports.artifacts.prompt},ensure_ascii=False)
        operation_id = str(uuid5(NAMESPACE_URL,'report-execution:'+fingerprint({
            'context':command.context.model_dump(mode='json'),'request':request_id})))
        invocation = await self.authority.report_invocation(command,delegated,operation_id,fence,instruction,
                                                            self.reports.artifacts.artifact_hash)
        if (not isinstance(invocation,Invocation) or invocation.context != command.context or
            invocation.operation_id != operation_id or invocation.fence != fence or
            invocation.instruction != instruction or invocation.participant.role != 'report' or
            invocation.artifact_hash != self.reports.artifacts.artifact_hash or
            not invocation.groupchat_version_id or not invocation.source_run_id or
            invocation.transcript or invocation.tasks or invocation.ticket_context):
            raise AdapterError('report_invocation_scope_mismatch')
        # Same released-session and AgentScope/Openbot path as specialist execution.
        await self.remote.prepare(invocation)
        output = await self.remote.invoke(invocation)
        if await self.records.get('report_cancel_request',cancel_key):
            raise AdapterError('report_cancel_requested')
        if output.follow_up_requests: raise AdapterError('report_follow_up_denied')
        try: draft = json.loads(output.content)
        except ValueError: raise AdapterError('invalid_report_narrative') from None
        if not isinstance(draft,dict): raise AdapterError('invalid_report_narrative')
        return await reports.persist_narrative(request_id,draft,delegated)

    async def download(self, wire, authentication):
        command,proof = await self.verify('report',wire,authentication)
        if command.payload.operation != 'download': raise AdapterError('download_operation_required')
        delegated = await self.authority.workflow_authentication(proof,authentication)
        if delegated is None: raise AdapterError('workflow_delegation_unavailable')
        reports=self.reports.for_context(command.context)
        authorization = await reports.producer.authorize_report_artifact(command.payload.artifact_id,delegated)
        if (not authorization or authorization.get('workspace_id') != command.context.workspace_id or
            authorization.get('tenant_id') != command.context.tenant_id):
            raise AdapterError('report_artifact_forbidden')
        content = await reports.download(command.payload.artifact_id,delegated,
            expected_request=command.payload.report_request_id)
        if not isinstance(content,bytes) or len(content) > 10*1024*1024:
            raise AdapterError('report_download_contract_invalid')
        return content
