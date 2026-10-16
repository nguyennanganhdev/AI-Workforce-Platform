import {
	LoaderCircle,
	Maximize2,
	MessageCircle,
	Pencil,
	RotateCcw,
	RotateCw,
	Users,
	X,
	ZoomIn,
	ZoomOut,
} from 'lucide-react';
import {
	Component,
	lazy,
	type ReactNode,
	Suspense,
	useEffect,
	useCallback,
	useMemo,
	useRef,
	useState,
	useSyncExternalStore,
} from 'react';

import { type GraphAgent, toGraphAgents } from './graph-model';
import { ROOM } from './office-palette';
import { buildLayout, LEADER_ID, OfficeSim, populate, roomLabels, USER_ID } from './office-sim';
import type { CameraCommand } from './Office3D';
import type { AgentView } from '@/api';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import './agent-graph.css';
import './agent-office.css';

/* ------------------------------------------------------------------ */
/* The view                                                            */
/* ------------------------------------------------------------------ */

const FLOAT =
	'rounded-full border border-border bg-background/95 text-foreground shadow-sm backdrop-blur';

function useOffice(agents: GraphAgent[], sessionId?: string, hostId: string | null = LEADER_ID) {
	const layout = useMemo(() => buildLayout(agents, hostId), [agents, hostId]);
	const [sim, setSim] = useState<OfficeSim | null>(null);

	useEffect(() => {
		const next = new OfficeSim();
		populate(next, layout, agents);
		setSim(next);
		let last = performance.now();
		let frame = 0;
		const tick = (now: number) => {
			if (!document.hidden) {
				if (next.tick(Math.min(now - last, 64))) next.publish();
			}
			last = now;
			frame = requestAnimationFrame(tick);
		};
		frame = requestAnimationFrame(tick);
		return () => {
			cancelAnimationFrame(frame);
			next.abort();
		};
	}, [layout, agents, sessionId]);

	return { layout, sim };
}

const Office3D = lazy(() => import('./Office3D'));

/** The installed Three renderer requires WebGL 2. Release the probe context immediately. */
function hasWebGL() {
	try {
		const canvas = document.createElement('canvas');
		const context = canvas.getContext('webgl2');
		context?.getExtension('WEBGL_lose_context')?.loseContext();
		return !!context;
	} catch {
		return false;
	}
}

class OfficeBoundary extends Component<
	{ children: ReactNode; fallback: ReactNode; onError: () => void },
	{ failed: boolean }
> {
	state = { failed: false };
	static getDerivedStateFromError() {
		return { failed: true };
	}
	componentDidCatch() {
		this.props.onError();
	}
	render() {
		return this.state.failed ? this.props.fallback : this.props.children;
	}
}

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
						(agent) => ({
							...agent,
							invitable: true,
							real: catalog.find((entry) => entry.id === agent.id)?.real ?? null,
						}),
					),
		[catalog, rosterKey],
	);
	const { layout, sim } = useOffice(agents, session?.id, session?.hostId);
	const { t } = useTranslation();
	const [webgl, setWebgl] = useState(hasWebGL);
	const unavailable = useCallback(() => setWebgl(false), []);
	const [cameraCommand, setCameraCommand] = useState<CameraCommand>({
		action: 'reset',
		sequence: 0,
	});
	const [selectedId, setSelectedId] = useState<string | null>(null);
	useEffect(() => setSelectedId(null), [sim]);
	useEffect(() => {
		if (sim && session?.motion === 'events') sim.applySession(session, layout);
	}, [session, sim, layout]);
	useEffect(() => {
		const user = sim?.actors.get(USER_ID);
		if (user) {
			user.name = t('agents.graph.you');
			sim?.publish();
		}
	}, [sim, t]);
	const roomNames = useMemo(
		() =>
			Object.fromEntries(
				roomLabels(layout).map(({ key }) => [key, t(`agents.office.rooms.${key}`)]),
			),
		[layout, t],
	);
	const fallback = (
		<div role="status" className="absolute inset-0 flex items-center justify-center px-6">
			<p className="max-w-sm rounded-2xl border bg-background/95 p-5 text-center text-sm/6 text-muted-foreground">
				{t('agents.office.noWebgl')}
			</p>
		</div>
	);
	const command = (action: CameraCommand['action']) =>
		setCameraCommand((current) => ({ action, sequence: current.sequence + 1 }));

	return (
		<div className="relative size-full overflow-hidden" style={{ background: ROOM.background }}>
			{!webgl
				? fallback
				: sim && (
						<OfficeBoundary
							key={session?.id ?? 'catalog'}
							fallback={fallback}
							onError={unavailable}
						>
							<Suspense
								fallback={
									<div
										role="status"
										className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-muted-foreground"
									>
										<LoaderCircle
											className="size-4 motion-safe:animate-spin"
											aria-hidden="true"
										/>
										{t('agents.office.loading')}
									</div>
								}
							>
								<Office3D
									layout={layout}
									sim={sim}
									selectedId={selectedId}
									setSelectedId={setSelectedId}
									roomNames={roomNames}
									offLabel={t('agents.graph.notInvitable')}
									cameraCommand={cameraCommand}
									onUnavailable={unavailable}
								/>
							</Suspense>
						</OfficeBoundary>
					)}

			{webgl && (
				<div
					role="toolbar"
					aria-label={t('agents.office.controls')}
					className={cn(FLOAT, 'absolute right-3 bottom-3 flex items-center gap-1 p-1')}
				>
					<ChromeButton
						label={t('agents.office.rotateLeft')}
						onClick={() => command('rotate-left')}
					>
						<RotateCcw className="size-4" />
					</ChromeButton>
					<ChromeButton
						label={t('agents.office.rotateRight')}
						onClick={() => command('rotate-right')}
					>
						<RotateCw className="size-4" />
					</ChromeButton>
					<ChromeButton
						label={t('agents.office.zoomOut')}
						onClick={() => command('zoom-out')}
					>
						<ZoomOut className="size-4" />
					</ChromeButton>
					<ChromeButton
						label={t('agents.office.zoomIn')}
						onClick={() => command('zoom-in')}
					>
						<ZoomIn className="size-4" />
					</ChromeButton>
					<ChromeButton
						label={t('agents.office.resetView')}
						onClick={() => command('reset')}
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
		<Button
			type="button"
			variant="ghost"
			size="icon"
			onClick={onClick}
			aria-label={label}
			title={label}
			className="size-11 rounded-full"
		>
			{children}
		</Button>
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
	const [rosterOpen, setRosterOpen] = useState(false);
	// Primitive snapshot stays equal during movement; only visible UI changes trigger a render.
	useSyncExternalStore(sim.subscribe, () => {
		const actor = selectedId ? sim.actors.get(selectedId) : undefined;
		return JSON.stringify([
			sim.phase,
			sim.playing,
			sim.speed,
			sim.log.map((entry) => entry.text),
			[...sim.actors.values()].map((entry) => [entry.id, entry.name, entry.status]),
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
				<span className="flex h-8 items-center rounded-full border bg-background/95 px-3 text-[12px] font-medium text-foreground">
					{t(session?.source === 'mock' ? 'agents.office.mock' : 'agents.office.live')}
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
							sim.phase === 'work'
								? 'ag-ping bg-emerald-600'
								: sim.phase === 'approval'
									? 'bg-amber-600'
									: 'bg-muted-foreground',
						)}
					/>
					{session?.statusLabel ?? t(`agents.office.phase.${sim.phase}`)}
				</span>
				<Popover open={rosterOpen} onOpenChange={setRosterOpen}>
					<PopoverTrigger asChild>
						<Button variant="outline" className="h-11 rounded-full px-3 text-xs">
							<Users />
							{t('agents.office.team')}
						</Button>
					</PopoverTrigger>
					<PopoverContent
						align="start"
						className="max-h-[min(60dvh,360px)] w-[min(280px,calc(100vw-32px))] overflow-y-auto rounded-2xl"
					>
						<h2 className="px-2 py-1 text-xs font-semibold text-muted-foreground">
							{t('agents.office.team')}
						</h2>
						{[...sim.actors.values()]
							.filter((actor) => actor.kind === 'agent' || actor.kind === 'leader')
							.map((actor) => (
								<button
									key={actor.id}
									type="button"
									aria-pressed={selectedId === actor.id}
									className="flex min-h-11 w-full items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
									onClick={() => {
										setSelectedId(actor.id);
										setRosterOpen(false);
									}}
								>
									<ClayAvatar id={actor.id} label={actor.name} size={28} />
									<span className="min-w-0">
										<span className="block truncate text-sm font-medium">
											{actor.name}
										</span>
										<span className="text-xs text-muted-foreground">
											{t(`agents.office.status.${actor.status}`)}
										</span>
									</span>
								</button>
							))}
					</PopoverContent>
				</Popover>
			</div>

			{/* What just happened, newest last. */}
			<section
				aria-label={t('agents.office.log')}
				className={cn(
					// Top-right, below the status chips, so it never covers the office floor.
					'absolute top-16 right-4 flex max-h-[min(36%,280px)] w-[min(260px,calc(100%-32px))] flex-col rounded-[18px] border border-border bg-background/95 p-3 shadow-sm backdrop-blur',
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
					{sim.log.length === 0 && (
						<li className="text-xs/5 text-muted-foreground">
							{t('agents.office.emptyLog')}
						</li>
					)}
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
							{entry.text}
						</li>
					))}
				</ol>
			</section>

			{selectedActor && (selected || selectedId === LEADER_ID) && (
				<section
					aria-label={selectedActor.name}
					className="ag-panel-in absolute bottom-[76px] left-3 flex max-h-[calc(100%-144px)] w-[min(280px,calc(100%-24px))] flex-col gap-3 overflow-y-auto rounded-[20px] border border-border bg-background p-4 shadow-lg md:bottom-4 md:left-4"
				>
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
							className="size-11 shrink-0"
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
								className="min-h-11 flex-1"
								onClick={() => onChat(selected.real!)}
							>
								<MessageCircle />
								{t('agents.list.chat')}
							</Button>
							<Button
								size="sm"
								variant="outline"
								className="min-h-11 flex-1"
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
