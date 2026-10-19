import {
	Activity,
	Maximize2,
	Radio,
	RotateCcw,
	RotateCw,
	UsersRound,
	X,
	ZoomIn,
	ZoomOut,
} from 'lucide-react';
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';

import type { TeamDetailResponse } from '@/api';
import type {
	OfficeAgent,
	SessionOfficeSnapshot,
} from '@/components/team/office/model';
import { ROOM } from '@/components/team/office/office-palette';
import {
	buildLayout,
	LEADER_ID,
	OfficeSim,
	populate,
} from '@/components/team/office/office-sim';
import type {
	OfficeCameraAction,
	OfficeCameraCommand,
} from '@/components/team/office/Office3D';
import { TeamAgentAvatar } from '@/components/team/TeamAgentAvatar';
import { Button } from '@/components/ui/button';
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from '@/components/ui/popover';
import type { ReplyPhase } from '@/hooks/useMessages';
import type {
	TeamActivityItem,
	TeamActivityParticipant,
	TeamMemberRuntime,
	TeamRuntimeStatus,
} from '@/hooks/useTeamActivity';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

import './MeetingRoomView.css';
import './office/agent-office.css';

const Office3D = lazy(() => import('./office/Office3D'));

interface MeetingRoomViewProps {
	team: TeamDetailResponse;
	participants: TeamActivityParticipant[];
	runtimeBySession: Record<string, TeamMemberRuntime>;
	activities: TeamActivityItem[];
	latestUserMessageId: string | null;
	latestUserMessageAt: string | null;
	phase: ReplyPhase;
	visible: boolean;
	simulationCache: OfficeSimulationCache;
}

export type OfficeSimulationCache = Map<
	string,
	{ rosterKey: string; sim: OfficeSim }
>;

const ACTIVE_STATUSES = new Set<TeamRuntimeStatus>([
	'active',
	'communicating',
	'waiting',
]);

const WEBGL_AVAILABLE = (() => {
	if (typeof document === 'undefined') return false;
	try {
		const canvas = document.createElement('canvas');
		return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'));
	} catch {
		return false;
	}
})();

const fallbackRuntime = (participant: TeamActivityParticipant): TeamMemberRuntime => ({
	status: participant.sessionId ? 'loading' : 'idle',
	detail: '',
	activeTool: null,
	updatedAt: null,
	connected: false,
});

const runtimeFor = (
	participant: TeamActivityParticipant,
	runtimeBySession: Record<string, TeamMemberRuntime>,
) =>
	participant.sessionId
		? (runtimeBySession[participant.sessionId] ?? fallbackRuntime(participant))
		: fallbackRuntime(participant);

const actorStatus = (
	participant: TeamActivityParticipant,
	runtime: TeamMemberRuntime,
): SessionOfficeSnapshot['participants'][number]['status'] => {
	if (!participant.sessionId || runtime.status === 'error') return 'off';
	return ACTIVE_STATUSES.has(runtime.status) ? 'working' : 'idle';
};

const shortDetail = (value: string) =>
	value.length > 128 ? `${value.slice(0, 125).trimEnd()}...` : value;

export function MeetingRoomView({
	team,
	participants,
	runtimeBySession,
	activities,
	latestUserMessageId,
	latestUserMessageAt,
	phase,
	visible,
	simulationCache,
}: MeetingRoomViewProps) {
	const { t } = useTranslation();
	const [activeSimulation, setActiveSimulation] = useState<{
		key: string;
		rosterKey: string;
		sim: OfficeSim;
	} | null>(null);
	const [resetKey, setResetKey] = useState(0);
	const [cameraCommand, setCameraCommand] = useState<OfficeCameraCommand | null>(null);
	const [selectedId, setSelectedId] = useState<string | null>(null);

	const leader = participants.find((participant) => participant.role === 'leader');
	const leaderName = team.leader_agent?.data.name;
	const members = useMemo(
		() => participants.filter((participant) => participant.role === 'member'),
		[participants],
	);
	const officeAgents = useMemo<OfficeAgent[]>(
		() =>
			members.map((participant) => ({
				id: participant.agentId,
				name: participant.name,
				role: participant.role,
				invitable: Boolean(participant.sessionId),
			})),
		[members],
	);
	const layout = useMemo(() => buildLayout(officeAgents), [officeAgents]);
	const simulationKey = team.team.session_id;
	const rosterKey = officeAgents
		.map((agent) => `${agent.id}:${agent.name}:${agent.invitable}`)
		.join('|');

	useEffect(() => {
		let cached = simulationCache.get(simulationKey);
		if (!cached || cached.rosterKey !== rosterKey) {
			cached?.sim.abort();
			const next = new OfficeSim();
			populate(next, layout, officeAgents);
			cached = { rosterKey, sim: next };
			simulationCache.set(simulationKey, cached);
		}
		setActiveSimulation({ key: simulationKey, rosterKey, sim: cached.sim });
		return () => cached.sim.setPlaying(false);
	}, [layout, officeAgents, rosterKey, simulationCache, simulationKey]);

	const sim =
		activeSimulation?.key === simulationKey && activeSimulation.rosterKey === rosterKey
			? activeSimulation.sim
			: null;

	const snapshot = useMemo<SessionOfficeSnapshot>(() => {
		const leaderRuntime = leader ? runtimeFor(leader, runtimeBySession) : null;
		const memberRows = members.map((participant) => {
			const runtime = runtimeFor(participant, runtimeBySession);
			return {
				id: participant.agentId,
				name: participant.name,
				role: participant.role,
				status: actorStatus(participant, runtime),
				message:
					runtime.detail && ACTIVE_STATUSES.has(runtime.status)
						? shortDetail(runtime.detail)
						: undefined,
			};
		});
		const participantIdByName = new Map(
			participants.map((participant) => [participant.name, participant.agentId]),
		);
		const chronological = [...activities].reverse();
		const currentActivities = latestUserMessageAt
			? chronological.filter((activity) => activity.createdAt >= latestUserMessageAt)
			: chronological;
		const leaderCalls = currentActivities.filter(
			(activity) =>
				activity.type === 'communication' &&
				activity.state !== 'error' &&
				activity.sourceName === leader?.name,
		);
		const exchanges = currentActivities.flatMap((activity) => {
			if (activity.type !== 'communication' || !activity.targetName) return [];
			const from = participantIdByName.get(activity.sourceName);
			const to = participantIdByName.get(activity.targetName);
			if (!from || !to || from === leader?.agentId || to === leader?.agentId) return [];
			return [{ from, to }];
		});
		const activeMembers = members
			.filter((participant) =>
				ACTIVE_STATUSES.has(runtimeFor(participant, runtimeBySession).status),
			)
			.map((participant) => participant.agentId);
		const calledByLeader = leaderCalls.flatMap((activity) => {
			if (!activity.targetName) return [];
			const targetId = participantIdByName.get(activity.targetName);
			return targetId && targetId !== leader?.agentId ? [targetId] : [];
		});
		const called = [...new Set([...calledByLeader, ...activeMembers])];
		const waitingForUser =
			leaderRuntime?.status === 'waiting' &&
			leaderCalls.at(-1)?.kind === 'requires_user_input';
		const working =
			phase !== 'idle' ||
			participants.some((participant) =>
				ACTIVE_STATUSES.has(runtimeFor(participant, runtimeBySession).status),
			);
		const officePhase: SessionOfficeSnapshot['phase'] = waitingForUser
			? 'approval'
			: working
				? 'work'
				: activities.length
					? 'done'
					: 'idle';

		return {
			id: team.team.id,
			source: 'live',
			statusLabel: working ? t('meetingRoom.live') : t('meetingRoom.ready'),
			motion: 'events',
			participants: [
				{
					id: LEADER_ID,
					name: leader?.name ?? leaderName ?? 'Workforce Leader',
					role: 'leader',
					status:
						leader && leaderRuntime
							? actorStatus(leader, leaderRuntime)
							: phase === 'idle'
								? 'idle'
								: 'working',
					message:
						leaderRuntime?.detail && ACTIVE_STATUSES.has(leaderRuntime.status)
							? shortDetail(leaderRuntime.detail)
							: undefined,
				},
				...memberRows,
			],
			phase: officePhase,
			turn: latestUserMessageId ?? 'initial',
			called,
			exchanges,
			hostId: LEADER_ID,
			activity: chronological.slice(-6).map((activity) => ({
				id: activity.id,
				text: activity.targetName
					? `${activity.sourceName} → ${activity.targetName}: ${activity.detail || activity.toolName}`
					: `${activity.sourceName}: ${activity.detail || activity.toolName}`,
			})),
		};
	}, [
		activities,
		latestUserMessageId,
		latestUserMessageAt,
		leader,
		members,
		participants,
		phase,
		runtimeBySession,
		t,
		leaderName,
		team.team.id,
	]);

	useEffect(() => {
		if (!sim) return;
		sim.setPlaying(visible);
		if (visible) sim.applySession(snapshot, layout);
	}, [layout, sim, snapshot, visible]);

	const runCameraAction = (action: OfficeCameraAction) => {
		setCameraCommand((current) => ({ id: (current?.id ?? 0) + 1, action }));
	};

	const teamBusy = snapshot.phase === 'work' || snapshot.phase === 'approval';
	const selectedParticipant =
		selectedId === LEADER_ID
			? leader
			: participants.find((participant) => participant.agentId === selectedId);
	const selectedRuntime = selectedParticipant
		? runtimeFor(selectedParticipant, runtimeBySession)
		: null;
	const roomNames = {
		meeting: t('meetingRoom.meetingZone'),
		approval: t('meetingRoom.approvalZone'),
		reception: t('meetingRoom.receptionZone'),
		workspace: t('meetingRoom.workZone'),
	};

	return (
		<section
			className="team-office-view"
			style={{ background: ROOM.background }}
			aria-label={t('meetingRoom.sceneLabel')}
		>
			{WEBGL_AVAILABLE && sim ? (
				<Suspense
					fallback={<div className="team-office-loading">{t('meetingRoom.loading')}</div>}
				>
					<Office3D
						key={simulationKey}
						layout={layout}
						sim={sim}
						active={visible}
						selectedId={selectedId}
						setSelectedId={setSelectedId}
						roomNames={roomNames}
						offLabel={t('meetingRoom.status.error')}
						resetKey={resetKey}
						cameraCommand={cameraCommand}
					/>
				</Suspense>
			) : (
				<div className="team-office-loading">{t('meetingRoom.noWebgl')}</div>
			)}

			<div className="team-office-toolbar">
				<span className="team-office-pill">
					<Activity />
					{t('meetingRoom.sessionActivity')}
				</span>
				<span className={cn('team-office-pill', teamBusy && 'is-live')}>
					<Radio />
					{snapshot.statusLabel}
				</span>
				<Popover>
					<PopoverTrigger asChild>
						<Button variant="outline" className="team-office-pill team-office-pill--button">
							<UsersRound />
							{t('meetingRoom.teamAgents')}
						</Button>
					</PopoverTrigger>
					<PopoverContent align="start" className="team-office-roster">
						<h3>{t('meetingRoom.teamAgents')}</h3>
						<ul>
							{participants.map((participant) => {
								const runtime = runtimeFor(participant, runtimeBySession);
								return (
									<li key={participant.agentId}>
										<TeamAgentAvatar
											role={participant.role}
											name={participant.name}
											status={runtime.status}
											size="sm"
										/>
										<div>
											<strong>{participant.name}</strong>
											<span>{t(`meetingRoom.status.${runtime.status}`)}</span>
										</div>
									</li>
								);
							})}
						</ul>
					</PopoverContent>
				</Popover>
			</div>

			{selectedParticipant && selectedRuntime ? (
				<div className="team-office-agent-card">
					<TeamAgentAvatar
						role={selectedParticipant.role}
						status={selectedRuntime.status}
						size="lg"
					/>
					<div>
						<strong>{selectedParticipant.name}</strong>
						<span>{t(`meetingRoom.status.${selectedRuntime.status}`)}</span>
					</div>
					<Button
						variant="ghost"
						size="icon-sm"
						onClick={() => setSelectedId(null)}
						aria-label={t('meetingRoom.close')}
					>
						<X />
					</Button>
				</div>
			) : null}

			<div
				className="meeting-room-camera-controls"
				role="toolbar"
				aria-label={t('meetingRoom.cameraControls')}
			>
				<Button variant="ghost" size="icon" onClick={() => runCameraAction('rotate-left')} aria-label={t('meetingRoom.rotateLeft')} title={t('meetingRoom.rotateLeft')}><RotateCcw /></Button>
				<Button variant="ghost" size="icon" onClick={() => runCameraAction('rotate-right')} aria-label={t('meetingRoom.rotateRight')} title={t('meetingRoom.rotateRight')}><RotateCw /></Button>
				<Button variant="ghost" size="icon" onClick={() => runCameraAction('zoom-out')} aria-label={t('meetingRoom.zoomOut')} title={t('meetingRoom.zoomOut')}><ZoomOut /></Button>
				<Button variant="ghost" size="icon" onClick={() => runCameraAction('zoom-in')} aria-label={t('meetingRoom.zoomIn')} title={t('meetingRoom.zoomIn')}><ZoomIn /></Button>
				<Button variant="ghost" size="icon" onClick={() => setResetKey((key) => key + 1)} aria-label={t('meetingRoom.resetCamera')} title={t('meetingRoom.resetCamera')}><Maximize2 /></Button>
			</div>
		</section>
	);
}
