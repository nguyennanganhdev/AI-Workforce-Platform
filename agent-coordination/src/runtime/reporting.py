"""D08 consumes existing Report artifacts; no second scheduler or metric calculator."""
import asyncio
import hashlib
import json
from pathlib import Path
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint


class ReportArtifacts:
    @classmethod
    def from_environment(cls):
        import os
        root, digest = os.environ.get('COORDINATION_REPORT_ROOT'), os.environ.get('COORDINATION_REPORT_HASH')
        if not root or not digest: raise AdapterError('report_artifact_configuration_required')
        return cls(root,expected_hash=digest)

    def __init__(self, repo, *, expected_hash=None, development=False):
        root = Path(repo)
        files = ('agent-report/schemas/config.py','agent-report/schemas/config-v1.schema.json',
                 'agent-report/templates/metric-contracts-v1.json','agent-report/prompts/report-v1.md',
                 'server/src/reporting/narrative/operations.py')
        try: sources = {name:(root/name).read_text() for name in files}
        except OSError: raise AdapterError('report_artifacts_missing') from None
        self.artifact_hash = fingerprint({'schema':json.loads(sources[files[1]]),
            'metrics':json.loads(sources[files[2]]),'prompt':sources[files[3]],
            'config_source':sources[files[0]],'narrative_source':sources[files[4]]})
        if not development and not expected_hash: raise AdapterError('report_artifact_pin_required')
        if expected_hash is not None and expected_hash != self.artifact_hash:
            raise AdapterError('report_artifact_hash_mismatch')
        self.source_hashes = {name:hashlib.sha256(value.encode()).hexdigest() for name,value in sources.items()}
        from types import ModuleType
        path = root/files[0]
        self.config = ModuleType('coordination_report_config')
        exec(compile(sources[files[0]],str(path),'exec'),self.config.__dict__)
        self.schema = json.loads(sources[files[1]])
        self.metrics = json.loads(sources[files[2]])
        self.prompt = sources[files[3]]
        # Consume the existing narrative validator with an import namespace scoped
        # to this module, without sys.path/sys.modules changes or source rewriting.
        import builtins
        from types import ModuleType
        narrative_path = root/'server/src/reporting/narrative/operations.py'
        narrative_source = sources[files[4]]
        narrative = ModuleType('coordination_report_narrative')
        default_import = builtins.__import__
        def artifact_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'schemas.config' and level == 0:
                return self.config
            return default_import(name, globals, locals, fromlist, level)
        narrative.__dict__['__builtins__'] = {**vars(builtins),'__import__':artifact_import}
        exec(compile(narrative_source,str(narrative_path),'exec'),narrative.__dict__)
        self.narrative = narrative.build_report_narrative

    def validate_config(self, raw, grants):
        # Existing consumer code verifies template/period/timezone/metric/scope grants.
        return self.config.validate_report_config(raw,grants)

    def validate_snapshot(self, snapshot, config, authorization):
        # Code-owned metric/narrative validation remains in the producer artifact.
        # Unknown differs from zero; units, denominator ranges and lineage checked.
        try:
            self.narrative(snapshot,config,authorization)
        except self.config.ReportContractError as exc:
            raise AdapterError(exc.code.lower()) from None
        return snapshot


class ScopedReportProducer:
    """Recheck scope on every authorization response, including after long I/O."""
    def __init__(self, producer, context): self.producer,self.context=producer,context

    def __getattr__(self, name):
        method=getattr(self.producer,name)
        if name not in ('authorize_report','authorize_report_request','authorize_report_artifact'):
            return method
        async def authorized(*args,**kwargs):
            proof=await method(*args,**kwargs)
            if (not isinstance(proof,dict) or proof.get('tenant_id')!=self.context.tenant_id or
                proof.get('workspace_id')!=self.context.workspace_id):
                raise AdapterError('report_scope_mismatch')
            return proof
        return authorized


class ReportConsumer:
    def __init__(self, artifacts, producer, records): self.artifacts,self.producer,self.records = artifacts,producer,records

    def for_context(self, context):
        return ReportConsumer(self.artifacts,ScopedReportProducer(self.producer,context),self.records)

    async def prepare(self, config, authentication, *, expected_request=None, expected_workspace=None, require_snapshot_pin=False):
        authorized = await self.producer.authorize_report(config,authentication)
        parsed = self.artifacts.validate_config(config,authorized)
        snapshot = await self.producer.fetch_report_snapshot(parsed,authorized)
        authorized = await self.producer.authorize_report(config,authentication)
        parsed = self.artifacts.validate_config(config,authorized)
        checked = self.artifacts.validate_snapshot(snapshot,parsed,authorized)
        if ((expected_request and checked['report_request_id'] != expected_request) or
            (expected_workspace and checked['workspace_id'] != expected_workspace)):
            raise AdapterError('report_snapshot_scope_mismatch')
        if require_snapshot_pin and (authorized.get('snapshot_id') != checked['snapshot_id'] or
            authorized.get('as_of') != checked['as_of'] or authorized.get('snapshot_hash') != fingerprint(checked)):
            raise AdapterError('report_snapshot_attestation_mismatch')
        key = fingerprint({'tenant':authorized.get('tenant_id'),'request':authorized['report_request_id'],'workspace':authorized['workspace_id']})
        await self.records.put_once('report_snapshot',key,{'snapshot':checked,'config':parsed,'artifact_hash':self.artifacts.artifact_hash})
        return checked

    async def pinned(self, request_id, authentication, *, require_snapshot_pin=False):
        authorized = await self.producer.authorize_report_request(request_id,authentication)
        if not authorized or authorized.get('report_request_id') != request_id:
            raise AdapterError('report_request_forbidden')
        key = fingerprint({'tenant':authorized.get('tenant_id'),'request':request_id,'workspace':authorized['workspace_id']})
        saved = await self.records.get('report_snapshot',key)
        if not saved: raise AdapterError('report_snapshot_required')
        if saved['artifact_hash'] != self.artifacts.artifact_hash: raise AdapterError('report_artifact_pin_changed')
        self.artifacts.validate_snapshot(saved['snapshot'],saved['config'],authorized)
        if require_snapshot_pin and (authorized.get('snapshot_id') != saved['snapshot']['snapshot_id'] or
            authorized.get('as_of') != saved['snapshot']['as_of'] or
            authorized.get('snapshot_hash') != fingerprint(saved['snapshot'])):
            raise AdapterError('report_snapshot_attestation_mismatch')
        return key,saved,authorized

    async def persist_narrative(self, request_id, draft, authentication):
        """H09/H10 owns rendering/persistence; agent may only add advisory prose.

        Recomputed code-owned rows/lineage must exactly match the pinned snapshot.
        Model prose cannot change numeric facts or become export authorization.
        """
        from uuid import uuid5,NAMESPACE_URL
        key,saved,authorized = await self.pinned(request_id,authentication,require_snapshot_pin=True)
        expected = self.artifacts.narrative(saved['snapshot'],saved['config'],authorized)
        if (draft.get('snapshot_id') != saved['snapshot']['snapshot_id'] or
            draft.get('narrative') != expected or set(draft)-{'snapshot_id','narrative','commentary'} or
            not isinstance(draft.get('commentary',''),str)):
            raise AdapterError('report_narrative_mismatch')
        operation_id = str(uuid5(NAMESPACE_URL,'report-result:'+key))
        intent = {'report_request_id':request_id,'snapshot_id':draft['snapshot_id'],
                  'operation_id':operation_id,'artifact_hash':self.artifacts.artifact_hash,
                  'narrative':expected}
        receipt = await self.records.get('report_result_receipt',key)
        if receipt: return receipt
        created = await self.records.put_once('report_result_intent',key,intent)
        if created is True:
            receipt = await self.producer.persist_report_result(intent,authorized)
        else:
            receipt = await self.producer.reconcile_report_result(intent,authorized)
            if not receipt: raise AdapterError('report_result_outcome_unknown',outcome_unknown=True)
        if (receipt.get('operation_id') != operation_id or receipt.get('report_request_id') != request_id or
            receipt.get('snapshot_id') != intent['snapshot_id'] or not receipt.get('result_id')):
            raise AdapterError('report_result_receipt_mismatch',outcome_unknown=True)
        await self.records.put_once('report_result_receipt',key,receipt)
        return receipt

    async def download(self, artifact_id, authentication, *, expected_request, limit=10*1024*1024, deadline=30):
        async with asyncio.timeout(deadline):
            return await self._download(artifact_id,authentication,expected_request=expected_request,limit=limit,deadline=deadline)

    async def _download(self, artifact_id, authentication, *, expected_request, limit, deadline):
        # Async context-managed bounded stream is required; bytes-only producers
        # fail closed. Producer must avoid buffering upstream before yielding.
        key,saved,_ = await self.pinned(expected_request,authentication,require_snapshot_pin=True)
        exported = await self.records.get('report_export_receipt',key)
        if not exported or exported.get('artifact_id') != artifact_id:
            raise AdapterError('report_artifact_request_mismatch')
        async def authorize():
            proof = await self.producer.authorize_report_artifact(artifact_id,authentication)
            if (not proof or proof.get('artifact_id') != artifact_id or
                proof.get('report_request_id') != expected_request or
                proof.get('snapshot_id') != saved['snapshot']['snapshot_id'] or
                proof.get('snapshot_hash') != fingerprint(saved['snapshot']) or
                proof.get('artifact_hash') != saved['artifact_hash'] or
                proof.get('content_sha256') != exported.get('content_sha256') or
                not isinstance(proof.get('content_sha256'),str) or len(proof['content_sha256']) != 64):
                raise AdapterError('report_artifact_forbidden')
            return proof
        content = bytearray()
        async with asyncio.timeout(deadline):
            proof = await authorize()
            stream = getattr(self.producer,'stream_report_artifact',None)
            if not callable(stream): raise AdapterError('report_bounded_stream_required')
            async with stream(artifact_id,proof) as chunks:
                async for chunk in chunks:
                    await authorize()  # revoke during fetch, before retaining bytes
                    if not isinstance(chunk,bytes) or len(chunk) > limit-len(content):
                        raise AdapterError('report_download_limit')
                    content.extend(chunk)
            await authorize()  # including empty body / revoke on stream close
        if hashlib.sha256(content).hexdigest() != exported['content_sha256']:
            raise AdapterError('report_content_hash_mismatch')
        return bytes(content)

    async def submit(self, config, source_message_id, authentication):
        from uuid import uuid5,NAMESPACE_URL
        if not isinstance(source_message_id,str) or not source_message_id:
            raise AdapterError('report_source_message_required')
        authorization=await self.producer.authorize_report(config,authentication)
        parsed=self.artifacts.validate_config(config,authorization)
        key=fingerprint({'tenant':authorization.get('tenant_id'),'workspace':authorization['workspace_id'],'source_message_id':source_message_id,'config':parsed})
        operation_id=str(uuid5(NAMESPACE_URL,'report:'+key))
        intent={'config':parsed,'source_message_id':source_message_id,'operation_id':operation_id,'workspace_id':authorization['workspace_id'],
                'artifact_hash':self.artifacts.artifact_hash}
        receipt=await self.records.get('report_request_receipt',key)
        if receipt: return receipt  # authority rechecked above, including retry after revoke
        previous=await self.records.get('report_request_intent',key)
        if previous:
            receipt=await self.producer.reconcile_report_request(operation_id,authorization)
            if not receipt: raise AdapterError('report_request_outcome_unknown',outcome_unknown=True)
        else:
            created=await self.records.put_once('report_request_intent',key,intent)
            if created is True: receipt=await self.producer.create_report_request(intent,authorization)
            else:
                receipt=await self.producer.reconcile_report_request(operation_id,authorization)
                if not receipt: raise AdapterError('report_request_outcome_unknown',outcome_unknown=True)
        if (receipt.get('operation_id')!=operation_id or receipt.get('workspace_id')!=authorization['workspace_id'] or
            receipt.get('source_message_id')!=source_message_id or not receipt.get('report_request_id')):
            raise AdapterError('report_request_receipt_mismatch',outcome_unknown=True)
        await self.records.put_once('report_request_receipt',key,receipt)
        return receipt

    async def status(self, request_id, authentication):
        authorized=await self.producer.authorize_report_request(request_id,authentication)
        if not authorized: raise AdapterError('report_request_forbidden')
        status=await self.producer.report_status(request_id,authorized)
        if (status.get('report_request_id')!=request_id or status.get('workspace_id')!=authorized['workspace_id'] or
            type(status.get('version')) is not int or status['version'] < 1 or
            status.get('status') not in ('pending','running','complete','partial','empty','error','cancel_requested','cancelled')):
            raise AdapterError('report_status_mismatch')
        await self.records.put_once('report_status',fingerprint({'tenant':authorized.get('tenant_id'),'request':request_id,'workspace':authorized['workspace_id'],
                                                               'version':status['version']}),status)
        return status

    async def export(self, request_id, authentication):
        from uuid import uuid5,NAMESPACE_URL
        authorized=await self.producer.authorize_report_request(request_id,authentication)
        if not authorized: raise AdapterError('report_export_forbidden')
        key=fingerprint({'tenant':authorized.get('tenant_id'),'request':request_id,'workspace':authorized['workspace_id']})
        saved=await self.records.get('report_snapshot',key)
        if not saved: raise AdapterError('report_snapshot_required')
        if saved['artifact_hash']!=self.artifacts.artifact_hash: raise AdapterError('report_artifact_pin_changed')
        self.artifacts.validate_snapshot(saved['snapshot'],saved['config'],authorized)
        if await self.records.get('report_cancel_request',fingerprint({'tenant':authorized.get('tenant_id'),'workspace':authorized['workspace_id'],'request':request_id})):
            raise AdapterError('report_cancel_requested')
        if not await self.records.get('report_result_receipt',key): raise AdapterError('report_result_required')
        operation_id=str(uuid5(NAMESPACE_URL,'export:'+key))
        existing=await self.records.get('report_export_receipt',key)
        if existing: return existing
        intent={'report_request_id':request_id,'snapshot_id':saved['snapshot']['snapshot_id'],'operation_id':operation_id,
                'snapshot_hash':fingerprint(saved['snapshot']),'artifact_hash':saved['artifact_hash']}
        if await self.records.get('report_export_intent',key):
            receipt=await self.producer.reconcile_report_export(intent,authorized)
            if not receipt: raise AdapterError('report_export_outcome_unknown',outcome_unknown=True)
        else:
            created=await self.records.put_once('report_export_intent',key,intent)
            if created is True: receipt=await self.producer.export_report(intent,authorized)
            else:
                receipt=await self.producer.reconcile_report_export(intent,authorized)
                if not receipt: raise AdapterError('report_export_outcome_unknown',outcome_unknown=True)
        if (receipt.get('operation_id')!=operation_id or receipt.get('report_request_id')!=request_id or
            receipt.get('snapshot_id')!=saved['snapshot']['snapshot_id'] or not receipt.get('artifact_id') or
            receipt.get('snapshot_hash')!=intent['snapshot_hash'] or receipt.get('artifact_hash')!=intent['artifact_hash'] or
            not isinstance(receipt.get('content_sha256'),str) or len(receipt['content_sha256'])!=64):
            raise AdapterError('report_export_receipt_mismatch',outcome_unknown=True)
        await self.records.put_once('report_export_receipt',key,receipt)
        return receipt

    async def cancel(self, request_id, authentication):
        from uuid import uuid5,NAMESPACE_URL
        authorized=await self.producer.authorize_report_request(request_id,authentication)
        if not authorized: raise AdapterError('report_cancel_forbidden')
        key=fingerprint({'tenant':authorized.get('tenant_id'),'request':request_id,'workspace':authorized['workspace_id']})
        operation_id=str(uuid5(NAMESPACE_URL,'cancel:'+key))
        intent={'report_request_id':request_id,'operation_id':operation_id}
        confirmed=await self.records.get('report_cancel_confirmation',key)
        if confirmed: return confirmed
        prior=await self.records.get('report_cancel_receipt',key)
        if prior and prior.get('status') == 'cancelled': return prior
        if await self.records.get('report_cancel_intent',key):
            receipt=await self.producer.reconcile_report_cancel(intent,authorized)
            if not receipt: raise AdapterError('report_cancel_outcome_unknown',outcome_unknown=True)
        else:
            created=await self.records.put_once('report_cancel_intent',key,intent)
            if created is True: receipt=await self.producer.cancel_report(intent,authorized)
            else:
                receipt=await self.producer.reconcile_report_cancel(intent,authorized)
                if not receipt: raise AdapterError('report_cancel_outcome_unknown',outcome_unknown=True)
        if receipt.get('report_request_id')!=request_id or receipt.get('operation_id')!=operation_id or receipt.get('status') not in ('cancel_requested','cancelled'):
            raise AdapterError('report_cancel_receipt_mismatch',outcome_unknown=True)
        if not prior: await self.records.put_once('report_cancel_receipt',key,receipt)
        if receipt['status'] == 'cancelled': await self.records.put_once('report_cancel_confirmation',key,receipt)
        return receipt  # cancel_requested is never converted to confirmed cancelled
