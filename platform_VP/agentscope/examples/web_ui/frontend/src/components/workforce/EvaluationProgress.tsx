import { Check, CheckCircle2, CircleAlert, CircleDashed, FlaskConical, Gavel, ListChecks, Loader2, PlayCircle, XCircle } from 'lucide-react';

import type { EvalProgress } from '@/api';
import { Badge } from '@/components/ui/badge';
import { TaskProgress } from '@/components/ui/task-progress';
import { cn } from '@/lib/utils';

const STAGE: Record<string, string> = { preparing: 'Chuẩn bị môi trường', generating: 'Sinh cấu hình và test case', tests_ready: 'Đã sinh test case',
	pending: 'Chờ chạy', running: 'Agent đang xử lý', checking: 'Đối chiếu điều kiện', judging: 'AI đang chấm',
	passed: 'Đạt', failed: 'Chưa đạt', error: 'Lỗi chạy', completed: 'Đã hoàn tất', interrupted: 'Mất cập nhật', case_completed: 'Đã cập nhật kết quả ca' };

const STEPS = [
	{ label: 'Sinh test case', icon: FlaskConical },
	{ label: 'Agent chạy từng ca', icon: PlayCircle },
	{ label: 'Đối chiếu điều kiện', icon: ListChecks },
	{ label: 'AI chấm và kết luận', icon: Gavel },
];

/** Which of the four steps the run is in, from its stage and its cases. */
function currentStep(progress: EvalProgress, done: number, total: number): number {
	if (progress.status === 'completed') return STEPS.length;
	if (['preparing', 'generating'].includes(progress.stage) || total === 0) return 0;
	if (progress.stage === 'judging') return 3;
	if (progress.stage === 'checking') return 2;
	return done === total ? 3 : 1;
}

function CaseIcon({ status }: { status: string }) {
	if (status === 'passed') return <CheckCircle2 className="size-4 text-emerald-600" />;
	if (status === 'failed') return <XCircle className="size-4 text-red-600" />;
	if (status === 'error') return <CircleAlert className="size-4 text-amber-600" />;
	if (status === 'pending') return <CircleDashed className="size-4 text-muted-foreground" />;
	return <Loader2 className="size-4 animate-spin text-primary" />;
}

export function EvaluationProgress({ progress }: { progress: EvalProgress }) {
	const tests = progress.agents.flatMap((agent) => agent.tests);
	const done = tests.filter((test) => ['passed', 'failed', 'error'].includes(test.status)).length;
	const live = progress.status === 'running';
	const step = currentStep(progress, done, tests.length);
	const passed = tests.filter((test) => test.status === 'passed').length;
	return (
		<section aria-label="Tiến độ đánh giá" className="space-y-4 rounded-2xl border border-border/70 bg-background p-4">
			<div className="flex flex-wrap items-center justify-between gap-2">
				<h3 className="text-sm font-semibold">{live ? 'Đang tạo và đánh giá agent' : 'Tiến trình đánh giá'}</h3>
				<span role="status" aria-live="polite" className="text-xs text-muted-foreground">
					{STAGE[progress.status === 'interrupted' ? 'interrupted' : progress.stage] ?? 'Đang xử lý'}
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
								'relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors',
								active ? 'border-primary bg-primary/10 text-foreground' : complete ? 'border-emerald-300/70 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300' : 'border-border/70 text-muted-foreground',
							)}
						>
							<span className={cn('flex size-6 shrink-0 items-center justify-center rounded-full', active ? 'bg-primary text-primary-foreground' : complete ? 'bg-emerald-500 text-white' : 'bg-muted')}>
								{complete ? <Check className="size-3.5" /> : active ? <Loader2 className="size-3.5 animate-spin" /> : <Icon className="size-3.5" />}
							</span>
							<span className="font-medium">{label}</span>
						</li>
					);
				})}
			</ol>

			{live && <TaskProgress label={STAGE[progress.stage] ?? 'Đang xử lý'} startedAt={new Date(progress.started_at).getTime()} />}
			{tests.length > 0 && (
				<div className="flex h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Số ca đã hoàn tất" aria-valuemin={0} aria-valuemax={tests.length} aria-valuenow={done}>
					{tests.map((test) => (
						<span
							key={test.id}
							className={cn('h-full flex-1 border-r border-background transition-colors last:border-r-0', test.status === 'passed' ? 'bg-emerald-500' : test.status === 'failed' ? 'bg-red-500' : test.status === 'error' ? 'bg-amber-400' : test.status === 'pending' ? 'bg-transparent' : 'animate-pulse bg-primary/50')}
						/>
					))}
				</div>
			)}
			{progress.error && <p role="alert" className="text-sm text-destructive">{progress.error}</p>}

			{progress.agents.map((agent, index) => (
				<div key={`${agent.name}-${index}`} className="space-y-2">
					<p className="text-sm font-medium">{agent.name}</p>
					<ul className="grid gap-2 sm:grid-cols-2">
						{agent.tests.map((test, i) => (
							<li key={test.id}>
								<details className={cn('rounded-xl border px-3 py-2 text-sm', ['failed'].includes(test.status) ? 'border-red-300/60' : test.status === 'error' ? 'border-amber-300/60' : 'border-border/70')}>
									<summary className="flex cursor-pointer items-start gap-2">
										<span className="mt-0.5"><CaseIcon status={test.status} /></span>
										<span className="min-w-0 flex-1 line-clamp-2">Ca {i + 1}: {test.scenario}</span>
										<span className="shrink-0 text-[11px] text-muted-foreground">
											{STAGE[test.status] ?? test.status}{test.status === 'running' && test.step ? ` · bước ${test.step}` : ''}
										</span>
									</summary>
									<div className="mt-2 space-y-1.5 text-xs text-muted-foreground">
										<p>Mong đợi: {test.expected}</p>
										{test.safety_critical && <Badge variant="outline">An toàn bắt buộc</Badge>}
										{test.expect_tool && <p>Tool mong đợi: {test.expect_tool}</p>}
										{test.result?.error && <p className="text-destructive">{test.result.error}</p>}
										{test.result?.judge && <p>Lý do chấm: {test.result.judge.reason}</p>}
									</div>
								</details>
							</li>
						))}
					</ul>
				</div>
			))}
			<p className="text-xs text-muted-foreground">Tiến độ đọc từ server, cập nhật mỗi 2 giây. Không tự gọi lại model khi kết nối gián đoạn.</p>
		</section>
	);
}
