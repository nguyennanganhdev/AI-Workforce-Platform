import { UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Bubble, BubbleContent } from '@/components/ui/bubble';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import './auth-showcase.css';

/**
 * The beats of one request, played on a loop: it arrives from a resident, the
 * Leader routes it to the right area and domain, hands it to the one agent
 * that fits, and that agent answers. What the product does, shown rather than
 * said, in the chat's own pieces (clay avatars, grey bubbles, status dots).
 */
const BEATS = ['idle', 'request', 'route', 'handoff', 'done'] as const;
type Beat = (typeof BEATS)[number];
/** How long each beat holds, in ms; the last one lingers so it can be read. */
const HOLD: Record<Beat, number> = {
	idle: 900,
	request: 1700,
	route: 1700,
	handoff: 1900,
	done: 3200,
};

/** The agents the Leader can choose from; the middle one gets the job. */
const AGENTS = [
	{ id: 'reception', label: 'Lễ tân', key: 'reception' },
	{ id: 'technical', label: 'Kỹ thuật', key: 'technical' },
	{ id: 'hotel', label: 'Khách sạn', key: 'hotel' },
] as const;
const CHOSEN = 'technical';

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

	const leaderWorking = beat === 'route';
	const agentWorking = beat === 'handoff';
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

			{/* The route a request travels: resident → Leader → the agent that fits. */}
			<div className="as-flow" aria-hidden="true">
				<div className={cn('as-node', step >= 1 && 'as-on')}>
					<span className="as-person">
						<UserRound className="size-5" />
					</span>
					<span className="as-name">{t('auth.showcase.resident')}</span>
				</div>

				<span className={cn('as-link', step >= 1 && 'as-link-on')}>
					{beat === 'request' && <span className="as-dot" />}
				</span>

				<div className={cn('as-node', step >= 2 && 'as-on')}>
					<span className={cn('as-ring', leaderWorking && 'as-ring-on')}>
						<ClayAvatar id="leader" label="Leader" size={48} working={leaderWorking} />
					</span>
					<span className="as-name">Leader</span>
				</div>

				<span className={cn('as-link', step >= 3 && 'as-link-on')}>
					{beat === 'handoff' && <span className="as-dot" />}
				</span>

				<ul className="as-agents">
					{AGENTS.map((agent) => {
						const chosen = agent.id === CHOSEN;
						return (
							<li
								key={agent.id}
								className={cn(
									'as-agent',
									step >= 3 && (chosen ? 'as-agent-chosen' : 'as-agent-passed'),
								)}
							>
								<ClayAvatar
									id={agent.id}
									label={agent.label}
									size={32}
									working={chosen && agentWorking}
								/>
								<span>{t(`auth.showcase.agents.${agent.key}`)}</span>
							</li>
						);
					})}
				</ul>
			</div>

			{/* Where it was routed: area and domain, the platform's two keys. */}
			<div className="as-route" aria-hidden="true">
				{step >= 2 && <span className="as-chip cue-pop">{t('auth.showcase.routed')}</span>}
			</div>

			<div className="as-chat" aria-hidden="true">
				{step >= 1 && (
					<Bubble variant="question" align="end" className="cue-pop self-end">
						<BubbleContent>{t('auth.showcase.request')}</BubbleContent>
					</Bubble>
				)}
				{beat === 'handoff' && (
					<span className="as-typing cue-pop">
						<span />
						<span />
						<span />
					</span>
				)}
				{beat === 'done' && (
					<div className="as-reply cue-pop">
						<ClayAvatar id="technical" label="Kỹ thuật" size={28} />
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
