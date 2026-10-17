import { CheckCircle2, CircleAlert, CircleDashed, Loader2 } from 'lucide-react';

import type { EvalProgress } from '@/api';
import { Badge } from '@/components/ui/badge';
import { TaskProgress } from '@/components/ui/task-progress';

const STAGE: Record<string, string> = { preparing: 'Chuẩn bị môi trường', generating: 'Sinh cấu hình và test case', tests_ready: 'Đã sinh test case',
	pending: 'Chờ chạy', running: 'Agent đang xử lý', checking: 'Đối chiếu điều kiện', judging: 'AI đang chấm',
	passed: 'Đạt', failed: 'Chưa đạt', error: 'Lỗi chạy', completed: 'Đã hoàn tất', interrupted: 'Mất cập nhật', case_completed: 'Đã cập nhật kết quả ca' };

export function EvaluationProgress({ progress }: { progress: EvalProgress }) {
	const tests = progress.agents.flatMap(agent => agent.tests);
	const completed = tests.filter(test => ['passed', 'failed', 'error'].includes(test.status)).length;
	const live = progress.status === 'running';
	const phase = ['preparing', 'generating'].includes(progress.stage) ? 1 : progress.stage === 'judging' ? 3 : 2;
	return <section aria-label="Tiến độ đánh giá" className="space-y-3 rounded-xl border border-border/70 p-4">
		<div className="flex flex-wrap items-center justify-between gap-2">
			<h3 className="text-sm font-semibold">{live ? 'Đang tạo và đánh giá agent' : 'Tiến trình đánh giá'}</h3>
			<span role="status" aria-live="polite" className="text-xs text-muted-foreground">{STAGE[progress.status === 'interrupted' ? 'interrupted' : progress.stage] ?? 'Đang xử lý'}{tests.length > 0 && ` · ${completed}/${tests.length} ca hoàn tất`}</span>
		</div>
		<ol aria-label="Các bước đánh giá" className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-3">
			{['Sinh test case', 'Chạy agent và kiểm tra điều kiện', 'AI chấm và kiểm tra phát hành'].map((label, i) => <li key={label} aria-current={live && phase === i + 1 ? 'step' : undefined} className={`rounded-lg px-3 py-2 ${live && phase === i + 1 ? 'bg-primary text-primary-foreground' : 'bg-muted/50'}`}>{progress.status === 'completed' ? '✓' : `${i + 1}.`} {label}</li>)}
		</ol>
		{live && <TaskProgress label={STAGE[progress.stage] ?? 'Đang xử lý'} startedAt={new Date(progress.started_at).getTime()} />}
		{tests.length > 0 && <progress aria-label="Số ca đã hoàn tất" max={tests.length} value={completed} className="h-2 w-full accent-primary" />}
		{progress.error && <p role="alert" className="text-sm text-destructive">{progress.error}</p>}
		{progress.agents.map((agent, index) => <div key={`${agent.name}-${index}`} className="space-y-2">
			<p className="text-sm font-medium">{agent.name}</p>
			{agent.tests.map((test, i) => <details key={test.id} className="rounded-lg border px-3 py-2 text-sm">
				<summary className="flex cursor-pointer items-start gap-2">
					{test.status === 'passed' ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" /> : ['failed', 'error'].includes(test.status) ? <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" /> : test.status === 'pending' ? <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted-foreground" /> : <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" />}
					<span className="min-w-0 flex-1">Ca {i + 1}: {test.scenario}</span>
					<span className="shrink-0 text-xs text-muted-foreground">{STAGE[test.status] ?? test.status}</span>
				</summary>
				<div className="mt-2 space-y-2 text-xs text-muted-foreground">
					<p>Mong đợi: {test.expected}</p>
					{test.safety_critical && <Badge variant="outline">An toàn bắt buộc</Badge>}
					{test.must_include?.length ? <p>Bắt buộc có: {test.must_include.join('; ')}</p> : null}
					{test.must_not_include?.length ? <p>Không được có: {test.must_not_include.join('; ')}</p> : null}
					{test.expect_tool && <p>Tool mong đợi: {test.expect_tool}</p>}
					{test.result?.error && <p className="text-destructive">{test.result.error}</p>}
					{test.result?.judge && <p>Lý do chấm: {test.result.judge.reason}</p>}
				</div>
			</details>)}
		</div>)}
		<p className="text-xs text-muted-foreground">Tiến độ đọc từ server, cập nhật mỗi 2 giây. Không tự gọi lại model khi kết nối gián đoạn.</p>
	</section>;
}
