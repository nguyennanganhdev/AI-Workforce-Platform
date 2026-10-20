import type { Msg, ToolCallBlock, ToolResultBlock } from '@agentscope-ai/agentscope/message';
import { useEffect, useMemo, useState } from 'react';

import { sessionApi } from '@/api';
import { getResultText } from '@/components/chat/tool-renderers/_shared';
import { isInternalId, withoutInternalIds } from '@/lib/readable';
import { summarizeToolArgs, type TeamActivityItem } from '@/lib/teamThreads';

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

export type { TeamActivityItem };

interface ParsedTeamSay {
	kind: string | null;
	targetName: string;
	content: string | null;
	handoffId: string | null;
	threadId: string | null;
	inReplyTo: string | null;
}

interface InviteAssignment {
	target: string;
	prompt: string | null;
}

// Threads nest tool calls, so keep enough history to reach their requests.
const MAX_ACTIVITIES = 120;
const POLL_INTERVAL_MS = 1_500;

const initialRuntime = (participant: TeamActivityParticipant): TeamMemberRuntime => ({
	status: participant.sessionId ? 'loading' : 'idle',
	detail: participant.sessionId ? 'Đang tải trạng thái' : 'Chưa có phiên làm việc',
	activeTool: null,
	updatedAt: null,
	connected: false,
});

const isTeamSay = (toolName: string) => toolName.toLowerCase().endsWith('teamsay');
const isAgentInvite = (toolName: string) => toolName.toLowerCase().endsWith('agentinvite');

const metaString = (metadata: Record<string, unknown> | undefined, key: string): string | null => {
	const value = metadata?.[key];
	return typeof value === 'string' && value.trim() ? value : null;
};

const displayHandle = (value: string): string => {
	const handle = value.split('@')[0]?.trim() || value;
	return isInternalId(handle) ? 'Thành viên nhóm' : handle;
};

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

/**
 * Read a TeamSay call. The tool result's metadata (runtime-resolved kind,
 * recipient and thread links) wins over the model's raw input; older
 * sessions without that metadata fall back to the input.
 */
const parseTeamSay = (
	input: string,
	participants: TeamActivityParticipant[],
	metadata?: Record<string, unknown>,
): ParsedTeamSay | null => {
	try {
		const value = JSON.parse(input) as Record<string, unknown>;
		const kind = metaString(metadata, 'kind') ?? (typeof value.kind === 'string' ? value.kind : null);
		const hasResolvedTarget = metadata !== undefined && 'to' in metadata;
		return {
			kind,
			targetName: resolveTargetName(hasResolvedTarget ? metadata.to : value.to, kind ?? '', participants),
			content: typeof value.content === 'string' ? value.content.trim() || null : null,
			handoffId: metaString(metadata, 'handoff_id'),
			threadId: metaString(metadata, 'thread_id') ?? (typeof value.thread_id === 'string' ? value.thread_id : null),
			inReplyTo:
				metaString(metadata, 'in_reply_to') ?? (typeof value.in_reply_to === 'string' ? value.in_reply_to : null),
		};
	} catch {
		return null;
	}
};

/** AgentInvite may brief several agents in one call: `target` plus `additional_assignments`. */
const parseAgentInvite = (input: string): InviteAssignment[] => {
	try {
		const value = JSON.parse(input) as Record<string, unknown>;
		const rows: unknown[] = [
			{ target: value.target, prompt: value.prompt },
			...(Array.isArray(value.additional_assignments) ? value.additional_assignments : []),
		];
		return rows.flatMap((row) => {
			if (!row || typeof row !== 'object') return [];
			const { target, prompt } = row as Record<string, unknown>;
			if (typeof target !== 'string' || !target.trim()) return [];
			return [{ target: target.trim(), prompt: typeof prompt === 'string' ? prompt.trim() || null : null }];
		});
	} catch {
		return [];
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
			const result = results.get(block.id);
			const state = activityState(block, result);
			const createdAt = block.created_at || message.created_at;
			const base = {
				sessionId: sourceSessionId as string,
				sourceName,
				toolName: block.name,
				state,
				createdAt,
				handoffId: null,
				threadId: null,
				inReplyTo: null,
				argsSummary: null,
			};
			if (isAgentInvite(block.name)) {
				// Inviting is how the Leader assigns work: one "Giao việc"
				// message per briefed agent, so each starts its own thread.
				const failed = result?.metadata?.failed_targets;
				parseAgentInvite(block.input).forEach((assignment, index) => {
					const assignmentFailed =
						state === 'error' && (!Array.isArray(failed) || failed.includes(assignment.target));
					activities.push({
						...base,
						// Tool-call ids survive transcript projection, so they are the
						// stable identity across Leader and worker history copies.
						id: index === 0 ? `tool:${block.id}` : `tool:${block.id}:${index}`,
						targetName: resolveTargetName(assignment.target, 'assign', participants),
						type: 'communication',
						kind: 'assign',
						detail: assignmentFailed
							? withoutInternalIds(getResultText(result)) || assignment.prompt
							: assignment.prompt,
						state: assignmentFailed ? 'error' : state === 'error' ? 'success' : state,
					});
				});
				continue;
			}
			const teamCall = isTeamSay(block.name);
			const teamSay = teamCall ? parseTeamSay(block.input, participants, result?.metadata) : null;
			activities.push({
				...base,
				id: `tool:${block.id}`,
				targetName: teamSay?.targetName ?? (teamCall ? 'Cả nhóm' : null),
				type: teamCall ? 'communication' : 'tool',
				kind: teamSay?.kind ?? null,
				detail: teamCall && result?.state === 'error'
					? withoutInternalIds(getResultText(result)) || teamSay?.content || null
					: teamSay?.content ?? null,
				handoffId: teamSay?.handoffId ?? null,
				threadId: teamSay?.threadId ?? null,
				inReplyTo: teamSay?.inReplyTo ?? null,
				argsSummary: teamCall ? null : summarizeToolArgs(block.input),
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
		const teamSay = parseTeamSay(call.input, participants, result?.metadata);
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
	// An idle poll returns the same items; keep the array so memoised
	// thread grouping and the panel skip the work.
	const unchanged = incoming.every((item) => {
		const known = byId.get(item.id);
		return known !== undefined && JSON.stringify(known) === JSON.stringify(item);
	});
	if (unchanged) return current;
	for (const item of incoming) byId.set(item.id, item);
	return [...byId.values()]
		.sort((left, right) => right.createdAt.localeCompare(left.createdAt))
		.slice(0, MAX_ACTIVITIES);
};

/** Poll team histories so observing a team never consumes one SSE connection per agent. */
export function useTeamActivity(participants: TeamActivityParticipant[]) {
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
		const snapshot = participants;
		const nextRuntime: Record<string, TeamMemberRuntime> = {};
		for (const participant of snapshot) {
			if (participant.sessionId) nextRuntime[participant.sessionId] = initialRuntime(participant);
		}
		setRuntimeBySession(nextRuntime);
		setActivities([]);

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
						// A member session deleted after the team was formed is gone, not failing.
						const gone = (error as { status?: number }).status === 404;
						setRuntimeBySession((current) => ({
							...current,
							[participant.sessionId as string]: {
								...initialRuntime(participant),
								status: gone ? 'idle' : 'error',
								detail: gone ? 'Phiên làm việc không còn' : 'Không tải được lịch sử hoạt động',
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
	}, [participantKey, participants]);

	return { runtimeBySession, activities };
}
