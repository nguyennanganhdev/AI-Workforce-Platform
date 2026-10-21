import { CheckCircle2, LoaderCircle, TriangleAlert, Wrench } from 'lucide-react';
import { useEffect, useState } from 'react';

import { sessionApi, type CaseFile } from '@/api';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useTranslation } from '@/i18n/useI18n';
import { readableToolName, summarizeToolArgs } from '@/lib/teamThreads';

interface Props {
	sessionId: string | null;
	agentId: string | null;
	/** The answer whose turn to show; null closes the sheet. */
	messageId: string | null;
	onClose: () => void;
}

const tokens = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
const usd = (value: number) => `$${value < 0.01 ? value.toFixed(4) : value.toFixed(2)}`;

/** Which lookups backed one answer, and what each agent spent on the turn. */
export function CaseFileSheet({ sessionId, agentId, messageId, onClose }: Props) {
	const { t } = useTranslation();
	const [caseFile, setCaseFile] = useState<CaseFile | null>(null);
	const [error, setError] = useState(false);

	useEffect(() => {
		if (!messageId || !sessionId || !agentId) return;
		let current = true;
		setCaseFile(null);
		setError(false);
		sessionApi
			.caseFile(sessionId, agentId, messageId)
			.then((value) => current && setCaseFile(value))
			.catch(() => current && setError(true));
		return () => {
			current = false;
		};
	}, [messageId, sessionId, agentId]);

	return (
		<Sheet open={messageId !== null} onOpenChange={(open) => !open && onClose()}>
			<SheetContent className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-lg">
				<SheetHeader>
					<SheetTitle>{t('caseFile.title')}</SheetTitle>
					<SheetDescription>{t('caseFile.description')}</SheetDescription>
				</SheetHeader>
				<div className="flex flex-col gap-5 px-4 pb-6">
					{error ? (
						<p className="text-sm text-destructive">{t('caseFile.loadFailed')}</p>
					) : !caseFile ? (
						<p className="flex items-center gap-2 text-sm text-muted-foreground">
							<LoaderCircle className="size-4 motion-safe:animate-spin" /> {t('caseFile.loading')}
						</p>
					) : (
						<>
							{caseFile.turn.customer_text && (
								<section>
									<h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
										{t('caseFile.question')}
									</h3>
									<p className="whitespace-pre-wrap break-words rounded-xl bg-muted/50 px-3 py-2 text-sm">
										{caseFile.turn.customer_text}
									</p>
								</section>
							)}

							<section>
								<h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
									{t('caseFile.cost')}
								</h3>
								<div className="grid grid-cols-3 gap-2 text-center">
									<div className="rounded-xl border px-2 py-2">
										<p className="text-[11px] text-muted-foreground">{t('caseFile.input')}</p>
										<p className="font-mono text-sm tabular-nums">{tokens(caseFile.totals.input_tokens)}</p>
										{caseFile.totals.cache_input_tokens > 0 && (
											<p className="text-[10px] text-muted-foreground">
												{t('caseFile.cached', { count: tokens(caseFile.totals.cache_input_tokens) })}
											</p>
										)}
									</div>
									<div className="rounded-xl border px-2 py-2">
										<p className="text-[11px] text-muted-foreground">{t('caseFile.output')}</p>
										<p className="font-mono text-sm tabular-nums">{tokens(caseFile.totals.output_tokens)}</p>
									</div>
									<div className="rounded-xl border px-2 py-2">
										<p className="text-[11px] text-muted-foreground">{t('caseFile.money')}</p>
										<p className="font-mono text-sm tabular-nums">
											{caseFile.totals.cost_usd !== null ? usd(caseFile.totals.cost_usd) : '—'}
										</p>
									</div>
								</div>
								{!caseFile.totals.priced && (
									<p className="mt-2 text-[11px] text-muted-foreground">{t('caseFile.unpriced')}</p>
								)}
								<ul className="mt-3 divide-y rounded-xl border">
									{caseFile.agents.map((agent) => (
										<li key={agent.agent_id} className="flex items-center gap-2 px-3 py-2 text-xs">
											<ClayAvatar id={agent.agent_id} label={agent.name} size={22} />
											<span className="min-w-0 flex-1">
												<span className="block truncate font-medium">{agent.name}</span>
												<span className="block truncate text-[10px] text-muted-foreground">
													{agent.model ?? '—'} · {t('caseFile.replies', { count: agent.replies })}
												</span>
											</span>
											<span className="shrink-0 text-right font-mono tabular-nums text-muted-foreground">
												↑{tokens(agent.input_tokens)} ↓{tokens(agent.output_tokens)}
												{agent.cost_usd !== null && <span className="block text-foreground">{usd(agent.cost_usd)}</span>}
											</span>
										</li>
									))}
								</ul>
							</section>

							<section>
								<h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
									{t('caseFile.evidence', { count: caseFile.evidence.length })}
								</h3>
								{caseFile.evidence.length === 0 ? (
									<p className="text-sm text-muted-foreground">{t('caseFile.noEvidence')}</p>
								) : (
									<ol className="flex flex-col gap-2">
										{caseFile.evidence.map((item, index) => {
											const args = summarizeToolArgs(item.arguments);
											const failed = item.state !== 'success';
											return (
												<li key={`${item.agent_id}-${index}`} className="rounded-xl border px-3 py-2">
													<div className="flex items-start gap-2 text-xs">
														{failed ? (
															<TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-destructive" />
														) : (
															<CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
														)}
														<span className="min-w-0 flex-1">
															<span className="font-medium">{readableToolName(item.tool)}</span>
															{args && <span className="text-muted-foreground"> · {args}</span>}
															<span className="block text-[10px] text-muted-foreground">
																<Wrench className="mr-1 inline size-3" />
																{item.agent_name}
																{failed ? ` · ${t('caseFile.failed')}` : ''}
															</span>
														</span>
													</div>
													{item.result && (
														<details className="mt-1.5 text-[11px]">
															<summary className="cursor-pointer text-muted-foreground hover:text-foreground">
																{t('caseFile.result')}
															</summary>
															<pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-2 font-mono text-[10px] leading-4">
																{item.result}
															</pre>
														</details>
													)}
												</li>
											);
										})}
									</ol>
								)}
							</section>
						</>
					)}
				</div>
			</SheetContent>
		</Sheet>
	);
}
