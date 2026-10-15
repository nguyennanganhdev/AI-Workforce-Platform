import type { Msg } from '@agentscope-ai/agentscope/message';

import { uniqueMessages, type SessionPresentation } from './presentation.ts';
import type { AgentView, SessionStatus } from '@/api';
import type { ReplyPhase } from '@/hooks/useMessages';

export function liveSessionPresentation(input: {
	id: string;
	ownerId: string;
	ownerName: string;
	agents: AgentView[];
	messages: Msg[];
	replyPhase: ReplyPhase;
	status?: SessionStatus;
	awaitingApproval: boolean;
	loading: boolean;
}): SessionPresentation {
	const participants = new Map(
		input.agents.map((agent) => [
			agent.id,
			{
				id: agent.id,
				name: agent.data.name,
				role: agent.data.invite_config?.invite_description ?? '',
			},
		]),
	);
	if (!participants.has(input.ownerId))
		participants.set(input.ownerId, { id: input.ownerId, name: input.ownerName, role: '' });
	const messages = input.loading
		? []
		: uniqueMessages(input.messages).map((message) => ({
				...message,
				metadata: { ...message.metadata, office_agent_id: input.ownerId },
			}));
	const completed = new Set(
		messages.flatMap((message) =>
			message.content
				.filter((block) => block.type === 'tool_result' && block.state !== 'running')
				.map((block) => block.id),
		),
	);
	const pending = messages.some(
		(message) =>
			message.role === 'assistant' &&
			message.content.some(
				(block) =>
					block.type === 'tool_call' &&
					!completed.has(block.id) &&
					block.state === 'asking',
			),
	);
	const external = messages.some(
		(message) =>
			message.role === 'assistant' &&
			message.content.some(
				(block) =>
					block.type === 'tool_call' &&
					!completed.has(block.id) &&
					block.state === 'submitted',
			),
	);
	const phase: SessionPresentation['phase'] = input.loading
		? 'idle'
		: input.awaitingApproval || pending || input.status === 'awaiting_permission'
			? 'waiting_approval'
			: external || input.status === 'awaiting_external_result'
				? 'waiting_external'
				: input.replyPhase !== 'idle' || input.status === 'running'
					? 'working'
					: 'idle';
	return {
		id: `session:${input.id}`,
		source: 'live',
		messages,
		participants: [...participants.values()],
		phase,
		activeAgentId: phase === 'working' ? input.ownerId : null,
	};
}
