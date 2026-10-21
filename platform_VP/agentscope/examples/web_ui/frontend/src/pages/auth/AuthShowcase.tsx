import { UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Bubble, BubbleContent } from '@/components/ui/bubble';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import './auth-showcase.css';

/** One request moves through the team, then returns to the user. */
const BEATS = ['idle', 'request', 'route', 'handoff', 'share', 'review', 'report', 'done'] as const;
type Beat = (typeof BEATS)[number];
const HOLD: Record<Beat, number> = {
	idle: 900,
	request: 2200,
	route: 1800,
	handoff: 2400,
	share: 3200,
	review: 3200,
	report: 2600,
	done: 4200,
};

const AGENTS = ['agent1', 'agent2', 'agent3'] as const;
const TEAM_PATHS = {
	handoff: 'M0 44 H15 V13 H100',
	report: 'M100 87 H15 V44 H0',
};

function useReducedMotion() {
	const [reduced, setReduced] = useState(
		() =>
			typeof window !== 'undefined' &&
			window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
	);
	useEffect(() => {
		const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
		if (!query) return;
		const update = () => setReduced(query.matches);
		query.addEventListener('change', update);
		return () => query.removeEventListener('change', update);
	}, []);
	return reduced;
}

export function AuthShowcase() {
	const { t } = useTranslation();
	const reduced = useReducedMotion();
	const [index, setIndex] = useState(0);
	// Without motion, the finished request stands still as a single picture.
	const beat: Beat = reduced ? 'done' : BEATS[index];
	const step = BEATS.indexOf(beat);

	useEffect(() => {
		if (reduced) return;
		const timer = setTimeout(() => setIndex((i) => (i + 1) % BEATS.length), HOLD[beat]);
		return () => clearTimeout(timer);
	}, [beat, reduced]);

	const leaderWorking = beat === 'route' || beat === 'report';
	const activeAgents =
		beat === 'handoff'
			? ['agent1']
			: beat === 'share'
				? ['agent1', 'agent2']
				: beat === 'review'
					? ['agent2', 'agent3']
					: beat === 'report'
						? ['agent3']
						: [];
	const exchangeAgent = beat === 'review' ? 'agent2' : beat === 'report' ? 'agent3' : 'agent1';
	const status =
		beat === 'idle'
			? { tone: 'idle', label: t('auth.showcase.statusIdle') }
			: beat === 'done'
				? { tone: 'done', label: t('auth.showcase.statusDone') }
				: { tone: 'busy', label: t('auth.showcase.statusBusy') };

	return (
		<figure className="as-card" aria-label={t('auth.showcase.caption')}>
			<header className="as-head" aria-hidden="true">
				<span className="as-live">
					<span className="as-live-dot" />
					{t('auth.showcase.live')}
				</span>
				<span
					key={status.label}
					className={cn('as-status cue-pop', `as-status-${status.tone}`)}
				>
					<span className="as-status-dot" />
					{status.label}
				</span>
			</header>

			{/* The Leader coordinates the team; agents also exchange information directly. */}
			<div className="as-flow" aria-hidden="true">
				<div className={cn('as-node', step >= 1 && 'as-on')}>
					<span className="as-person">
						<UserRound className="size-5" />
					</span>
					<span className="as-name">{t('auth.showcase.user')}</span>
				</div>

				<span className={cn('as-link', step >= 1 && 'as-link-on')}>
					{(beat === 'request' || (beat === 'done' && !reduced)) && (
						<span key={beat} className={cn('as-dot', beat === 'done' && 'as-dot-return')} />
					)}
				</span>

				<div className={cn('as-node', step >= 2 && 'as-on')}>
					<span className={cn('as-ring', leaderWorking && 'as-ring-on')}>
						<ClayAvatar id="leader" label="Leader" size={48} working={leaderWorking} />
					</span>
					<span className="as-name">Leader</span>
				</div>

				<div className="as-team">
					<svg className="as-network" viewBox="0 0 100 100" preserveAspectRatio="none">
						<path
							className={cn('as-network-line', beat === 'done' && 'as-network-active')}
							d="M100 13 H15 V87 H100 M0 44 H15 M15 50 H100"
						/>
						{(beat === 'handoff' || beat === 'report') && (
							<g key={beat}>
								<path className="as-network-active" d={TEAM_PATHS[beat]} />
								<circle className="as-network-dot" r="3">
									<animateMotion dur="1.6s" path={TEAM_PATHS[beat]} fill="freeze" />
								</circle>
							</g>
						)}
					</svg>
					<ul className="as-agents">
						{AGENTS.map((agent, agentIndex) => {
							const working = activeAgents.includes(agent);
							const exchanging =
								(agentIndex === 0 && beat === 'share') ||
								(agentIndex === 1 && beat === 'review');
							return (
								<li
									key={agent}
									className={cn('as-agent', (working || beat === 'done') && 'as-agent-active')}
								>
									<ClayAvatar id={agent} label={agent} size={32} working={working} />
									<span>{agent}</span>
									{agentIndex < AGENTS.length - 1 && (
										<span className={cn('as-peer-link', (exchanging || beat === 'done') && 'as-peer-link-on')}>
											{exchanging && <span className="as-peer-dot" />}
										</span>
									)}
								</li>
							);
						})}
					</ul>
				</div>
			</div>

			{/* Describe the current exchange alongside the animated connections. */}
			<div className="as-route" aria-hidden="true">
				{step >= 2 && (
					<span key={beat} className="as-chip cue-pop">{t(`auth.showcase.stages.${beat}`)}</span>
				)}
			</div>

			<div className="as-chat" aria-hidden="true">
				{step >= 1 && (
					<Bubble variant="question" align="end" className="cue-pop self-end">
						<BubbleContent>{t('auth.showcase.request')}</BubbleContent>
					</Bubble>
				)}
				{step >= 3 && (
					<div key={beat} className="as-reply cue-pop">
						<ClayAvatar id={exchangeAgent} label={exchangeAgent} size={28} />
						<Bubble variant="agent">
							<BubbleContent className="whitespace-pre-line">
								{t(`auth.showcase.messages.${beat}`)}
							</BubbleContent>
						</Bubble>
					</div>
				)}
				{beat === 'done' && (
					<div className="as-reply cue-pop">
						<ClayAvatar id="leader" label="Leader" size={28} />
						<Bubble variant="agent">
							<BubbleContent>{t('auth.showcase.reply')}</BubbleContent>
						</Bubble>
					</div>
				)}
			</div>
			<figcaption className="sr-only">{t('auth.showcase.caption')}</figcaption>
		</figure>
	);
}
