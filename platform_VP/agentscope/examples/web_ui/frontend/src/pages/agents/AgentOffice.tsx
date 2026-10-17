import { Maximize2, MessageCircle, Pencil, X } from 'lucide-react';
import {
	lazy,
	type ReactNode,
	Suspense,
	useEffect,
	useMemo,
	useRef,
	useState,
	useSyncExternalStore,
} from 'react';

import { type GraphAgent, toGraphAgents } from './graph-model';
import { ROOM } from './office-palette';
import { buildLayout, LEADER_ID, OfficeSim, populate, roomLabels } from './office-sim';
import type { AgentView } from '@/api';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import './agent-graph.css';
import './agent-office.css';

/* ------------------------------------------------------------------ */
/* The view                                                            */
/* ------------------------------------------------------------------ */

const FLOAT =
	'rounded-full border border-[var(--cue-border,#e8e8e8)] bg-white/90 shadow-[0_2px_8px_rgba(0,0,0,0.06)] backdrop-blur';

function useOffice(
	agents: GraphAgent[],
	sessionId?: string,
) {
	const layout = useMemo(() => buildLayout(agents), [agents]);
	const [sim, setSim] = useState<OfficeSim | null>(null);

	useEffect(() => {
		const next = new OfficeSim();
		populate(next, layout, agents);
		setSim(next);

		return () => next.abort();
	}, [layout, agents, sessionId]);

	return { layout, sim };
}

const Office3D = lazy(() => import('./Office3D'));

/** Whether this browser can draw the office at all; without it a notice stands in. */
const WEBGL = (() => {
	try {
		const canvas = document.createElement('canvas');
		return !!(canvas.getContext('webgl2') ?? canvas.getContext('webgl'));
	} catch {
		return false;
	}
})();

export function AgentOffice({
	agents: apiAgents,
	session,
	onChat,
	onEdit,
}: {
	agents: AgentView[];
	session?: SessionOfficeSnapshot;
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
}) {
	const { agents: catalog } = useMemo(() => toGraphAgents(apiAgents), [apiAgents]);
	// Roster metadata stays stable while statuses/messages change, so the map is not rebuilt.
	const rosterKey = session
		? JSON.stringify(
				session.participants
					.filter((p) => p.id !== LEADER_ID)
					.map(({ id, name, role }) => ({ id, name, role })),
			)
		: null;
	const agents = useMemo<GraphAgent[]>(
		() =>
			rosterKey === null
				? catalog
				: (JSON.parse(rosterKey) as { id: string; name: string; role: string }[]).map(
						(agent) => ({ ...agent, invitable: true, real: null }),
					),
		[catalog, rosterKey],
	);
	const { layout, sim } = useOffice(agents, session?.id);
	const { t } = useTranslation();
	const [resetKey, setResetKey] = useState(0);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	useEffect(() => {
		if (sim && session?.motion === 'events') sim.applySession(session, layout);
	}, [session, sim, layout]);
	const roomNames = useMemo(
		() =>
			Object.fromEntries(
				roomLabels(layout).map(({ key }) => [key, t(`agents.office.rooms.${key}`)]),
			),
		[layout, t],
	);

	return (
		<div className="relative size-full overflow-hidden" style={{ background: ROOM.background }}>
			{!WEBGL ? (
				<p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[13px] text-[#8b8478]">
					{t('agents.office.noWebgl')}
				</p>
			) : (
				sim && (
					<Suspense fallback={null}>
						<Office3D
							layout={layout}
							sim={sim}
							selectedId={selectedId}
							setSelectedId={setSelectedId}
							roomNames={roomNames}
							offLabel={t('agents.graph.notInvitable')}
							resetKey={resetKey}
						/>
					</Suspense>
				)
			)}

			{WEBGL && (
				<div className={cn(FLOAT, 'absolute right-4 bottom-6 flex items-center p-1')}>
					<ChromeButton
						label={t('agents.office.resetView')}
						onClick={() => setResetKey((key) => key + 1)}
					>
						<Maximize2 className="size-4" />
					</ChromeButton>
				</div>
			)}

			{sim && (
				<OfficeChrome
					session={session}
					sim={sim}
					agents={agents}
					selectedId={selectedId}
					setSelectedId={setSelectedId}
					onChat={onChat}
					onEdit={onEdit}
				/>
			)}
		</div>
	);
}

function ChromeButton({
	label,
	onClick,
	children,
}: {
	label: string;
	onClick: () => void;
	children: ReactNode;
}) {
	return (
		<button
			type="button"
			onClick={onClick}
			aria-label={label}
			title={label}
			className="grid size-8 place-items-center rounded-full text-[#444] hover:bg-black/5"
		>
			{children}
		</button>
	);
}

function OfficeChrome({
	session,
	sim,
	agents,
	selectedId,
	setSelectedId,
	onChat,
	onEdit,
}: {
	session?: SessionOfficeSnapshot;
	sim: OfficeSim;
	agents: GraphAgent[];
	selectedId: string | null;
	setSelectedId: (id: string | null) => void;
	onChat: (agent: AgentView) => void;
	onEdit: (agent: AgentView) => void;
}) {
	const { t } = useTranslation();
	// Primitive snapshot stays equal during movement; only visible UI changes trigger a render.
	useSyncExternalStore(sim.subscribe, () => {
		const actor = selectedId ? sim.actors.get(selectedId) : undefined;
		return JSON.stringify([
			sim.phase,
			sim.playing,
			sim.speed,
			sim.log.map((entry) => entry.text),
			actor?.name,
			actor ? (actor.path.length ? 'walking' : actor.status) : null,
		]);
	});
	const selected =
		selectedId === LEADER_ID ? null : agents.find((agent) => agent.id === selectedId);
	const selectedActor = selectedId ? sim.actors.get(selectedId) : undefined;
	// Keep the newest entry in view once the capped log starts scrolling.
	const logRef = useRef<HTMLOListElement>(null);
	const lastLogId = sim.log.at(-1)?.id;
	useEffect(() => {
		const el = logRef.current;
		if (el) el.scrollTop = el.scrollHeight;
	}, [lastLogId]);
	return (
		<>
			{/* Chrome. */}
			<div className="absolute top-3 right-4 left-4 flex flex-wrap items-center gap-2">
				<span className="flex h-8 items-center gap-2 rounded-full bg-[#fff4dc] px-3 text-[12px] font-medium text-[#8a5a00]">
					<span className="size-1.5 rounded-full bg-[#d99a00]" />
					{t('agents.office.live')}
				</span>
				<span
					className={cn(
						FLOAT,
						'flex h-8 items-center gap-2 px-3 text-[12px] font-medium',
					)}
				>
					<span
						className={cn(
							'relative size-2 rounded-full',
							sim.phase === 'idle' ? 'bg-[#b5b5b5]' : 'ag-ping bg-[#34c759]',
						)}
					/>
					{session?.statusLabel ?? t(`agents.office.phase.${sim.phase}`)}
				</span>
			</div>

			{/* What just happened, newest last. */}
			<section
				aria-label={t('agents.office.log')}
				className={cn(
					// Top-right, below the status chips, so it never covers the office floor.
					'absolute top-14 right-4 flex max-h-[min(40%,320px)] w-[280px] flex-col rounded-[18px] border border-[var(--cue-border,#e8e8e8)] bg-white/92 p-3 shadow-[0_2px_8px_rgba(0,0,0,0.06)] backdrop-blur',
					// The adjacent session transcript already shows this activity on small screens.
					session && 'max-md:hidden',
				)}
			>
				<h2 className="mb-2 text-[12px] font-semibold text-muted-foreground">
					{t('agents.office.log')}
				</h2>
				<ol
					ref={logRef}
					className="flex min-h-0 flex-col gap-1.5 overflow-y-auto"
					aria-live="polite"
				>
					{sim.log.map((entry, index) => (
						<li
							key={entry.id}
							className={cn(
								'of-log flex gap-2 text-[12px]/4',
								index === sim.log.length - 1
									? 'text-foreground'
									: 'text-muted-foreground',
							)}
						>
							<span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-current opacity-60" />
							{entry.text}
						</li>
					))}
				</ol>
			</section>

			{selectedActor && (selected || selectedId === LEADER_ID) && (
				<section className="ag-panel-in absolute bottom-4 left-4 flex w-[280px] flex-col gap-3 rounded-[20px] border border-[var(--cue-border,#e8e8e8)] bg-white p-4 shadow-[var(--cue-shadow-float,0_8px_32px_rgba(0,0,0,0.1))]">
					<header className="flex items-start gap-3">
						<ClayAvatar
							id={selectedId === LEADER_ID ? 'leader' : selectedId!}
							label={selectedActor.name}
							size={40}
						/>
						<div className="min-w-0 flex-1">
							<h2 className="truncate text-[15px]/6 font-semibold">
								{selectedActor.name}
							</h2>
							<p className="text-[12px]/4 text-muted-foreground">
								{selectedId === LEADER_ID
									? t('agents.graph.leaderNote')
									: selected?.role || t('agents.list.noDescription')}
							</p>
						</div>
						<Button
							variant="ghost"
							size="icon-sm"
							aria-label={t('common.close')}
							onClick={() => setSelectedId(null)}
						>
							<X />
						</Button>
					</header>
					<p className="text-[12px] text-muted-foreground">
						{t(
							`agents.office.status.${selectedActor.path.length ? 'walking' : selectedActor.status}`,
						)}
					</p>
					{selected?.real && (
						<div className="flex gap-2">
							<Button
								size="sm"
								className="flex-1"
								onClick={() => onChat(selected.real!)}
							>
								<MessageCircle />
								{t('agents.list.chat')}
							</Button>
							<Button
								size="sm"
								variant="outline"
								className="flex-1"
								onClick={() => onEdit(selected.real!)}
							>
								<Pencil />
								{t('agents.list.edit')}
							</Button>
						</div>
					)}
				</section>
			)}
		</>
	);
}
