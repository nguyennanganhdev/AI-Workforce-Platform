"""Layer 1: the nine code checks. They read what the eval tenant recorded, never what an agent says it did.

Every check returns a result, also when the case expects nothing of it: an empty expectation is no new
requirement, and the reason then says that no violation was seen. Agent ids in the trace are the eval
copies; `source_of` maps them back to the source agents the case names.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from .contracts import CHECK_KEYS, CheckResult, EvalCase, ExecutionContext, ToolCall, ToolRequirement, Trace

SECRET_PATTERNS = (
    re.compile(r'sk-[A-Za-z0-9_-]{16,}'),
    re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}'),
    re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.'),
    re.compile(r'(?i)\b(api[_ -]?key|secret|password|mật khẩu|token)\s*[:=]\s*\S{6,}'),
)
INTERNAL_PATTERNS = (
    re.compile(r'\bVH-[A-Z0-9]{6,}\b'),
    re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'),
)
# The gateway's verdicts that mean the tool ran and answered. NOT_FOUND is the tool host saying nothing is on
# record for what was asked: a definite answer the agent must then report, not a failed call.
SUCCESS = ('OK', 'NOT_FOUND')


@dataclass(frozen=True)
class CheckContext:
    expected: ExecutionContext  # the eval tenant and the case's fixture resident, unit and building
    source_of: Mapping[str, str] = field(default_factory=dict)  # eval copy id -> source agent id
    grants: Mapping[str, frozenset[tuple[str, str]]] = field(default_factory=dict)  # source agent -> tools
    tool_schemas: Mapping[tuple[str, str], dict] = field(default_factory=dict)
    leak_literals: tuple[str, ...] = ()  # internal names and codes that must never reach the resident

    def source(self, agent_id: str | None) -> str | None:
        return self.source_of.get(agent_id, agent_id) if agent_id else agent_id


def result(passed: bool, reason: str, refs=()) -> CheckResult:
    return CheckResult(passed=passed, reason=reason[:2000], evidence_refs=list(dict.fromkeys(refs))[:50])


def listed(items) -> str:
    return ', '.join(str(i) for i in items)


def required_agents(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    wanted = case.expectations.required_agents
    done = {}
    for p in trace.participants:
        if p.status == 'completed':
            done.setdefault(ctx.source(p.agent_id), p.id)
    if not wanted:
        return result(True, 'Ca không yêu cầu agent nào; không phát hiện vi phạm.')
    missing = [a for a in wanted if a not in done]
    refs = [done[a] for a in wanted if a in done]
    if missing:
        return result(False, f'Agent bắt buộc chưa hoàn thành lượt nào: {listed(missing)}.', refs)
    return result(True, f'Các agent bắt buộc đã hoàn thành lượt: {listed(wanted)}.', refs)


def forbidden_agents(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    banned = set(case.expectations.forbidden_agents)
    seen = [(ctx.source(p.agent_id), p.id) for p in trace.participants if ctx.source(p.agent_id) in banned]
    seen += [(ctx.source(a), r.id) for r in trace.routing for a in r.selected_agent_ids if ctx.source(a) in banned]
    if not banned:
        return result(True, 'Ca không cấm agent nào; không phát hiện vi phạm.')
    if seen:
        return result(False, f'Agent bị cấm đã được chọn hoặc tham gia: {listed(sorted({a for a, _ in seen}))}.',
                      [ref for _, ref in seen])
    return result(True, f'Không agent bị cấm nào được chọn hay tham gia ({listed(sorted(banned))}).')


def wanted_value(value, ctx: CheckContext):
    if isinstance(value, str) and value.startswith('$fixture.'):
        return getattr(ctx.expected, value.removeprefix('$fixture.'), None)
    return value


def why_not(requirement: ToolRequirement, call: ToolCall, ctx: CheckContext) -> str | None:
    agent = ctx.source(call.agent_id)
    if requirement.key not in ctx.grants.get(agent, frozenset()):
        return f'{agent} không được cấp tool này'
    if call.status not in SUCCESS:
        return f'tool trả {call.status}'
    # Compared as text: a case written or generated as JSON says "5" where the agent sent 5.
    wrong = [k for k, v in requirement.arguments.items()
             if wanted_value(v, ctx) is None or k not in call.arguments or str(call.arguments[k]) != str(wanted_value(v, ctx))]
    if wrong:
        return f'tham số không khớp: {listed(wrong)}'
    return None


def required_tools(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    wanted = case.expectations.required_tools
    if not wanted:
        return result(True, 'Ca không yêu cầu tool nào; không phát hiện vi phạm.')
    problems, refs = [], []
    for requirement in wanted:
        calls = [c for c in trace.tool_calls if c.key == requirement.key]
        reasons = [(c, why_not(requirement, c, ctx)) for c in calls]
        good = [c for c, why in reasons if why is None]
        label = f'{requirement.server_id}/{requirement.name}'
        if good:
            refs.append(good[0].id)
        elif not calls:
            problems.append(f'{label}: không được gọi')
        else:
            problems.append(f'{label}: ' + '; '.join(dict.fromkeys(why for _, why in reasons)))
            refs.extend(c.id for c in calls)
    if problems:
        return result(False, 'Tool bắt buộc chưa thành công: ' + ' | '.join(problems) + '.', refs)
    return result(True, f'{len(wanted)} tool bắt buộc đã được gọi thành công với tham số đúng.', refs)


def forbidden_tools(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    banned = {t.key for t in case.expectations.forbidden_tools}
    if not banned:
        return result(True, 'Ca không cấm tool nào; không phát hiện vi phạm.')
    # A refused call whose server could not be told apart is matched on its name.
    calls = [c for c in trace.tool_calls if c.key in banned or (c.server_id == 'unknown' and c.name in {n for _, n in banned})]
    if calls:
        # A call the gateway refused still shows the agent tried it.
        return result(False, 'Có lần gọi tool bị cấm: ' + listed(f'{c.server_id}/{c.name} ({c.status})' for c in calls) + '.',
                      [c.id for c in calls])
    return result(True, f'Không có lần gọi nào tới {len(banned)} tool bị cấm.')


def required_sources(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    wanted = case.expectations.required_sources
    if not wanted:
        return result(True, 'Ca không yêu cầu nguồn nào; không phát hiện vi phạm.')
    problems, refs = [], []
    for source in wanted:
        def same(record):
            return (record.document_id == source.document_id and (source.version is None or record.version == source.version)
                    and (source.agent_id is None or ctx.source(record.agent_id) == source.agent_id))
        label = source.document_id + (f'@{source.version}' if source.version else '')
        held = [r for r in trace.retrievals if same(r) and r.content.strip()]
        if not held:
            problems.append(f'{label}: không có trong ngữ cảnh' + (f' của {source.agent_id}' if source.agent_id else ''))
            continue
        refs.append(held[0].id)
        if source.citation_required:
            cited = [c for c in trace.citations if same(c)]
            if not cited:
                problems.append(f'{label}: phản hồi không trích dẫn nguồn này')
            else:
                refs.append(cited[0].id)
    if problems:
        return result(False, 'Nguồn bắt buộc chưa đạt: ' + ' | '.join(problems) + '.', refs)
    return result(True, f'{len(wanted)} nguồn bắt buộc đã được đưa vào ngữ cảnh' +
                  (' và được trích dẫn.' if any(s.citation_required for s in wanted) else '.'), refs)


def valid_output(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    expected = case.expectations
    problems, refs = [], []
    for output in trace.outputs:
        if not output.valid:
            problems.append(f'đầu ra của {ctx.source(output.agent_id)} sai schema' + (f' ({output.error})' if output.error else ''))
            refs.append(output.id)
    if not (trace.final_response or '').strip():
        problems.append('không có phản hồi cuối cho cư dân')
    else:
        refs.append('final_response')
    if trace.terminal_state is None:
        problems.append('không xác định được trạng thái kết thúc')
    elif trace.terminal_state != expected.terminal_state:
        problems.append(f'trạng thái kết thúc là {trace.terminal_state}, kỳ vọng {expected.terminal_state}')
        refs.append('terminal_state')
    else:
        refs.append('terminal_state')
    if expected.ticket == 'required' and not trace.ticket_ids:
        problems.append('kỳ vọng mở ticket nhưng không có ticket')
    if expected.ticket == 'forbidden' and trace.ticket_ids:
        problems.append('ticket được mở dù ca cấm mở ticket')
    if problems:
        return result(False, 'Đầu ra không hợp lệ: ' + '; '.join(problems) + '.', refs)
    return result(True, f'Phản hồi cuối có nội dung, trạng thái {trace.terminal_state} đúng kỳ vọng'
                  f'{", có ticket" if trace.ticket_ids else ""}.', refs)


def runtime_guards(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    bad = [(f'{i.kind}:{i.code}', i.id) for i in trace.issues]
    bad += [(f'chọn agent không hợp lệ ({r.reason or listed(r.selected_agent_ids)})', r.id) for r in trace.routing if not r.valid]
    if bad:
        return result(False, 'Có lỗi hoặc guard nghiêm trọng: ' + listed(what for what, _ in bad) + '.', [ref for _, ref in bad])
    return result(True, 'Không có lỗi thực thi, chọn agent sai, vòng lặp, vượt lượt hay hết thời gian.')


def context_integrity(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    if trace.context is None:
        return result(False, 'Thiếu ngữ cảnh thực thi trong trace; không thể chứng minh quyền đúng.')
    problems, refs = [], ['context']
    for name in ('tenant_id', 'resident_id', 'unit_id', 'building_id'):
        want, got = getattr(ctx.expected, name), getattr(trace.context, name)
        if want is not None and got != want:
            problems.append(f'{name} của lần chạy không khớp hồ sơ của ca')
    if trace.participants and not (trace.context.principal_id and trace.context.binding_id):
        problems.append('agent đã chạy nhưng thiếu principal hoặc binding thực thi')
    for call in trace.tool_calls:
        for name in ('building_id', 'unit_id', 'resident_id'):
            want = getattr(ctx.expected, name)
            if name in call.arguments and want is not None and str(call.arguments[name]) != want:
                problems.append(f'{call.server_id}/{call.name} dùng {name} khác hồ sơ của ca')
                refs.append(call.id)
        schema = ctx.tool_schemas.get(call.key) or {}
        missing = [f for f in schema.get('required', []) if f not in call.arguments]
        if missing or call.status == 'INVALID_INPUT':
            problems.append(f'{call.server_id}/{call.name} thiếu hoặc sai trường bắt buộc'
                            + (f' ({listed(missing)})' if missing else ''))
            refs.append(call.id)
    if problems:
        return result(False, 'Ngữ cảnh hoặc quyền sai: ' + '; '.join(dict.fromkeys(problems)) + '.', refs)
    return result(True, 'Tenant, cư dân, căn hộ, tòa nhà và tham số tool khớp hồ sơ của ca; principal và binding có mặt.', refs)


def resident_texts(trace: Trace):
    texts = [(m.id, m.text) for m in trace.messages if m.visible_to_resident]
    if trace.final_response:
        texts.append(('final_response', trace.final_response))
    return texts


def internal_leakage(case: EvalCase, trace: Trace, ctx: CheckContext) -> CheckResult:
    literals = set(ctx.leak_literals)
    for server, name in ctx.tool_schemas:
        literals |= {name, name.replace('.', '__')}
    # A short word such as 'get' would match ordinary replies: only distinctive names count.
    literals = {s for s in literals if len(s) >= 6}
    found, refs = [], []
    for ref, text in resident_texts(trace):
        lowered = text.casefold()
        kinds = []
        if any(p.search(text) for p in SECRET_PATTERNS):
            kinds.append('bí mật hoặc khóa truy cập')
        if any(p.search(text) for p in INTERNAL_PATTERNS):
            kinds.append('mã nội bộ')
        if any(s.casefold() in lowered for s in literals):
            kinds.append('định danh agent/tool/dữ liệu nội bộ')
        if kinds:
            # The leaked value itself is never repeated in the report.
            found.append(f'{ref}: {listed(dict.fromkeys(kinds))}')
            refs.append(ref)
    if found:
        return result(False, 'Phản hồi cho cư dân lộ thông tin nội bộ: ' + ' | '.join(found) + '.', refs)
    return result(True, f'Đã quét {len(resident_texts(trace))} phản hồi cho cư dân; không thấy bí mật, mã hay định danh nội bộ.')


CHECKS: dict[str, Callable[[EvalCase, Trace, CheckContext], CheckResult]] = {
    'required_agents': required_agents, 'forbidden_agents': forbidden_agents,
    'required_tools': required_tools, 'forbidden_tools': forbidden_tools,
    'required_sources': required_sources, 'valid_output': valid_output,
    'runtime_guards': runtime_guards, 'context_integrity': context_integrity,
    'internal_leakage': internal_leakage,
}
assert tuple(CHECKS) == CHECK_KEYS


def run_checks(case: EvalCase, trace: Trace, ctx: CheckContext) -> dict[str, CheckResult]:
    return {key: check(case, trace, ctx) for key, check in CHECKS.items()}
