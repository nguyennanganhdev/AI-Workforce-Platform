"""The evaluation worker: claims a run from the business API and plays its six cases in the sandbox stack.

One run at a time, under the API's lease (heartbeat every 15 s). Before the first case and before every
case the sandbox attests whose database it is; a sandbox that can reach the source database, or answers
for another tenant, ends the run unsafe. Each case opens a conversation as a synthetic fixture resident,
says the case's message, answers questions only with the case's declared follow-ups, and waits until the
recorded state settles or the case times out. Then the nine checks, the judge and the metrics run on what
was recorded, and the result goes back to the API, which makes the verdict. The conversation's work in
the sandbox is closed afterwards in every case.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from .checks import CheckContext, run_checks
from .contracts import EnvironmentAttestation, EvalCase, ExecutionContext, Trace
from .judge import judge
from .llm import ModelConfig
from .metrics import score_metrics

log = logging.getLogger('agent_eval.worker')
HEARTBEAT_SECONDS = 15
LEASE_SECONDS = 60  # the API's lease; renewed every HEARTBEAT_SECONDS


class Stop(Exception):
    """The run was cancelled or the lease was lost: stop without writing more."""


class Unsafe(Exception):
    def __init__(self, attestation: EnvironmentAttestation):
        super().__init__(attestation.reason)
        self.attestation = attestation


@dataclass(frozen=True)
class Settings:
    backend_url: str
    service_token: str = field(repr=False)
    sandbox_url: str = ''
    sandbox_token: str = field(default='', repr=False)
    worker_id: str = 'agent-eval'
    host: str = '127.0.0.1'
    port: int = 4400
    poll_seconds: float = 5.0
    settle_seconds: float = 3.0
    catalog_seconds: float = 300.0
    case_seconds: float = 300.0
    judge_seconds: float = 120.0
    fallback_model: ModelConfig | None = None

    @classmethod
    def from_env(cls, env=None) -> Settings:
        env = os.environ if env is None else env
        get = lambda name, default='': (env.get(name) or default).strip()
        backend, token = get('EVAL_BACKEND_URL'), get('EVAL_SERVICE_TOKEN')
        if not backend.startswith(('http://', 'https://')) or len(token) < 32:
            raise ValueError('EVAL_BACKEND_URL and EVAL_SERVICE_TOKEN (32+ characters) are required')
        sandbox, sandbox_token = get('EVAL_SANDBOX_URL'), get('EVAL_SANDBOX_TOKEN')
        if sandbox and len(sandbox_token) < 32:
            raise ValueError('EVAL_SANDBOX_TOKEN (32+ characters) is required with EVAL_SANDBOX_URL')
        return cls(backend.rstrip('/'), token, sandbox.rstrip('/'), sandbox_token,
                   get('EVAL_WORKER_ID') or f'{socket.gethostname()}-{os.getpid()}', get('EVAL_HOST', '127.0.0.1'),
                   int(get('EVAL_PORT', '4400')), float(get('EVAL_POLL_SECONDS', '5')), float(get('EVAL_SETTLE_SECONDS', '3')),
                   float(get('EVAL_CATALOG_SECONDS', '300')), fallback_model=ModelConfig.from_env(env))


class Api:
    def __init__(self, client: httpx.AsyncClient, base: str, token: str):
        self.client, self.base, self.headers = client, base, {'Authorization': 'Bearer ' + token}

    async def call(self, method: str, path: str, **options) -> httpx.Response:
        return await self.client.request(method, self.base + path, headers=self.headers, timeout=60, **options)

    async def json(self, method: str, path: str, **options):
        reply = await self.call(method, path, **options)
        if reply.status_code >= 400:
            raise httpx.HTTPStatusError(f'{method} {path} answered {reply.status_code}: {reply.text[:300]}', request=reply.request, response=reply)
        return reply.json()


def attest(facts: dict, execution_tenant_id: str) -> EnvironmentAttestation:
    """Whether the sandbox is isolated from the source, from facts its own database reported."""
    problems = []
    if facts.get('rolsuper') or facts.get('rolbypassrls'):
        problems.append('role sandbox có quyền superuser hoặc BYPASSRLS')
    if facts.get('tenant_id') != execution_tenant_id:
        problems.append('sandbox trả lời cho tenant khác tenant eval của lần chạy')
    if not facts.get('source_database') or facts.get('database') == facts.get('source_database'):
        problems.append('sandbox không tách khỏi database nguồn')
    if facts.get('source_database') in (facts.get('connectable') or []) or facts.get('source_connect'):
        problems.append('role sandbox kết nối được database nguồn')
    if facts.get('tenants') != 1:
        problems.append('database sandbox chứa nhiều hơn một tenant')
    if problems:
        return EnvironmentAttestation(safe=False, reason='Môi trường không an toàn: ' + '; '.join(problems) + '.')
    return EnvironmentAttestation(safe=True, reason=(f"Sandbox {facts['database']} (role {facts['role']}, tenant eval) không kết nối được "
                                                     f"database nguồn {facts['source_database']}; không superuser, không BYPASSRLS."))


def map_agents(raw: dict, source_of: dict[str, str]) -> dict:
    """Agent ids in the trace as the case names them: the eval copies become their source agents."""
    def one(value):
        return source_of.get(value, value) if isinstance(value, str) else value
    for group in ('messages', 'participants', 'tool_calls', 'retrievals', 'citations', 'outputs'):
        for record in raw.get(group, []):
            if record.get('agent_id'):
                record['agent_id'] = one(record['agent_id'])
    for decision in raw.get('routing', []):
        decision['selected_agent_ids'] = [one(a) for a in decision.get('selected_agent_ids', [])]
    return raw


@dataclass
class Played:
    trace: dict | None
    refs: dict
    usage: dict
    error: dict | None


class Worker:
    def __init__(self, settings: Settings, client: httpx.AsyncClient, *, clock=time.monotonic, sleep=asyncio.sleep):
        self.settings, self.client, self.clock, self.sleep = settings, client, clock, sleep
        self.api = Api(client, settings.backend_url, settings.service_token)
        self.sandbox = Api(client, settings.sandbox_url, settings.sandbox_token)
        self.cancelled = False

    async def register(self) -> None:
        """The sandbox's catalogue, so management can write cases against it without calling the sandbox."""
        catalog = await self.sandbox.json('GET', '/internal/agent-eval/sandbox/v1/catalog')
        await self.api.json('PUT', '/internal/agent-eval/v1/environment', json={
            'execution_tenant_id': catalog['tenant_id'], 'fixture_version': catalog['fixture_version'],
            'runtime_profile': {'sandbox': 'EVAL_SANDBOX_URL', 'worker': self.settings.worker_id},
            'catalog': {k: catalog[k] for k in ('fixtures', 'documents', 'tools')}})

    async def once(self) -> bool:
        """Claim and play one run; False when nothing is queued."""
        claimed = await self.api.json('POST', '/internal/agent-eval/v1/runs/claim', json={'worker': self.settings.worker_id})
        if not claimed.get('run'):
            return False
        await self.play(claimed)
        return True

    async def heartbeat(self, run_id: str) -> None:
        last = self.clock()
        while True:
            await self.sleep(HEARTBEAT_SECONDS)
            try:
                reply = await self.api.call('POST', f'/internal/agent-eval/v1/runs/{run_id}/heartbeat', json={'worker': self.settings.worker_id})
                status = reply.status_code
            except httpx.HTTPError:
                status = None
            if status == 200:
                last = self.clock()
            # Cancelled, or a lease that could not be renewed in time: another run may take the sandbox, so stop.
            if status == 409 or self.clock() - last >= LEASE_SECONDS - HEARTBEAT_SECONDS:
                self.cancelled = True
                return

    async def events(self, run_id: str, events: list[dict]) -> None:
        if events and not self.cancelled:
            await self.api.call('POST', f'/internal/agent-eval/v1/runs/{run_id}/events', json={'worker': self.settings.worker_id, 'events': events})

    async def safety(self, execution_tenant_id: str) -> EnvironmentAttestation:
        facts = await self.sandbox.json('GET', '/internal/agent-eval/sandbox/v1/attestation')
        attestation = attest(facts, execution_tenant_id)
        if not attestation.safe:
            raise Unsafe(attestation)
        return attestation

    async def play(self, claimed: dict) -> None:
        run, snapshot = claimed['run'], claimed['run']['snapshot']
        run_id, worker = run['id'], self.settings.worker_id
        judge_model = ModelConfig.from_api(claimed['judge_model']) if claimed.get('judge_model') else self.settings.fallback_model
        self.cancelled = False
        beating = asyncio.create_task(self.heartbeat(run_id))
        error = None
        try:
            await self.safety(snapshot['environment']['execution_tenant_id'])
            agents = [{'source_id': snapshot['target']['agent_id'], 'name': snapshot['target']['name'],
                       'configuration': snapshot['target']['configuration'],
                       'model': ({k: snapshot['target']['model'][k] for k in ('provider', 'model_name')} if snapshot['target'].get('model') else None)},
                      *({'source_id': c['agent_id'], 'name': c['name'], 'configuration': c['configuration'],
                         'model': ({k: c['model'][k] for k in ('provider', 'model_name')} if c.get('model') else None)} for c in snapshot['collaborators'])]
            installed = await self.sandbox.call('POST', '/internal/agent-eval/sandbox/v1/install', json={'run_id': run_id, 'agents': agents})
            if installed.status_code == 409:
                error = {'code': 'environment_unsupported', 'message': installed.json().get('detail', '')[:500]}
                return
            installed.raise_for_status()
            mapping = installed.json()['agents']
            await self.events(run_id, [{'kind': 'lifecycle', 'payload': {'step': 'installed', 'agents': len(mapping)}}])
            for raw in sorted(claimed['cases'], key=lambda c: c['ordinal']):
                if self.cancelled:
                    raise Stop()
                await self.case(run_id, snapshot, raw, mapping, judge_model)
        except Unsafe as unsafe:
            error = {'code': 'environment_unsafe', 'message': unsafe.attestation.reason}
        except Stop:
            return
        except (httpx.HTTPError, KeyError, ValueError) as failure:
            log.exception('run %s failed', run_id)
            error = {'code': 'worker_error', 'message': str(failure)[:500]}
        finally:
            beating.cancel()
            if not self.cancelled:
                await self.api.call('POST', f'/internal/agent-eval/v1/runs/{run_id}/finish', json={'worker': worker, 'error': error})

    async def case(self, run_id: str, snapshot: dict, raw: dict, mapping: dict[str, str], judge_model: ModelConfig | None) -> None:
        worker = self.settings.worker_id
        case = EvalCase.model_validate({k: raw[k] for k in ('name', 'kind', 'source', 'input', 'expectations', 'rubric', 'metric_policy')})
        await self.api.json('PUT', f"/internal/agent-eval/v1/runs/{run_id}/cases/{raw['id']}", json={'worker': worker, 'status': 'running'})
        started = datetime.now(UTC)
        attestation = await self.safety(snapshot['environment']['execution_tenant_id'])
        played = await self.converse(run_id, raw['id'], case)
        attempts = 1
        if played.error is not None or (played.trace or {}).get('terminal_state') is None:
            # A model call cut off or a service refusing mid-way leaves the conversation nowhere. That is the stack's
            # trouble, not the agent's answer: the case is played once more, in a new conversation.
            await self.events(run_id, [{'case_id': raw['id'], 'kind': 'lifecycle', 'payload': {'step': 'retry', 'reason': (played.error or {}).get('code', 'no_terminal_state')}}])
            first, played, attempts = played, await self.converse(run_id, raw['id'], case, attempt=2), 2
            played.refs['first_attempt'] = {'error': first.error, 'channel_id': first.refs.get('channel_id')}
        played.refs['attempts'] = attempts
        source_of = {copy: source for source, copy in mapping.items()}
        trace, checks, judgement, metrics, usage = None, None, None, [], dict(played.usage)
        error = played.error
        if played.trace is not None:
            try:
                trace = Trace.model_validate(map_agents(played.trace, source_of))
            except ValidationError as invalid:
                error = error or {'code': 'invalid_trace', 'message': str(invalid)[:500]}
        if trace is not None:
            # What the case's fixture profile says, never what the run reported about itself.
            catalog = await self.sandbox.json('GET', '/internal/agent-eval/sandbox/v1/catalog')
            profile = next((f for f in catalog['fixtures'] if f['fixture_profile_id'] == case.input.fixture_profile_id), {})
            expected = ExecutionContext(tenant_id=snapshot['environment']['execution_tenant_id'], resident_id=profile.get('resident_id'),
                                        unit_id=profile.get('unit_id'), building_id=profile.get('building_id'))
            granted = {snapshot['target']['agent_id']: snapshot['target']['configuration'].get('mcp_tools', []),
                       **{c['agent_id']: c['configuration'].get('mcp_tools', []) for c in snapshot['collaborators']}}
            ctx = CheckContext(
                expected=expected, grants={a: frozenset((t['server_id'], t['name']) for t in tools) for a, tools in granted.items()},
                tool_schemas={(t['server_id'], t['name']): t.get('input_schema') or {} for t in snapshot['tools']},
                leak_literals=tuple({*mapping, *mapping.values(), snapshot['environment']['execution_tenant_id'], run_id,
                                     *(played.refs.get('ticket_ids') or [])}))
            results = run_checks(case, trace, ctx)
            checks = {k: r.model_dump() for k, r in results.items()}
            judged, judge_usage = await judge(self.client, judge_model, case, trace, results, timeout=self.settings.judge_seconds,
                                              target=snapshot['target']['agent_id'])
            judgement = judged.model_dump()
            usage.update(judge_input_tokens=judge_usage.input_tokens, judge_output_tokens=judge_usage.output_tokens)
            metrics = [m.model_dump() for m in await score_metrics(case, trace, snapshot['evaluator'], judge_model)]
            await self.events(run_id, [{'case_id': raw['id'], 'kind': 'tool', 'payload': {
                'tool': f'{c.server_id}/{c.name}', 'status': c.status, 'agent': c.agent_id}} for c in trace.tool_calls][:150] +
                [{'case_id': raw['id'], 'kind': 'state', 'payload': {'terminal_state': trace.terminal_state}}])
        await self.api.json('PUT', f"/internal/agent-eval/v1/runs/{run_id}/cases/{raw['id']}", json={
            'worker': worker, 'status': 'done', 'execution_refs': played.refs, 'trace': trace.model_dump(mode='json') if trace else None,
            'checks': checks, 'judge': judgement, 'metrics': metrics, 'environment': attestation.model_dump(), 'usage': usage,
            'error': error, 'started_at': started.isoformat(), 'finished_at': datetime.now(UTC).isoformat()})

    async def converse(self, run_id: str, case_id: str, case: EvalCase, attempt: int = 1) -> Played:
        """Speak as the fixture resident until the recorded state settles, then close the conversation's work."""
        base = '/internal/agent-eval/sandbox/v1/conversations'
        opened = await self.sandbox.json('POST', base, json={'fixture_profile_id': case.input.fixture_profile_id, 'title': case.name[:160]})
        channel = opened['channel_id']
        follow_ups, sent = list(case.input.follow_up_messages), 1
        deadline = self.clock() + self.settings.case_seconds
        read, error, last_seen = None, None, None
        try:
            await self.sandbox.json('POST', f'{base}/{channel}/messages', json={'text': case.input.message, 'client_message_id': f'{run_id}:{case_id}:{attempt}:0'})
            await self.events(run_id, [{'case_id': case_id, 'kind': 'message', 'payload': {'role': 'resident', 'turn': 0}}])
            while True:
                if self.cancelled:
                    raise Stop()
                await self.sleep(self.settings.settle_seconds)
                read = await self.sandbox.json('GET', f'{base}/{channel}/trace')
                trace, progress = read['trace'], read['progress']
                # Settled: the same state on two reads in a row, nothing answering or working any more.
                seen = (trace['terminal_state'], len(trace['messages']), tuple(progress['team_status']), tuple(progress['pending']))
                settled = trace['terminal_state'] is not None and seen == last_seen
                last_seen = seen
                if settled and trace['terminal_state'] == 'information_requested' and follow_ups:
                    # A person asked several things answers them together; the declared answers go out as one message.
                    text, route = ' '.join(follow_ups), ('answers' if 'information' in progress['pending'] else 'messages')
                    follow_ups.clear()
                    await self.sandbox.json('POST', f'{base}/{channel}/{route}', json={'text': text, 'client_message_id': f'{run_id}:{case_id}:{attempt}:{sent}'})
                    await self.events(run_id, [{'case_id': case_id, 'kind': 'message', 'payload': {'role': 'resident', 'turn': sent}}])
                    sent, last_seen = sent + 1, None
                    continue
                if settled or progress['stalled']:
                    break
                if self.clock() > deadline:
                    error = {'code': 'case_timeout', 'message': f'Ca chưa kết thúc sau {int(self.settings.case_seconds)} giây'}
                    trace.setdefault('issues', []).append({'id': 'i-case-timeout', 'kind': 'timeout', 'code': 'case_timeout', 'message': error['message']})
                    break
        finally:
            closed = await self.sandbox.call('POST', f'{base}/{channel}/close')
            if closed.status_code >= 400:
                log.warning('closing %s answered %s', channel, closed.status_code)
        refs = dict(read['refs']) if read else {'channel_id': channel}
        return Played(read['trace'] if read else None, refs, read['usage'] if read else {}, error)
