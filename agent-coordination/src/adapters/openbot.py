"""Openbot /ag-ui consumer. Coordination owns tool continuation.

No local specialist model loop. RUN_FINISHED is a transport terminal only.
Cancellation without a producer lookup/cancel contract is always unconfirmed.
"""
import asyncio
import codecs
import json
from dataclasses import asdict
from uuid import uuid5, NAMESPACE_URL

import httpx
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from groupchat.models import AgentOutput, RoomError


class SSEDecoder:
    def __init__(self, limit=1048576):
        self.decoder = codecs.getincrementaldecoder('utf-8')('strict')
        self.buffer, self.data, self.size = '', [], 0
        self.limit = limit

    def feed(self, chunk, *, final=False):
        self.size += len(chunk)
        if self.size > self.limit:
            raise AdapterError('stream_limit')
        self.buffer += self.decoder.decode(chunk,final=final)
        events = []
        while True:
            indices = [i for i in (self.buffer.find('\r'),self.buffer.find('\n')) if i >= 0]
            if not indices: break
            index = min(indices)
            if self.buffer[index] == '\r' and index == len(self.buffer)-1 and not final: break
            line = self.buffer[:index]
            count = 2 if self.buffer[index:index+2] == '\r\n' else 1
            self.buffer = self.buffer[index+count:]
            if not line:
                if self.data:
                    try:
                        value = json.loads('\n'.join(self.data))
                        if not isinstance(value,dict): raise ValueError()
                    except (ValueError,TypeError):
                        raise AdapterError('invalid_sse_event') from None
                    events.append(value)
                    self.data = []
            elif line.startswith('data:'):
                value = line[5:]
                self.data.append(value[1:] if value.startswith(' ') else value)
        if final and (self.buffer or self.data):
            raise AdapterError('truncated_sse',outcome_unknown=True)
        return events


class RunStream:
    def __init__(self, thread_id, run_id):
        self.thread, self.run = thread_id,run_id
        self.started = self.finished = False
        self.messages, self.calls = {}, {}

    def consume(self, event):
        kind = event.get('type')
        if self.finished: raise AdapterError('late_stream_event')
        if kind in ('RUN_STARTED','RUN_FINISHED'):
            if (event.get('threadId'),event.get('runId')) != (self.thread,self.run):
                raise AdapterError('run_correlation_mismatch')
            if kind == 'RUN_STARTED':
                if self.started: raise AdapterError('duplicate_run_started')
                self.started = True
                return
            if not self.started or any(not v['ended'] for v in (*self.messages.values(),*self.calls.values())):
                raise AdapterError('incomplete_run')
            self.finished = True
            return
        if kind == 'RUN_ERROR':
            raise AdapterError('openbot_run_error',outcome_unknown=True)
        if not self.started: raise AdapterError('run_not_started')
        if kind == 'TEXT_MESSAGE_START':
            key = event.get('messageId')
            if not key or key in self.messages or event.get('role') != 'assistant': raise AdapterError('invalid_text_start')
            self.messages[key] = {'content':'','ended':False}
        elif kind in ('TEXT_MESSAGE_CONTENT','TEXT_MESSAGE_END'):
            item = self.messages.get(event.get('messageId'))
            if item is None or item['ended']: raise AdapterError('invalid_text_event')
            if kind.endswith('CONTENT'):
                if not isinstance(event.get('delta'),str): raise AdapterError('invalid_text_delta')
                item['content'] += event['delta']
            else: item['ended'] = True
        elif kind == 'TOOL_CALL_START':
            key = event.get('toolCallId')
            if not key or key in self.calls or not event.get('toolCallName'): raise AdapterError('invalid_tool_start')
            self.calls[key] = {'name':event['toolCallName'],'args':'','ended':False}
        elif kind in ('TOOL_CALL_ARGS','TOOL_CALL_END'):
            item = self.calls.get(event.get('toolCallId'))
            if item is None or item['ended']: raise AdapterError('invalid_tool_event')
            if kind.endswith('ARGS'):
                if not isinstance(event.get('delta'),str): raise AdapterError('invalid_tool_delta')
                item['args'] += event['delta']
            else: item['ended'] = True
        else:
            raise AdapterError('unsupported_openbot_event')


class OpenbotAdapter:
    def __init__(self, releases, records, tools, budget, *, client=None, max_continuations=8, deadline=120):
        if not 1 <= max_continuations <= 32: raise ValueError('invalid continuation bound')
        self.releases, self.records, self.tools, self.budget = releases,records,tools,budget
        self.client = client or httpx.AsyncClient(follow_redirects=False,timeout=60)
        if not 0 < deadline <= 600: raise ValueError("invalid remote deadline")
        self.deadline = deadline
        self.max_continuations = max_continuations

    async def prepare(self, invocation):
        # Producer must reauthorize pins, grant revocation and isolated session on every call.
        release = await self.releases.for_invocation(invocation)
        release.validate(invocation)

    async def invoke(self, invocation):
        async with asyncio.timeout(self.deadline):
            return await self._invoke(invocation)

    async def _invoke(self, invocation):
        release = await self.releases.for_invocation(invocation)
        release.validate(invocation)
        # Worker takeover must not create a fresh remote mutation identity. Fence
        # authorizes an attempt; immutable operation identifies its side effects.
        key = fingerprint({'scope':invocation.context.model_dump(mode='json'),'operation':invocation.operation_id})
        # Exact input survives ownership takeover; only fence may change. A stable
        # ID with changed prompt/context/tool input conflicts before cached replay.
        wire_input = {name:value for name,value in asdict(invocation).items() if name != 'fence'}
        normalized = json.loads(json.dumps(wire_input,default=lambda value:value.model_dump(mode='json')))
        await self.records.put_once('remote_input',key,normalized)
        if await self.records.get('remote_cancel',key): raise RoomError('CANCEL_REQUESTED')
        saved = await self.records.get('remote_result',key)
        if saved: return AgentOutput.model_validate(saved)
        if await self.records.get('remote_intent',key):
            raise AdapterError('remote_outcome_unknown',outcome_unknown=True)
        budget = self.budget.for_scope(invocation.context) if hasattr(self.budget,'for_scope') else self.budget
        if getattr(budget,'cost',None) is not None or getattr(budget,'tenant_cost',None) is not None:
            raise AdapterError('remote_cost_bound_unavailable')
        created = await self.records.put_once('remote_intent',key,{'operation_id':invocation.operation_id,'fence':invocation.fence,'release_hash':release.digest,'thread_id':release.thread_id})
        if created is not True: raise AdapterError('remote_outcome_unknown',outcome_unknown=True)
        messages = [{'id':f'context-{key}', 'role':'user','content':json.dumps({
            'instruction':invocation.instruction,
            'context':[i.model_dump(mode='json') for i in invocation.ticket_context],
            'tasks':[t.model_dump(mode='json') for t in invocation.tasks],
            'messages':[m.model_dump(mode='json') for m in invocation.transcript]},ensure_ascii=False)}]
        for index in range(self.max_continuations):
            await self.releases.reauthorize(invocation,release)
            if await self.records.get('remote_cancel',key): raise AdapterError('cancel_outcome_unknown',outcome_unknown=True)
            run_id = str(uuid5(NAMESPACE_URL,f'{key}:{index}'))
            wire = {'threadId':release.thread_id,'runId':run_id,'state':{},'messages':messages,
                    'tools':release.tool_descriptors,'context':[],'forwardedProps':{}}
            reserve = len(json.dumps(wire,ensure_ascii=False).encode()) + release.output_tokens
            await budget.reserve(run_id,reserve)
            stream, decoder = RunStream(release.thread_id,run_id), SSEDecoder()
            try:
                async with self.client.stream('POST',release.endpoint,headers=await release.headers(),json=wire) as response:
                    if response.status_code != 200 or 'text/event-stream' not in response.headers.get('content-type',''):
                        raise AdapterError('openbot_transport_error',outcome_unknown=True)
                    async for chunk in response.aiter_bytes():
                        await self.releases.reauthorize(invocation,release)
                        if await self.records.get('remote_cancel',key): raise AdapterError('cancel_outcome_unknown',outcome_unknown=True)
                        for event in decoder.feed(chunk): stream.consume(event)
                    for event in decoder.feed(b'',final=True): stream.consume(event)
                if not stream.finished: raise AdapterError('remote_outcome_unknown',outcome_unknown=True)
            finally:
                # Current Openbot has no usage event. Keep explicit unknown, charged bound.
                await budget.reconcile(run_id)
            if not stream.calls:
                text = ''.join(v['content'] for v in stream.messages.values())
                output = AgentOutput.model_validate_json(text)
                await self.releases.reauthorize(invocation,release)
                if await self.records.get('remote_cancel',key): raise AdapterError('cancel_outcome_unknown',outcome_unknown=True)
                # This is advisor text. Supervisor still requires staff/QC/publication.
                await self.records.put_once('remote_result',key,output.model_dump(mode='json'))
                return output
            messages.append({'id':f'assistant-{run_id}','role':'assistant',
                'content':''.join(v['content'] for v in stream.messages.values()),
                'toolCalls':[{'id':call_id,'type':'function','function':{'name':call['name'],'arguments':call['args']}} for call_id,call in stream.calls.items()]})
            for call_id,call in stream.calls.items():
                await self.releases.reauthorize(invocation,release)
                if await self.records.get('remote_cancel',key): raise AdapterError('cancel_outcome_unknown',outcome_unknown=True)
                if call['name'] not in release.tool_names: raise RoomError('FORBIDDEN')
                arguments = json.loads(call['args'])
                if not isinstance(arguments,dict): raise RoomError('VALIDATION_ERROR')
                # Tool boundary validates descriptor schema + signed request-scoped
                # authorization at backend apply. Saved intent blocks blind replay.
                op = str(uuid5(NAMESPACE_URL,f'{key}:{run_id}:{call_id}'))
                await self.records.put_once('tool_intent',op,{'name':call['name'],'arguments':arguments,'run_id':run_id,'call_id':call_id,'fence':invocation.fence})
                receipt = await self.tools.execute_authorized(invocation,release,call['name'],arguments,op,run_id,call_id)
                if receipt.get('operation_id') != op or receipt.get('run_id') != run_id or receipt.get('call_id') != call_id:
                    raise AdapterError('tool_receipt_mismatch',outcome_unknown=True)
                await self.releases.reauthorize(invocation,release)
                await self.records.put_once('tool_receipt',op,receipt)
                messages.append({'id':f'result-{op}','role':'tool','toolCallId':call_id,'content':json.dumps(receipt,ensure_ascii=False)})
        raise AdapterError('continuation_limit',outcome_unknown=True)

    async def cancel(self, invocation):
        await self.releases.for_invocation(invocation)
        key = fingerprint({'scope':invocation.context.model_dump(mode='json'),'operation':invocation.operation_id})
        await self.records.put_once('remote_cancel',key,{'requested':True})
        # No real producer cancel/lookup endpoints in current source.
        return False

    async def close(self):
        await self.client.aclose()
