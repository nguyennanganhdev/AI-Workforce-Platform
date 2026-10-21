import { ArrowDown, ArrowUp, FlaskConical, LoaderCircle, Play, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { agentEvalApi, type AgentEvalCase, type AgentEvalRun } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

interface Props {
	agentId: string;
	agentName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

const FINISHED = new Set(['passed', 'failed', 'error']);
const when = (iso: string) => new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });

function StatusBadge({ status }: { status: string }) {
	const { t } = useTranslation();
	const tone = status === 'passed' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300'
		: status === 'failed' || status === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300'
			: 'bg-muted text-muted-foreground';
	return <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium', tone)}>{t(`agentEval.status.${status}`)}</span>;
}

/** Saved test cases of one agent, and the runs that replay them. */
export function AgentEvalDialog({ agentId, agentName, open, onOpenChange }: Props) {
	const { t } = useTranslation();
	const [cases, setCases] = useState<AgentEvalCase[]>([]);
	const [runs, setRuns] = useState<AgentEvalRun[]>([]);
	const [selected, setSelected] = useState<AgentEvalRun | null>(null);
	const [adding, setAdding] = useState(false);
	const [scenario, setScenario] = useState('');
	const [expected, setExpected] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');

	const load = useCallback(async () => {
		const [nextCases, nextRuns] = await Promise.all([agentEvalApi.listCases(agentId), agentEvalApi.listRuns(agentId)]);
		setCases(nextCases);
		setRuns(nextRuns);
		return nextRuns;
	}, [agentId]);

	const select = useCallback(async (run: AgentEvalRun, all: AgentEvalRun[]) => {
		const previous = all[all.findIndex((item) => item.id === run.id) + 1];
		setSelected(await agentEvalApi.getRun(agentId, run.id, previous?.id));
	}, [agentId]);

	useEffect(() => {
		if (!open) return;
		setError('');
		load().then((all) => all[0] && void select(all[0], all)).catch(() => setError(t('agentEval.loadFailed')));
	}, [open, load, select, t]);

	// A running suite saves after every case; follow it until it ends.
	useEffect(() => {
		if (!open || selected?.status !== 'running') return;
		const timer = window.setTimeout(() => {
			load().then((all) => {
				const current = all.find((item) => item.id === selected.id);
				if (current) void select(current, all);
			}).catch(() => undefined);
		}, 2000);
		return () => window.clearTimeout(timer);
	}, [open, selected, load, select]);

	const run = async () => {
		setBusy(true);
		setError('');
		try {
			const started = await agentEvalApi.startRun(agentId);
			setSelected(started);
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : t('agentEval.runFailed'));
		} finally {
			setBusy(false);
		}
	};

	const addCase = async () => {
		if (!scenario.trim() || !expected.trim()) return;
		setBusy(true);
		try {
			await agentEvalApi.createCase(agentId, { scenario: scenario.trim(), expected: expected.trim() });
			setScenario('');
			setExpected('');
			setAdding(false);
			await load();
		} finally {
			setBusy(false);
		}
	};

	const removeCase = async (caseId: string) => {
		await agentEvalApi.deleteCase(agentId, caseId);
		await load();
	};

	const running = runs.some((item) => item.status === 'running');
	const changes = new Map((selected?.comparison?.cases ?? []).map((row) => [row.case_id, row.change]));

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2"><FlaskConical className="size-4" />{t('agentEval.title', { name: agentName })}</DialogTitle>
					<DialogDescription>{t('agentEval.description')}</DialogDescription>
				</DialogHeader>
				{error && <p className="text-sm text-destructive">{error}</p>}

				<section className="flex flex-col gap-2">
					<div className="flex items-center justify-between gap-2">
						<h3 className="text-sm font-medium">{t('agentEval.cases', { count: cases.length })}</h3>
						<div className="flex gap-2">
							<Button variant="outline" size="sm" onClick={() => setAdding((value) => !value)}>
								<Plus /> {t('agentEval.addCase')}
							</Button>
							<Button size="sm" onClick={() => void run()} disabled={busy || running || cases.length === 0}>
								{running ? <LoaderCircle className="motion-safe:animate-spin" /> : <Play />} {t('agentEval.runAll')}
							</Button>
						</div>
					</div>
					{adding && (
						<div className="flex flex-col gap-2 rounded-xl border p-3">
							<Textarea value={scenario} onChange={(event) => setScenario(event.target.value)} placeholder={t('agentEval.scenarioPlaceholder')} rows={2} />
							<Textarea value={expected} onChange={(event) => setExpected(event.target.value)} placeholder={t('agentEval.expectedPlaceholder')} rows={2} />
							<Button size="sm" className="self-end" onClick={() => void addCase()} disabled={busy || !scenario.trim() || !expected.trim()}>
								{t('agentEval.save')}
							</Button>
						</div>
					)}
					{cases.length === 0 ? (
						<p className="rounded-xl border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">{t('agentEval.noCases')}</p>
					) : (
						<ul className="divide-y rounded-xl border">
							{cases.map((item) => (
								<li key={item.id} className="flex items-start gap-2 px-3 py-2 text-xs">
									<div className="min-w-0 flex-1">
										<p className="break-words font-medium">{item.scenario}</p>
										<p className="mt-0.5 break-words text-muted-foreground">→ {item.expected}</p>
										{Object.keys(item.recorded).length > 0 && (
											<p className="mt-0.5 text-[10px] text-muted-foreground">
												{t('agentEval.recorded', { tools: Object.keys(item.recorded).join(', ') })}
											</p>
										)}
									</div>
									<Button variant="ghost" size="icon-sm" aria-label={t('agentEval.deleteCase')} onClick={() => void removeCase(item.id)}>
										<Trash2 />
									</Button>
								</li>
							))}
						</ul>
					)}
				</section>

				{runs.length > 0 && (
					<section className="flex flex-col gap-2">
						<h3 className="text-sm font-medium">{t('agentEval.runs')}</h3>
						<div className="flex flex-wrap gap-1.5">
							{runs.map((item) => (
								<button
									key={item.id}
									type="button"
									onClick={() => void select(item, runs)}
									className={cn('rounded-lg border px-2 py-1 text-left text-[11px] hover:bg-accent', selected?.id === item.id && 'border-primary bg-accent')}
								>
									<span className="block font-mono">{item.version}</span>
									<span className="block text-muted-foreground">
										{when(item.started_at)} · {item.report ? `${item.report.passed}/${item.report.total}` : t(`agentEval.status.${item.status}`)}
									</span>
								</button>
							))}
						</div>
					</section>
				)}

				{selected && (
					<section className="flex flex-col gap-2">
						<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
							<Badge variant="secondary" className="font-mono">{selected.version}</Badge>
							<span>{selected.model}</span>
							{selected.report && <span>{t('agentEval.passRate', { passed: selected.report.passed, total: selected.report.total })}</span>}
							{selected.comparison && <span>{t('agentEval.comparedWith', { version: selected.comparison.version ?? '' })}</span>}
						</div>
						<ul className="flex flex-col gap-2">
							{selected.tests.map((test) => {
								const change = changes.get(test.case_id);
								return (
									<li key={test.case_id} className="rounded-xl border px-3 py-2 text-xs">
										<div className="flex items-start gap-2">
											<p className="min-w-0 flex-1 break-words font-medium">{test.scenario}</p>
											{change === 'better' && <ArrowUp className="size-3.5 text-emerald-600" aria-label={t('agentEval.better')} />}
											{change === 'worse' && <ArrowDown className="size-3.5 text-destructive" aria-label={t('agentEval.worse')} />}
											{FINISHED.has(test.status) ? <StatusBadge status={test.status} />
												: <LoaderCircle className="size-3.5 text-muted-foreground motion-safe:animate-spin" />}
										</div>
										{test.result?.summary && <p className="mt-1 break-words text-muted-foreground">{test.result.summary}</p>}
										{test.result?.error && <p className="mt-1 text-destructive">{test.result.error}</p>}
										{test.result?.answer && (
											<details className="mt-1">
												<summary className="cursor-pointer text-muted-foreground">{t('agentEval.answer')}</summary>
												<p className="mt-1 whitespace-pre-wrap break-words">{test.result.answer}</p>
											</details>
										)}
									</li>
								);
							})}
						</ul>
					</section>
				)}
			</DialogContent>
		</Dialog>
	);
}
