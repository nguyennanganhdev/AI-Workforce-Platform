import type { Msg, ToolCallBlock, ToolResultBlock } from '@agentscope-ai/agentscope/message';
import { useEffect, useMemo, useState } from 'react';

import { sessionApi } from '@/api';

export type TeamRuntimeStatus =
	| 'loading'
	| 'idle'
	| 'active'
	| 'communicating'
	| 'waiting'
	| 'completed'
	| 'error';

export interface TeamActivityParticipant {
	agentId: string;
	sessionId: string | null;
	name: string;
	role: 'leader' | 'member';
}

export interface TeamMemberRuntime {
	status: TeamRuntimeStatus;
	detail: string;
	activeTool: string | null;
	updatedAt: string | null;
	connected: boolean;
}

export interface TeamActivityItem {
	id: string;
	sessionId: string;
	sourceName: string;
	targetName: string | null;
	type: 'communication' | 'tool';
	kind: string | null;
	toolName: string;
	detail: string | null;
	state: 'running' | 'success' | 'error';
	createdAt: string;
}

interface ParsedTeamSay {
	kind: string;
	targetName: string;
	content: string | null;
}

const MAX_ACTIVITIES = 80;
const POLL_INTERVAL_MS = 1_500;

const initialRuntime = (participant: TeamActivityParticipant): TeamMemberRuntime => ({
	status: participant.sessionId ? 'loading' : 'idle',
	detail: participant.sessionId ? 'Đang tải trạng thái' : 'Chưa có phiên làm việc',
	activeTool: null,
	updatedAt: null,
	connected: false,
});

const isTeamSay = (toolName: string) => toolName.toLowerCase().endsWith('teamsay');

const displayHandle = (value: string): string => value.split('@')[0]?.trim() || value;

const resolveTargetName = (
	rawTarget: unknown,
	kind: string,
	participants: TeamActivityParticipant[],
): string => {
	if (typeof rawTarget !== 'string' || !rawTarget.trim()) {
		return kind === 'requires_user_input' ? 'Khách hàng' : 'Cả nhóm';
	}
	const target = rawTarget.trim();
	if (
		kind === 'requires_user_input' &&
		['null', 'none'].includes(target.toLocaleLowerCase())
	) {
		return 'Khách hàng';
	}
	const resolved = participants.find(
		(participant) =>
			participant.name === target ||
			target.startsWith(`${participant.name}@`) ||
			target.includes(participant.agentId),
	);
	return resolved?.name ?? displayHandle(target);
};

const parseTeamSay = (
	input: string,
	participants: TeamActivityParticipant[],
	effectiveKind?: unknown,
	effectiveTarget?: unknown,
): ParsedTeamSay | null => {
	try {
		const value = JSON.parse(input) as Record<string, unknown>;
		const kind = typeof effectiveKind === 'string' ? effectiveKind : typeof value.kind === 'string' ? value.kind : 'result';
		return {
			kind,
			targetName: resolveTargetName(effectiveTarget ?? value.to, kind, participants),
			content: typeof value.content === 'string' ? value.content.trim() || null : null,
		};
	} catch {
		return null;
	}
};

const activityState = (
	call: ToolCallBlock,
	result: ToolResultBlock | undefined,
): TeamActivityItem['state'] => {
	if (result?.state === 'error' || result?.state === 'denied' || result?.state === 'interrupted') {
		return 'error';
	}
	if (result?.state === 'running') return 'running';
	if (!result && call.state !== 'finished') return 'running';
	return 'success';
};

const buildHistoryActivities = (
	participant: TeamActivityParticipant,
	messages: Msg[],
	participants: TeamActivityParticipant[],
): TeamActivityItem[] => {
	const activities: TeamActivityItem[] = [];
	for (const message of messages) {
		const authoredParticipant = participants.find(
			(candidate) =>
				message.name === candidate.name || message.name === candidate.agentId,
		);
		const sourceName = authoredParticipant?.name ?? displayHandle(message.name || participant.name);
		const sourceSessionId = authoredParticipant?.sessionId ?? participant.sessionId;
		const results = new Map<string, ToolResultBlock>();
		for (const block of message.content) {
			if (block.type === 'tool_result') results.set(block.id, block);
		}
		for (const block of message.content) {
			if (block.type !== 'tool_call') continue;
			const teamCall = isTeamSay(block.name);
			const result = results.get(block.id);
			const teamSay = teamCall ? parseTeamSay(
				block.input,
				participants,
				result?.metadata?.kind,
				result?.metadata?.effective_to,
			) : null;
			activities.push({
				// Tool-call ids survive transcript projection, so they are the
				// stable identity across Leader and worker history copies.
				id: `tool:${block.id}`,
				sessionId: sourceSessionId as string,
				sourceName,
				targetName: teamSay?.targetName ?? (teamCall ? 'Cả nhóm' : null),
				type: teamCall ? 'communication' : 'tool',
				kind: teamSay?.kind ?? null,
				toolName: block.name,
				detail: teamSay?.content ?? null,
				state: activityState(block, result),
				createdAt: block.created_at || message.created_at,
			});
		}
	}
	return activities;
};

const lastToolCall = (messages: Msg[]): ToolCallBlock | null => {
	for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
		const blocks = messages[messageIndex]?.content ?? [];
		for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex -= 1) {
			const block = blocks[blockIndex];
			if (block?.type === 'tool_call') return block;
		}
	}
	return null;
};

const toolResult = (messages: Msg[], call: ToolCallBlock | null): ToolResultBlock | null => {
	if (!call) return null;
	for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
		const result = messages[messageIndex]?.content.find(
			(block): block is ToolResultBlock => block.type === 'tool_result' && block.id === call.id,
		);
		if (result) return result;
	}
	return null;
};

const runtimeFromHistory = (
	messages: Msg[],
	isRunning: boolean,
	participants: TeamActivityParticipant[],
): TeamMemberRuntime => {
	const call = lastToolCall(messages);
	const result = toolResult(messages, call);
	const tail = messages[messages.length - 1];
	const updatedAt = tail?.finished_at ?? tail?.created_at ?? null;
	if (isRunning) {
		return {
			status: call && isTeamSay(call.name) ? 'communicating' : 'active',
			detail: call ? `Đang gọi ${call.name}` : 'Đang xử lý yêu cầu',
			activeTool: call?.name ?? null,
			updatedAt,
			connected: true,
		};
	}
	if (call?.state === 'asking' || call?.state === 'submitted') {
		return {
			status: 'waiting',
			detail: 'Đang chờ xác nhận',
			activeTool: call.name,
			updatedAt,
			connected: true,
		};
	}
	if (call && isTeamSay(call.name) && activityState(call, result ?? undefined) !== 'error') {
		const teamSay = parseTeamSay(
			call.input,
			participants,
			result?.metadata?.kind,
			result?.metadata?.effective_to,
		);
		if (teamSay?.kind === 'requires_user_input') {
			return {
				status: 'waiting',
				detail: 'Đang chờ khách hàng trả lời',
				activeTool: null,
				updatedAt,
				connected: true,
			};
		}
		if (teamSay?.kind === 'question') {
			return {
				status: 'waiting',
				detail: `Đang chờ ${teamSay.targetName} trả lời`,
				activeTool: null,
				updatedAt,
				connected: true,
			};
		}
	}
	if (tail?.finished_reason === 'error') {
		return {
			status: 'error',
			detail: tail.error?.message ?? 'Lượt xử lý gặp lỗi',
			activeTool: null,
			updatedAt,
			connected: true,
		};
	}
	return {
		status: messages.length > 0 ? 'completed' : 'idle',
		detail: messages.length > 0 ? 'Đã hoàn thành lượt xử lý' : 'Chưa hoạt động',
		activeTool: null,
		updatedAt,
		connected: true,
	};
};

const mergeActivities = (
	current: TeamActivityItem[],
	incoming: TeamActivityItem[],
): TeamActivityItem[] => {
	const byId = new Map(current.map((item) => [item.id, item]));
	for (const item of incoming) byId.set(item.id, item);
	return [...byId.values()]
		.sort((left, right) => right.createdAt.localeCompare(left.createdAt))
		.slice(0, MAX_ACTIVITIES);
};

/** Poll team histories so observing a team never consumes one SSE connection per agent. */
export function useTeamActivity(
	participants: TeamActivityParticipant[],
	enabled = true,
) {
	const participantKey = useMemo(
		() =>
			participants
				.map(
					(participant) =>
						`${participant.agentId}:${participant.sessionId ?? ''}:${participant.name}:${participant.role}`,
				)
				.join('|'),
		[participants],
	);
	const [runtimeBySession, setRuntimeBySession] = useState<Record<string, TeamMemberRuntime>>(
		{},
	);
	const [activities, setActivities] = useState<TeamActivityItem[]>([]);

	useEffect(() => {
		const nextRuntime: Record<string, TeamMemberRuntime> = {};
		for (const participant of participants) {
			if (participant.sessionId) nextRuntime[participant.sessionId] = initialRuntime(participant);
		}
		setRuntimeBySession(nextRuntime);
		setActivities([]);
	}, [participantKey, participants]);

	useEffect(() => {
		if (!enabled) return;
		const snapshot = participants;

		const controller = new AbortController();
		let pollTimer: ReturnType<typeof setTimeout> | null = null;

		const refresh = async () => {
			await Promise.all(
				snapshot.map(async (participant) => {
					if (!participant.sessionId) return;
					try {
						const history = await sessionApi.messages(
							participant.sessionId,
							participant.agentId,
							{ limit: 60 },
							{ signal: controller.signal, silent: true },
						);
						if (controller.signal.aborted) return;
						setActivities((current) =>
							mergeActivities(
								current,
								buildHistoryActivities(participant, history.messages, snapshot),
							),
						);
						const ownMessages = history.messages.filter(
							(message) =>
								message.role !== 'assistant' ||
								!message.name ||
								message.name === participant.name ||
								message.name === participant.agentId,
						);
						setRuntimeBySession((current) => ({
							...current,
							[participant.sessionId as string]: runtimeFromHistory(
								ownMessages,
								history.is_running,
								snapshot,
							),
						}));
					} catch (error) {
						if (controller.signal.aborted || (error as Error).name === 'AbortError') return;
						setRuntimeBySession((current) => ({
							...current,
							[participant.sessionId as string]: {
								...initialRuntime(participant),
								status: 'error',
								detail: 'Không tải được lịch sử hoạt động',
							},
						}));
					}
				}),
			);
		};

		const poll = async () => {
			await refresh();
			if (!controller.signal.aborted) {
				pollTimer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
			}
		};
		void poll();

		return () => {
			controller.abort();
			if (pollTimer) clearTimeout(pollTimer);
		};
	}, [enabled, participantKey, participants]);

	return { runtimeBySession, activities };
}
