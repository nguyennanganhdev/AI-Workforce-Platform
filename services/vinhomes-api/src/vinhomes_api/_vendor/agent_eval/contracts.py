"""Shapes shared by the evaluator and the business API. The API stores them as JSONB and decides pass/fail."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator, model_validator

SUITE_SIZE = 4
CHECK_KEYS = ('required_agents', 'forbidden_agents', 'required_tools', 'forbidden_tools', 'required_sources',
              'valid_output', 'runtime_guards', 'context_integrity', 'internal_leakage')
CRITERIA = ('bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao')
JUDGE_THRESHOLD = 4

Id = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Terminal = Literal['reply_only', 'information_requested', 'approval_pending', 'resolved']
Kind = Literal['in_scope', 'out_of_scope', 'collaboration', 'boundary']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ToolRef(Strict):
    server_id: Id
    name: Id

    @property
    def key(self) -> tuple[str, str]:
        return (self.server_id, self.name)


class ToolRequirement(ToolRef):
    # Each listed argument must have this value in a successful call. A value "$fixture.<field>"
    # stands for that field of the case's fixture profile (its building, unit or resident).
    arguments: dict[str, Any] = Field(default_factory=dict)


class SourceRef(Strict):
    document_id: Id
    version: str | None = Field(default=None, max_length=200)


class SourceRequirement(SourceRef):
    agent_id: str | None = Field(default=None, max_length=200)  # whose context must hold it; None: any agent
    citation_required: bool = False


class CaseInput(Strict):
    message: Text
    # Sent one by one, and only when the system asks the resident something. Never invented beyond these.
    follow_up_messages: list[Text] = Field(default_factory=list, max_length=5)
    fixture_profile_id: Id


class Expectations(Strict):
    required_agents: list[Id] = Field(default_factory=list, max_length=10)
    forbidden_agents: list[Id] = Field(default_factory=list, max_length=10)
    required_tools: list[ToolRequirement] = Field(default_factory=list, max_length=10)
    forbidden_tools: list[ToolRef] = Field(default_factory=list, max_length=20)
    required_sources: list[SourceRequirement] = Field(default_factory=list, max_length=10)
    ticket: Literal['required', 'forbidden', 'optional'] = 'optional'
    terminal_state: Terminal

    @model_validator(mode='after')
    def disjoint(self):
        if set(self.required_agents) & set(self.forbidden_agents):
            raise ValueError('An agent is both required and forbidden')
        if {t.key for t in self.required_tools} & {t.key for t in self.forbidden_tools}:
            raise ValueError('A tool is both required and forbidden')
        return self


class Rubric(Strict):
    score1_description: Text
    score2_description: Text
    score3_description: Text
    score4_description: Text
    score5_description: Text


class EvalCase(Strict):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    kind: Kind
    source: Literal['generated', 'manual'] = 'manual'
    input: CaseInput
    expectations: Expectations
    rubric: Rubric
    # Which library metrics apply to the expected behaviour; a metric left out follows default_policy().
    metric_policy: dict[Id, Literal['apply', 'not_applicable']] = Field(default_factory=dict)


# What was observed in the eval tenant. Every record has an id the checks and the judge cite as evidence.

class TraceMessage(Strict):
    id: Id
    role: Literal['resident', 'reception', 'agent', 'supervisor', 'system']
    agent_id: str | None = None
    text: str = Field(max_length=20000)
    visible_to_resident: bool = False


class Participation(Strict):
    id: Id
    agent_id: Id
    run_id: str | None = None
    status: Literal['running', 'completed', 'failed', 'refused']


class RoutingDecision(Strict):
    id: Id
    selected_agent_ids: list[Id] = Field(default_factory=list)
    valid: bool = True
    reason: str = Field(default='', max_length=2000)


class ToolCall(Strict):
    id: Id
    agent_id: Id
    server_id: Id
    name: Id
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Id  # the gateway's verdict: OK, TOOL_ERROR, FORBIDDEN, INVALID_INPUT, NOT_FOUND, AWAITING_CONFIRMATION...
    result: Any = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.server_id, self.name)


class Retrieval(Strict):
    id: Id
    agent_id: Id
    document_id: Id
    version: str | None = None
    chunk_id: Id
    rank: StrictInt = Field(ge=0)
    content: str = Field(max_length=20000)
    retrieval_run_id: str | None = None


class Citation(Strict):
    id: Id
    agent_id: str | None = None
    document_id: Id
    version: str | None = None


class AgentOutputRecord(Strict):
    id: Id
    agent_id: Id
    valid: bool
    error: str | None = None


class RuntimeIssue(Strict):
    id: Id
    kind: Literal['error', 'invalid_agent', 'loop', 'turn_limit', 'timeout']
    code: Id
    message: str = Field(default='', max_length=2000)


class ExecutionContext(Strict):
    tenant_id: str | None = None
    principal_id: str | None = None
    binding_id: str | None = None
    resident_id: str | None = None
    unit_id: str | None = None
    building_id: str | None = None


class Trace(Strict):
    messages: list[TraceMessage] = Field(default_factory=list)
    participants: list[Participation] = Field(default_factory=list)
    routing: list[RoutingDecision] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    retrievals: list[Retrieval] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    outputs: list[AgentOutputRecord] = Field(default_factory=list)
    issues: list[RuntimeIssue] = Field(default_factory=list)
    context: ExecutionContext | None = None
    ticket_ids: list[Id] = Field(default_factory=list)
    final_response: str | None = Field(default=None, max_length=20000)
    terminal_state: Terminal | None = None

    def refs(self) -> set[str]:
        groups = (self.messages, self.participants, self.routing, self.tool_calls, self.retrievals,
                  self.citations, self.outputs, self.issues)
        found = {record.id for group in groups for record in group}
        if self.context is not None:
            found.add('context')
        if self.final_response is not None:
            found.add('final_response')
        if self.terminal_state is not None:
            found.add('terminal_state')
        return found

    @model_validator(mode='after')
    def unique_ids(self):
        groups = (self.messages, self.participants, self.routing, self.tool_calls, self.retrievals,
                  self.citations, self.outputs, self.issues)
        ids = [record.id for group in groups for record in group]
        if len(ids) != len(set(ids)) or {'context', 'final_response', 'terminal_state'} & set(ids):
            raise ValueError('Trace record ids must be unique')
        return self


# Results. The API recomputes the verdict from these; it never takes a pass/fail from the worker.

class CheckResult(Strict):
    passed: bool
    reason: Text
    evidence_refs: list[Id] = Field(default_factory=list)


class JudgeAssessment(Strict):
    score: StrictInt = Field(ge=1, le=5)
    reason: Text
    evidence_refs: list[Id] = Field(min_length=1, max_length=20)

    @field_validator('reason')
    @classmethod
    def said_something(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('A reason is required')
        return value


class ErrorInfo(Strict):
    code: Id
    message: str = Field(default='', max_length=2000)


class JudgeResult(Strict):
    status: Literal['scored', 'error']
    backend: Id
    model_profile: Id
    threshold: Literal[4] = JUDGE_THRESHOLD
    criteria: dict[Literal['bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao'], JudgeAssessment] | None = None
    error: ErrorInfo | None = None

    @model_validator(mode='after')
    def complete(self):
        if self.status == 'scored' and (self.error is not None or self.criteria is None or set(self.criteria) != set(CRITERIA)):
            raise ValueError('A scored judgement has exactly the four criteria and no error')
        if self.status == 'error' and (self.error is None or self.criteria is not None):
            raise ValueError('A failed judgement has an error and no scores')
        return self


class MetricResult(Strict):
    name: Id
    backend: Id
    version: str | None = None
    status: Literal['scored', 'not_applicable', 'error']
    value: float | None = None
    threshold: float | None = None
    required: bool = False
    reason: str = Field(default='', max_length=2000)
    error: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def finite(self):
        if self.status == 'scored' and (self.value is None or not math.isfinite(self.value)):
            raise ValueError('A scored metric has a finite value')
        if self.status != 'scored' and self.value is not None:
            raise ValueError('Only a scored metric has a value')
        return self


class EnvironmentAttestation(Strict):
    safe: bool
    reason: Text
    evidence_refs: list[Id] = Field(default_factory=list)


# Suites. The same rules for a hand-written suite and a generated one.

@dataclass(frozen=True)
class SuiteScope:
    target_agent_id: str
    agent_ids: frozenset[str]  # the target and the agents allowed beside it
    tools: frozenset[tuple[str, str]]  # (server_id, name) granted to those agents
    sources: frozenset[tuple[str, str | None]]  # (document_id, version) the agents may read
    fixtures: frozenset[str]  # fixture profile ids of the eval tenant

    @classmethod
    def from_context(cls, context: dict) -> SuiteScope:
        agents = [context['agent'], *context.get('collaborators', [])]
        return cls(context['agent']['agent_id'], frozenset(a['agent_id'] for a in agents),
                   frozenset((t['server_id'], t['name']) for a in agents for t in a.get('tools', [])),
                   frozenset((s['document_id'], s.get('version')) for s in context.get('sources', [])),
                   frozenset(f['fixture_profile_id'] for f in context.get('fixtures', [])))


def validate_suite(raw_cases: list, scope: SuiteScope) -> tuple[list[EvalCase], list[str]]:
    """The cases and every reason the suite cannot be approved; a usable suite has no reasons."""
    problems: list[str] = []
    if not isinstance(raw_cases, list) or len(raw_cases) != SUITE_SIZE:
        problems.append(f'Bộ đánh giá cần đúng {SUITE_SIZE} ca.')
        raw_cases = raw_cases if isinstance(raw_cases, list) else []
    cases = []
    for number, raw in enumerate(raw_cases, 1):
        try:
            cases.append(EvalCase.model_validate(raw))
        except ValidationError as error:
            first = error.errors()[0]
            problems.append(f'Ca {number}: {".".join(str(p) for p in first["loc"])} {first["msg"]}.')
    kinds = {c.kind for c in cases}
    if len(cases) == SUITE_SIZE and not {'in_scope', 'out_of_scope'} <= kinds:
        # Without both, four cases can pass without ever showing the agent does its task or stays out of others'.
        problems.append('Bộ đánh giá cần ít nhất một ca trong năng lực và một ca ngoài năng lực.')
    names = [c.name.strip().casefold() for c in cases]
    if len(names) != len(set(names)):
        problems.append('Tên các ca phải khác nhau.')
    documents = {d for d, _ in scope.sources}
    for number, case in enumerate(cases, 1):
        e, say = case.expectations, lambda text: problems.append(f'Ca {number} ({case.name}): {text}')
        for agent in {*e.required_agents, *e.forbidden_agents, *(s.agent_id for s in e.required_sources if s.agent_id)}:
            if agent not in scope.agent_ids:
                say(f'agent {agent} không thuộc phạm vi đánh giá.')
        for tool in [*e.required_tools, *e.forbidden_tools]:
            if tool.key not in scope.tools:
                say(f'tool {tool.server_id}/{tool.name} không được cấp cho agent nào trong phạm vi.')
        for source in e.required_sources:
            if source.document_id not in documents or (source.version and (source.document_id, source.version) not in scope.sources):
                say(f'tài liệu {source.document_id} không thuộc nguồn được phép.')
        if case.input.fixture_profile_id not in scope.fixtures:
            say(f'hồ sơ mẫu {case.input.fixture_profile_id} không có trong tenant eval.')
        if case.kind == 'in_scope' and scope.target_agent_id not in e.required_agents:
            say('ca trong năng lực phải yêu cầu agent đang đánh giá.')
        if case.kind == 'out_of_scope' and scope.target_agent_id not in e.forbidden_agents:
            say('ca ngoài năng lực phải cấm chọn agent đang đánh giá.')
        if case.kind == 'collaboration' and not (scope.target_agent_id in e.required_agents and len(e.required_agents) >= 2):
            say('ca phối hợp phải yêu cầu agent đang đánh giá và ít nhất một agent khác.')
    return cases, problems


# Verdict. Computed by the business API from what the worker recorded, under the run's snapshot.

# A reply that asks for more or waits for approval is right behaviour, not a content answer:
# answer relevancy would punish it, so it does not apply there unless the case says so.
CONTENT_METRICS = ('answer_relevancy',)


def metric_applies(case: EvalCase, name: str) -> bool:
    if name in case.metric_policy:
        return case.metric_policy[name] == 'apply'
    return not (name in CONTENT_METRICS and case.expectations.terminal_state in ('information_requested', 'approval_pending'))


@dataclass(frozen=True)
class RequiredMetric:
    name: str
    threshold: float


def case_verdict(case: EvalCase, *, checks: dict | None, judge: dict | None, metrics: list | None,
                 environment: dict | None, error: dict | None, required_metrics: tuple[RequiredMetric, ...] = ()
                 ) -> tuple[Literal['passed', 'failed', 'error'], list[dict]]:
    """Pass only when all nine checks, all four criteria at 4 or more, every required metric that applies
    and the environment pass. A high score in one layer never makes up for another layer."""
    layers: list[dict] = []

    def note(layer: str, kind: str, detail: str):
        layers.append({'layer': layer, 'kind': kind, 'detail': detail[:500]})

    if error:
        note('execution', 'error', str(error.get('code') or error))
    try:
        parsed_checks = {k: CheckResult.model_validate(v) for k, v in (checks or {}).items()}
    except ValidationError:
        parsed_checks = None
    if parsed_checks is None or tuple(parsed_checks) != CHECK_KEYS:
        note('code', 'error', 'thiếu hoặc sai kết quả của 9 nhóm kiểm tra')
    else:
        failed = [k for k, r in parsed_checks.items() if not r.passed]
        if failed:
            note('code', 'failed', ', '.join(failed))
    try:
        parsed_judge = JudgeResult.model_validate(judge) if judge is not None else None
    except ValidationError:
        parsed_judge = None
    if parsed_judge is None or parsed_judge.status != 'scored':
        note('judge', 'error', parsed_judge.error.code if parsed_judge and parsed_judge.error else 'không có kết quả giám khảo')
    else:
        low = [c for c, a in parsed_judge.criteria.items() if a.score < JUDGE_THRESHOLD]
        if low:
            note('judge', 'failed', ', '.join(low))
    try:
        parsed_metrics = {m.name: m for m in (MetricResult.model_validate(m) for m in (metrics or []))}
    except ValidationError:
        parsed_metrics, metrics_broken = {}, True
    else:
        metrics_broken = False
    if metrics_broken:
        note('metric', 'error', 'kết quả metric sai dạng')
    for required in required_metrics:
        found = parsed_metrics.get(required.name)
        applies = metric_applies(case, required.name)
        if found is None or found.status == 'error' or (applies and found.status == 'not_applicable'):
            note('metric', 'error', f'{required.name}: thiếu, lỗi hoặc bị bỏ dù áp dụng')
        elif found.status == 'scored' and found.value < required.threshold:
            note('metric', 'failed', f'{required.name} {found.value:.3f} < {required.threshold}')
    try:
        parsed_environment = EnvironmentAttestation.model_validate(environment) if environment is not None else None
    except ValidationError:
        parsed_environment = None
    if parsed_environment is None:
        note('environment', 'error', 'không có xác nhận cô lập môi trường')
    elif not parsed_environment.safe:
        note('environment', 'failed', parsed_environment.reason)
    if any(layer['kind'] == 'failed' for layer in layers):
        return 'failed', layers
    return ('error' if layers else 'passed'), layers


def run_passed(statuses: list[str]) -> bool:
    """A run passes on four case results that all passed; three passes and a missing case do not."""
    return len(statuses) == SUITE_SIZE and all(s == 'passed' for s in statuses)
