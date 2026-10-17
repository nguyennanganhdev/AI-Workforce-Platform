import { motion, useMotionValue, useTransform, type MotionStyle } from 'framer-motion';
import {
	Activity,
	ArrowRight,
	Focus,
	Mail,
	Minus,
	Plus,
	Radio,
	RotateCcw,
	RotateCw,
	UsersRound,
} from 'lucide-react';
import {
	useEffect,
	useMemo,
	useRef,
	type CSSProperties,
	type PointerEvent as ReactPointerEvent,
	type WheelEvent as ReactWheelEvent,
} from 'react';

import type { TeamDetailResponse } from '@/api';
import { AgentCharacterAvatar } from '@/components/team/AgentCharacterAvatar';
import { Button } from '@/components/ui/button';
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

interface MeetingRoomViewProps {
	team: TeamDetailResponse;
	participants: TeamActivityParticipant[];
	runtimeBySession: Record<string, TeamMemberRuntime>;
	activities: TeamActivityItem[];
	latestUserMessageId: string | null;
	phase: ReplyPhase;
	visible: boolean;
}

interface ActorPosition {
	x: number;
	y: number;
}

type ActorStyle = CSSProperties & {
	'--actor-x': string;
	'--actor-y': string;
	'--actor-delay': string;
};

const ROOM_STATUSES = new Set<TeamRuntimeStatus>(['active', 'communicating', 'waiting']);
const MIN_ZOOM = 0.62;
const MAX_ZOOM = 1.42;

const MEETING_SEATS: ActorPosition[] = [
	{ x: 39, y: 23 },
	{ x: 50, y: 28 },
	{ x: 47, y: 48 },
	{ x: 35, y: 52 },
	{ x: 29, y: 38 },
	{ x: 42, y: 37 },
];

const meetingPosition = (index: number, leader: boolean): ActorPosition =>
	leader ? { x: 31, y: 25 } : MEETING_SEATS[index % MEETING_SEATS.length];

const restPosition = (index: number): ActorPosition => ({
	x: 64 + (index % 3) * 12,
	y: 24 + (Math.floor(index / 3) % 2) * 31,
});

const actorStyle = (position: ActorPosition, index: number): ActorStyle => ({
	'--actor-x': `${position.x}cqw`,
	'--actor-y': `${position.y}cqh`,
	'--actor-delay': `${index * 70}ms`,
});

const fallbackRuntime = (participant: TeamActivityParticipant): TeamMemberRuntime => ({
	status: participant.sessionId ? 'loading' : 'idle',
	detail: '',
	activeTool: null,
	updatedAt: null,
	connected: false,
});

const clampZoom = (value: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));

export function MeetingRoomView({
	team,
	participants,
	runtimeBySession,
	activities,
	latestUserMessageId,
	phase,
	visible,
}: MeetingRoomViewProps) {
	const { t } = useTranslation();
	const animatedMessageRef = useRef<string | null>(null);
	const deliveryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const deliveryRef = useRef<HTMLDivElement>(null);
	const rotation = useMotionValue(-5);
	const zoom = useMotionValue(0.92);
	const inverseRotation = useTransform(rotation, (value) => `${-value}deg`);
	const pointerRef = useRef<{ id: number; x: number } | null>(null);
	const teamBusy =
		phase !== 'idle' ||
		participants.some((participant) => {
			const status = participant.sessionId
				? runtimeBySession[participant.sessionId]?.status
				: 'idle';
			return status === 'active' || status === 'communicating' || status === 'waiting';
		});

	useEffect(() => {
		if (
			!visible ||
			!teamBusy ||
			!latestUserMessageId ||
			animatedMessageRef.current === latestUserMessageId
		) {
			return;
		}
		animatedMessageRef.current = latestUserMessageId;
		deliveryRef.current?.classList.add('is-delivering');
		if (deliveryTimerRef.current) clearTimeout(deliveryTimerRef.current);
		deliveryTimerRef.current = setTimeout(() => {
			deliveryRef.current?.classList.remove('is-delivering');
		}, 4_800);
		return () => {
			if (deliveryTimerRef.current) clearTimeout(deliveryTimerRef.current);
		};
	}, [latestUserMessageId, teamBusy, visible]);

	const actors = useMemo(
		() =>
			participants.map((participant, index) => {
				const runtime = participant.sessionId
					? (runtimeBySession[participant.sessionId] ?? fallbackRuntime(participant))
					: fallbackRuntime(participant);
				const inRoom =
					participant.role === 'leader' ? teamBusy : ROOM_STATUSES.has(runtime.status);
				return {
					participant,
					runtime,
					inRoom,
					position: inRoom
						? meetingPosition(index, participant.role === 'leader')
						: restPosition(index),
				};
			}),
		[participants, runtimeBySession, teamBusy],
	);
	const inRoomCount = actors.filter((actor) => actor.inRoom).length;
	const activeActorId = actors.find(
		(actor) => actor.runtime.status === 'active' || actor.runtime.status === 'communicating',
	)?.participant.agentId;
	const courierDispatching = actors.some(
		(actor) => actor.inRoom && actor.participant.role === 'member',
	);

	const startRotate = (event: ReactPointerEvent<HTMLElement>) => {
		pointerRef.current = { id: event.pointerId, x: event.clientX };
		event.currentTarget.setPointerCapture(event.pointerId);
		event.currentTarget.dataset.dragging = 'true';
	};
	const rotate = (event: ReactPointerEvent<HTMLElement>) => {
		if (pointerRef.current?.id !== event.pointerId) return;
		rotation.set(rotation.get() + (event.clientX - pointerRef.current.x) * 0.48);
		pointerRef.current.x = event.clientX;
	};
	const stopRotate = (event: ReactPointerEvent<HTMLElement>) => {
		if (pointerRef.current?.id !== event.pointerId) return;
		pointerRef.current = null;
		delete event.currentTarget.dataset.dragging;
	};
	const handleWheel = (event: ReactWheelEvent<HTMLElement>) => {
		event.preventDefault();
		zoom.set(clampZoom(zoom.get() - event.deltaY * 0.001));
	};
	const resetCamera = () => {
		rotation.set(-5);
		zoom.set(0.92);
	};
	const cameraStyle = {
		rotateZ: rotation,
		scale: zoom,
		'--office-inverse-rotation': inverseRotation,
	} as MotionStyle;

	return (
		<div className="team-office-view">
			<header className="team-office-statusbar">
				<div className="team-office-statusbar__title">
					<strong>{team.team.data.name || t('meetingRoom.title')}</strong>
					<span>{t('meetingRoom.description')}</span>
				</div>
				<div className="team-office-statusbar__metrics">
					<span><Activity />{t('meetingRoom.sessionActivity')}</span>
					<span className={cn(teamBusy && 'is-live')}><Radio />{teamBusy ? t('meetingRoom.live') : t('meetingRoom.quiet')}</span>
					<span><UsersRound />{inRoomCount}/{actors.length}</span>
				</div>
			</header>

			<div className="team-office-layout">
				<section
					className="meeting-room-stage"
					aria-label={t('meetingRoom.sceneLabel')}
					tabIndex={0}
					onPointerDown={startRotate}
					onPointerMove={rotate}
					onPointerUp={stopRotate}
					onPointerCancel={stopRotate}
					onWheel={handleWheel}
					onKeyDown={(event) => {
						if (event.key === 'ArrowLeft') rotation.set(rotation.get() - 15);
						if (event.key === 'ArrowRight') rotation.set(rotation.get() + 15);
						if (event.key === '+' || event.key === '=') zoom.set(clampZoom(zoom.get() + 0.1));
						if (event.key === '-') zoom.set(clampZoom(zoom.get() - 0.1));
					}}
				>
					<div className="meeting-room-camera-tilt">
						<motion.div className="meeting-room-world" style={cameraStyle}>
							<div className="meeting-room-wall meeting-room-wall--back" />
							<div className="meeting-room-wall meeting-room-wall--left" />
							<div className="meeting-room-zone meeting-room-zone--conference">
								<span>{t('meetingRoom.meetingZone')}</span>
							</div>
							<div className="meeting-room-zone meeting-room-zone--work">
								<span>{t('meetingRoom.workZone')}</span>
							</div>
							<div className="meeting-room-zone meeting-room-zone--lounge">
								<span>{t('meetingRoom.loungeZone')}</span>
							</div>

							<div className="office-reception"><span /></div>
							<div className="office-mailbox">
								<Mail />
								<span>{t('meetingRoom.mailZone')}</span>
								<span className="meeting-room-envelope" />
							</div>
							<div className="meeting-room-table"><span /></div>
							<div className="office-desk office-desk--one"><span /></div>
							<div className="office-desk office-desk--two"><span /></div>
							<div className="office-sofa" />
							<div className="office-divider office-divider--one" />
							<div className="office-divider office-divider--two" />
							<div className="office-plant office-plant--one"><span /></div>
							<div className="office-plant office-plant--two"><span /></div>
							<div className="office-plant office-plant--three"><span /></div>

							{actors.map(({ participant, runtime, position, inRoom }, index) => (
								<div
									key={participant.agentId}
									className={cn('meeting-room-actor', inRoom ? 'is-in-room' : 'is-resting')}
									style={actorStyle(position, index)}
									data-status={runtime.status}
								>
									<div className="meeting-room-actor__billboard">
										{participant.agentId === activeActorId && runtime.detail ? (
											<div className="meeting-room-speech">{runtime.detail}</div>
										) : null}
										<AgentCharacterAvatar
											role={participant.role}
											active={runtime.status === 'active' || runtime.status === 'communicating'}
							className="size-10"
										/>
										<div className="meeting-room-actor__label">
											<strong>{participant.name}</strong>
											<small>{t(`meetingRoom.status.${runtime.status}`)}</small>
										</div>
									</div>
								</div>
							))}

							<div
								ref={deliveryRef}
								className={cn('meeting-room-courier', courierDispatching && 'is-dispatching')}
							>
								<div className="meeting-room-actor__billboard">
									<AgentCharacterAvatar role="courier" className="size-10" />
									<div className="meeting-room-actor__label">
										<strong>{t('meetingRoom.courier')}</strong>
										<small>{courierDispatching ? t('meetingRoom.courierDispatching') : t('meetingRoom.courierRest')}</small>
									</div>
								</div>
							</div>
						</motion.div>
					</div>

					<div className="meeting-room-camera-hint">{t('meetingRoom.cameraHint')}</div>
					<div
						className="meeting-room-camera-controls"
						onPointerDown={(event) => event.stopPropagation()}
					>
						<Button variant="outline" size="icon-sm" onClick={resetCamera} aria-label={t('meetingRoom.resetCamera')} title={t('meetingRoom.resetCamera')}><Focus /></Button>
						<Button variant="outline" size="icon-sm" onClick={() => rotation.set(rotation.get() - 30)} aria-label={t('meetingRoom.rotateLeft')} title={t('meetingRoom.rotateLeft')}><RotateCcw /></Button>
						<Button variant="outline" size="icon-sm" onClick={() => rotation.set(rotation.get() + 30)} aria-label={t('meetingRoom.rotateRight')} title={t('meetingRoom.rotateRight')}><RotateCw /></Button>
						<span />
						<Button variant="outline" size="icon-sm" onClick={() => zoom.set(clampZoom(zoom.get() - 0.1))} aria-label={t('meetingRoom.zoomOut')} title={t('meetingRoom.zoomOut')}><Minus /></Button>
						<Button variant="outline" size="icon-sm" onClick={() => zoom.set(clampZoom(zoom.get() + 0.1))} aria-label={t('meetingRoom.zoomIn')} title={t('meetingRoom.zoomIn')}><Plus /></Button>
					</div>
				</section>

				<aside className="team-office-activity">
					<h3>{t('meetingRoom.activity')}</h3>
					{activities.length === 0 ? (
						<p className="team-office-activity__empty">{t('meetingRoom.noActivity')}</p>
					) : (
						<ol>
							{activities.slice(0, 10).map((activity) => (
								<li key={activity.id} data-state={activity.state}>
									<div>
										<strong>{activity.sourceName}</strong>
										{activity.targetName ? <><ArrowRight /><strong>{activity.targetName}</strong></> : null}
									</div>
									<p>{activity.detail || activity.toolName}</p>
								</li>
							))}
						</ol>
					)}
				</aside>
			</div>
		</div>
	);
}
