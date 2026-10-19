import {
	Bot,
	Check,
	CheckCircle2,
	CircleAlert,
	CircleDashed,
	CircleMinus,
	FlaskConical,
	Gavel,
	ListChecks,
	Loader2,
	MessageSquareText,
	PlayCircle,
	ShieldCheck,
	Wrench,
	XCircle,
} from 'lucide-react';
import { useState } from 'react';

import type { BuilderEval, BuilderEvalAgent, BuilderEvalCase } from '@/api';
import { Badge } from '@/components/ui/badge';
import { TaskProgress } from '@/components/ui/task-progress';
import { cn } from '@/lib/utils';

const CASE_STATUS: Record<BuilderEvalCase['status'], string> = {
	pending: 'Chờ chạy',
	running: 'Agent đang xử lý',
	checking: 'Đối chiếu điều kiện',
	judging: 'AI đang chấm',
	passed: 'Đạt',
	failed: 'Chưa đạt',
	error: 'Lỗi chạy',
};

const STEPS = [
	{ label: 'Sinh test case', icon: FlaskConical },
	{ label: 'Agent chạy từng ca', icon: PlayCircle },
	{ label: 'Đối chiếu điều kiện', icon: ListChecks },
	{ label: 'AI chấm và kết luận', icon: Gavel },
];

const CRITERIA = [
	{ key: 'task_completion', label: 'Đúng hành vi mong đợi', short: 'Hành vi' },
	{ key: 'evidence', label: 'Có căn cứ, không bịa', short: 'Căn cứ' },
	{ key: 'scope_safety', label: 'Đúng phạm vi và an toàn', short: 'An toàn' },
	{ key: 'tool_use', label: 'Dùng công cụ phù hợp', short: 'Công cụ' },
];

const CHECK_LABEL: Record<string, string> = {
	known_tools: 'Chỉ dùng công cụ của agent',
	expect_tool: 'Dùng đúng công cụ mong đợi',
	answered: 'Có câu trả lời',
};

const TOOL_MODE: Record<string, { label: string; tone: string }> = {
	fixture: { label: 'Dữ liệu giả lập', tone: 'bg-sky-100 text-sky-800 dark:bg-sky-950/50 dark:text-sky-300' },
	simulated: { label: 'Mô phỏng, không ghi', tone: 'bg-muted text-muted-foreground' },
	error: { label: 'Công cụ không có', tone: 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300' },
};

const FINISHED = new Set(['passed', 'failed', 'error']);
const seconds = (ms?: number) => (ms == null ? '' : `${(ms / 1000).toFixed(1)} giây`);

/** Which of the four steps the run is in. */
function currentStep(run: BuilderEval, tests: BuilderEvalCase[]): number {
	if (run.status !== 'running') return STEPS.length;
	if (tests.length === 0 || run.agents.some((agent) => agent.stage === 'generating')) return 0;
	if (tests.some((test) => test.status === 'judging')) return 3;
	if (tests.some((test) => test.status === 'checking')) return 2;
	return 1;
}

function CaseIcon({ status }: { status: BuilderEvalCase['status'] }) {
	if (status === 'passed') return <CheckCircle2 className="size-4 text-emerald-600" />;
	if (status === 'failed') return <XCircle className="size-4 text-red-600" />;
	if (status === 'error') return <CircleAlert className="size-4 text-amber-600" />;
	if (status === 'pending') return <CircleDashed className="size-4 text-muted-foreground" />;
	return <Loader2 className="size-4 animate-spin text-primary" />;
}

/** The run as it happens: the four steps, a bar of cases, each case's status. */
export function BuilderEvalProgress({ run }: { run: BuilderEval }) {
	const tests = run.agents.flatMap((agent) => agent.tests);
	const done = tests.filter((test) => FINISHED.has(test.status)).length;
	const passed = tests.filter((test) => test.status === 'passed').length;
	const live = run.status === 'running';
	const step = currentStep(run, tests);
	return (
		<section aria-label="Tiến trình đánh giá" className="space-y-4 rounded-2xl border border-border/70 bg-background p-4">
			<div className="flex flex-wrap items-center justify-between gap-2">
				<h3 className="text-sm font-semibold">Tiến trình đánh giá</h3>
				<span role="status" aria-live="polite" className="text-xs text-muted-foreground">
					{live ? 'Đang chạy' : run.status === 'error' ? 'Gián đoạn' : 'Đã hoàn tất'}
					{tests.length > 0 && ` · ${done}/${tests.length} ca xong · ${passed} đạt`}
				</span>
			</div>
			<ol aria-label="Các bước đánh giá" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
				{STEPS.map(({ label, icon: Icon }, index) => {
					const complete = index < step;
					const active = live && index === step;
					return (
						<li
							key={label}
							aria-current={active ? 'step' : undefined}
							className={cn(
								'flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors',
								active
									? 'border-primary bg-primary/10 text-foreground'
									: complete
										? 'border-emerald-300/70 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300'
										: 'border-border/70 text-muted-foreground',
							)}
						>
							<span
								className={cn(
									'flex size-6 shrink-0 items-center justify-center rounded-full',
									active ? 'bg-primary text-primary-foreground' : complete ? 'bg-emerald-500 text-white' : 'bg-muted',
								)}
							>
								{complete ? <Check className="size-3.5" /> : active ? <Loader2 className="size-3.5 animate-spin" /> : <Icon className="size-3.5" />}
							</span>
							<span className="font-medium">{label}</span>
						</li>
					);
				})}
			</ol>
			{live && run.started_at && (
				<TaskProgress label="Eval đang sinh và chạy test case…" startedAt={new Date(run.started_at).getTime()} />
			)}
			{tests.length > 0 && (
				<div className="flex h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={tests.length} aria-valuenow={done}>
					{tests.map((test) => (
						<span
							key={test.id}
							className={cn(
								'h-full flex-1 border-r border-background last:border-r-0',
								test.status === 'passed'
									? 'bg-emerald-500'
									: test.status === 'failed'
										? 'bg-red-500'
										: test.status === 'error'
											? 'bg-amber-400'
											: test.status === 'pending'
												? 'bg-transparent'
												: 'animate-pulse bg-primary/50',
							)}
						/>
					))}
				</div>
			)}
			{run.agents.map((agent) => (
				<div key={agent.name} className="space-y-2">
					<p className="text-sm font-medium">
						{agent.name}
						{agent.stage === 'generating' && <span className="ml-2 text-xs font-normal text-muted-foreground">Đang sinh test case…</span>}
						{agent.error && <span className="ml-2 text-xs font-normal text-amber-700">{agent.error}</span>}
					</p>
					<ul className="grid gap-2 sm:grid-cols-2">
						{agent.tests.map((test, index) => (
							<li
								key={test.id}
								className={cn(
									'flex items-start gap-2 rounded-xl border px-3 py-2 text-sm',
									test.status === 'failed' ? 'border-red-300/60' : test.status === 'error' ? 'border-amber-300/60' : 'border-border/70',
								)}
							>
								<span className="mt-0.5"><CaseIcon status={test.status} /></span>
								<span className="line-clamp-2 min-w-0 flex-1">Ca {index + 1}: {test.scenario}</span>
								<span className="shrink-0 text-[11px] text-muted-foreground">{CASE_STATUS[test.status]}</span>
							</li>
						))}
					</ul>
				</div>
			))}
			<p className="text-xs text-muted-foreground">Tiến độ đọc từ server, cập nhật mỗi 2 giây.</p>
		</section>
	);
}

function Mark({ passed, title }: { passed: boolean | undefined; title?: string }) {
	if (passed === undefined) return <CircleMinus aria-label="Không áp dụng" className="size-4 text-muted-foreground/50" />;
	return passed ? (
		<CheckCircle2 aria-label={title ? `${title}: đạt` : 'Đạt'} className="size-4 text-emerald-600" />
	) : (
		<XCircle aria-label={title ? `${title}: chưa đạt` : 'Chưa đạt'} className="size-4 text-red-600" />
	);
}

function ScoreRing({ passed, total }: { passed: number; total: number }) {
	const rate = total ? passed / total : 0;
	const circumference = 2 * Math.PI * 26;
	return (
		<div className="relative size-16 shrink-0" role="img" aria-label={`Đạt ${passed} trên ${total} ca`}>
			<svg viewBox="0 0 64 64" className="size-16 -rotate-90">
				<circle cx="32" cy="32" r="26" className="fill-none stroke-muted" strokeWidth="7" />
				<circle
					cx="32"
					cy="32"
					r="26"
					strokeWidth="7"
					strokeLinecap="round"
					className={cn('fill-none transition-[stroke-dashoffset] duration-700', rate >= 0.8 ? 'stroke-emerald-500' : rate >= 0.5 ? 'stroke-amber-500' : 'stroke-red-500')}
					strokeDasharray={circumference}
					strokeDashoffset={circumference * (1 - rate)}
				/>
			</svg>
			<span className="absolute inset-0 flex flex-col items-center justify-center leading-none">
				<span className="text-base font-semibold tabular-nums">{Math.round(rate * 100)}%</span>
				<span className="mt-0.5 text-[10px] text-muted-foreground tabular-nums">{passed}/{total}</span>
			</span>
		</div>
	);
}

function CaseTimeline({ test }: { test: BuilderEvalCase }) {
	const result = test.result;
	return (
		<ol className="relative mt-3 space-y-3 border-l border-border/70 pl-5 text-xs">
			<li className="relative">
				<span className="absolute -left-[27px] flex size-5 items-center justify-center rounded-full bg-background ring-1 ring-border"><MessageSquareText className="size-3" /></span>
				<p className="font-medium text-foreground">Khách nói</p>
				<p className="mt-1 rounded-xl rounded-tl-sm bg-muted/60 px-3 py-2 text-sm text-foreground">{test.scenario}</p>
			</li>
			{(result?.tool_calls ?? []).map((call, index) => {
				const mode = TOOL_MODE[call.mode] ?? TOOL_MODE.simulated;
				return (
					<li key={index} className="relative">
						<span className="absolute -left-[27px] flex size-5 items-center justify-center rounded-full bg-background ring-1 ring-border"><Wrench className="size-3" /></span>
						<p className="flex flex-wrap items-center gap-1.5">
							<span className="font-medium text-foreground">{call.name}</span>
							<span className={cn('rounded-full px-2 py-0.5 text-[11px]', mode.tone)}>{mode.label}</span>
						</p>
					</li>
				);
			})}
			<li className="relative">
				<span className="absolute -left-[27px] flex size-5 items-center justify-center rounded-full bg-background ring-1 ring-border"><Bot className="size-3" /></span>
				<p className="font-medium text-foreground">Agent trả lời</p>
				<p className="mt-1 whitespace-pre-wrap rounded-xl rounded-tl-sm border border-border/70 px-3 py-2 text-sm leading-relaxed text-foreground">
					{result?.answer || 'Chưa có câu trả lời được đánh giá.'}
				</p>
			</li>
			<li className="relative">
				<span className="absolute -left-[27px] flex size-5 items-center justify-center rounded-full bg-background ring-1 ring-border"><Gavel className="size-3" /></span>
				<p className="font-medium text-foreground">Bộ chấm</p>
				{result?.error && <p className="mt-1 rounded-lg bg-amber-50 p-2 dark:bg-amber-950/30">{result.error}</p>}
				{result?.summary && <p className="mt-1 text-sm text-foreground">{result.summary}</p>}
				{!!result?.criteria?.length && (
					<ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
						{result.criteria.map((criterion) => (
							<li key={criterion.name} className={cn('rounded-lg p-2', criterion.passed ? 'bg-emerald-50 dark:bg-emerald-950/30' : 'bg-red-50 dark:bg-red-950/30')}>
								<p className="flex items-center gap-1.5 font-medium text-foreground">
									<Mark passed={criterion.passed} />
									{CRITERIA.find((item) => item.key === criterion.name)?.label ?? criterion.name}
								</p>
								{criterion.reason && <p className="mt-1 text-muted-foreground">{criterion.reason}</p>}
							</li>
						))}
					</ul>
				)}
				{!!result?.checks?.length && (
					<ul className="mt-2 space-y-1">
						{result.checks.map((check) => (
							<li key={check.name} className="flex items-center gap-1.5"><Mark passed={check.passed} /> {CHECK_LABEL[check.name] ?? check.name}</li>
						))}
					</ul>
				)}
			</li>
		</ol>
	);
}

type Verdict = 'passed' | 'failed' | 'error';
const verdictOf = (test: BuilderEvalCase): Verdict =>
	test.status === 'passed' ? 'passed' : test.status === 'failed' ? 'failed' : 'error';

/** One agent's finished evaluation: score, criteria table and every case. Advisory only. */
export function BuilderEvalReport({ agent }: { agent: BuilderEvalAgent }) {
	const [filter, setFilter] = useState<'all' | Verdict>('all');
	const [open, setOpen] = useState<string | null>(null);
	const tests = agent.tests;
	const counts = { passed: 0, failed: 0, error: 0 };
	for (const test of tests) counts[verdictOf(test)] += 1;
	const total = tests.length;
	const criterion = (test: BuilderEvalCase, key: string) => test.result?.criteria?.find((item) => item.name === key)?.passed;
	const safetyTests = tests.filter((test) => test.safety);
	const shown = tests.map((test, index) => ({ test, index })).filter(({ test }) => filter === 'all' || verdictOf(test) === filter);

	if (agent.stage === 'error') {
		return (
			<p className="flex items-start gap-2 rounded-xl border border-amber-300/60 bg-amber-50/50 p-3 text-sm dark:bg-amber-950/20">
				<CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
				{agent.name}: {agent.error ?? 'Không đánh giá được agent này.'}
			</p>
		);
	}

	return (
		<section aria-label={`Kết quả đánh giá ${agent.name}`} className="space-y-4 rounded-2xl border border-border/70 bg-background p-4">
			<div className="flex flex-wrap items-center gap-4">
				<ScoreRing passed={counts.passed} total={total} />
				<div className="min-w-0 flex-1 space-y-1.5">
					<div className="flex flex-wrap items-center gap-2">
						<h3 className="text-sm font-semibold">{agent.name}</h3>
						<Badge variant="outline" className={counts.passed === total ? 'text-emerald-700' : 'text-amber-700'}>
							{counts.passed === total ? 'Đạt tất cả ca' : 'Tham khảo · không chặn phát hành'}
						</Badge>
					</div>
					<div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
						<span className="bg-emerald-500" style={{ width: `${(counts.passed / Math.max(total, 1)) * 100}%` }} />
						<span className="bg-red-500" style={{ width: `${(counts.failed / Math.max(total, 1)) * 100}%` }} />
						<span className="bg-amber-400" style={{ width: `${(counts.error / Math.max(total, 1)) * 100}%` }} />
					</div>
					<p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
						<span><i className="mr-1 inline-block size-2 rounded-full bg-emerald-500" />{counts.passed} đạt</span>
						<span><i className="mr-1 inline-block size-2 rounded-full bg-red-500" />{counts.failed} chưa đạt</span>
						<span><i className="mr-1 inline-block size-2 rounded-full bg-amber-400" />{counts.error} lỗi chạy/chấm</span>
						{safetyTests.length > 0 && (
							<span>
								<ShieldCheck className="mr-0.5 inline size-3" />
								An toàn {safetyTests.filter((test) => test.status === 'passed').length}/{safetyTests.length}
							</span>
						)}
						{agent.finished_at && <span>{new Date(agent.finished_at).toLocaleString('vi-VN')}</span>}
					</p>
				</div>
			</div>

			{total > 0 && (
				<div className="overflow-x-auto rounded-xl border border-border/70">
					<table className="w-full text-xs">
						<thead className="bg-muted/40 text-muted-foreground">
							<tr>
								<th scope="col" className="px-3 py-2 text-left font-medium">Ca</th>
								{CRITERIA.map((item) => {
									const passed = tests.filter((test) => criterion(test, item.key) === true).length;
									const judged = tests.filter((test) => criterion(test, item.key) !== undefined).length;
									return (
										<th key={item.key} scope="col" className="px-2 py-2 text-center font-medium" title={item.label}>
											{item.short}
											<span className="block text-[10px] font-normal tabular-nums">{judged ? `${passed}/${judged}` : '–'}</span>
										</th>
									);
								})}
								<th scope="col" className="px-3 py-2 text-right font-medium">Kết quả</th>
							</tr>
						</thead>
						<tbody>
							{tests.map((test, index) => {
								const verdict = verdictOf(test);
								return (
									<tr key={test.id} onClick={() => { setFilter('all'); setOpen(test.id); }} className="cursor-pointer border-t border-border/50 hover:bg-muted/40">
										<td className="max-w-[16rem] truncate px-3 py-2" title={test.scenario}>
											<span className="mr-1.5 font-medium tabular-nums">{index + 1}.</span>{test.scenario}
										</td>
										{CRITERIA.map((item) => (
											<td key={item.key} className="px-2 py-2"><span className="flex justify-center"><Mark passed={criterion(test, item.key)} title={item.label} /></span></td>
										))}
										<td className="px-3 py-2 text-right">
											<span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium', verdict === 'passed' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300' : verdict === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300' : 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300')}>
												{verdict === 'passed' ? 'Đạt' : verdict === 'failed' ? 'Chưa đạt' : 'Lỗi'}
											</span>
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			)}

			<div role="tablist" aria-label="Lọc ca" className="flex flex-wrap gap-1.5">
				{([['all', `Tất cả ${total}`], ['failed', `Chưa đạt ${counts.failed}`], ['error', `Lỗi ${counts.error}`], ['passed', `Đạt ${counts.passed}`]] as const).map(([key, label]) => (
					<button
						key={key}
						type="button"
						role="tab"
						aria-selected={filter === key}
						onClick={() => setFilter(key)}
						className={cn('rounded-full px-3 py-1 text-xs transition-colors', filter === key ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground')}
					>
						{label}
					</button>
				))}
			</div>

			<ol className="space-y-2">
				{shown.map(({ test, index }) => {
					const verdict = verdictOf(test);
					const expanded = open === test.id || (open === null && verdict !== 'passed');
					return (
						<li key={test.id} className={cn('rounded-xl border p-3 text-sm', verdict === 'passed' ? 'border-border/70' : verdict === 'failed' ? 'border-red-300/60' : 'border-amber-300/60')}>
							<button type="button" aria-expanded={expanded} onClick={() => setOpen(expanded ? '' : test.id)} className="flex w-full items-start gap-2 text-left">
								<span className="mt-0.5"><CaseIcon status={test.status} /></span>
								<span className="min-w-0 flex-1">
									<span className="font-semibold">Ca {index + 1}</span> · {test.scenario}
									<span className="mt-0.5 block text-xs text-muted-foreground">Mong đợi: {test.expected}</span>
								</span>
								<span className="shrink-0 text-xs text-muted-foreground">{seconds(test.result?.latency_ms)}</span>
							</button>
							{expanded && <CaseTimeline test={test} />}
						</li>
					);
				})}
			</ol>
		</section>
	);
}
