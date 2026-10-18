import { ReplyFinishedReason } from '@agentscope-ai/agentscope/event';
import type { Msg, ToolCallBlock } from '@agentscope-ai/agentscope/message';

export type TeamChatMode = 'customer-reply' | 'activity';

interface VisibleMessage {
	message: Msg;
	teamMode?: TeamChatMode;
}

export function teamSayTarget(message: Msg, call: ToolCallBlock): string | null {
	try {
		const input = JSON.parse(call.input) as { to?: string | null };
		const result = message.content.find(
			(block) => block.type === 'tool_result' && block.id === call.id,
		);
		const effectiveTo = result?.type === 'tool_result' ? result.metadata?.effective_to : null;
		return typeof effectiveTo === 'string' ? effectiveTo : (input.to ?? null);
	} catch {
		return null;
	}
}

export function isAgentTarget(target: string | null, sourceName: string): boolean {
	if (!target) return false;
	const normalized = target.trim().toLowerCase();
	const source = sourceName.trim().toLowerCase();
	return (
		!['null', 'none', 'customer'].includes(normalized) &&
		normalized.split('@')[0] !== source.split('@')[0]
	);
}

export function visibleTeamMessages(
	msgs: Msg[],
	agentId: string | null,
	teamChat: boolean,
): VisibleMessage[] {
	if (!teamChat) return msgs.map((message) => ({ message }));

	return msgs.flatMap((message): VisibleMessage[] => {
		if (message.role !== 'assistant') return [{ message }];

		const ownerFlag = message.metadata?.team_reply_owner;
		const isCustomerReply =
			ownerFlag === true ||
			(ownerFlag !== false &&
				typeof message.metadata?.team_agent_id === 'string' &&
				message.metadata.team_agent_id === agentId);
		const teamSayCalls = message.content.filter(
			(block): block is ToolCallBlock =>
				block.type === 'tool_call' && block.name === 'TeamSay',
		);
		const teamSayIds = new Set(teamSayCalls.map((call) => call.id));
		const hasAgentCall = teamSayCalls.some((call) =>
			isAgentTarget(teamSayTarget(message, call), message.name),
		);
		const hasActiveAgentCall = teamSayCalls.some((call) => {
			if (!isAgentTarget(teamSayTarget(message, call), message.name)) return false;
			const result = message.content.find(
				(block) => block.type === 'tool_result' && block.id === call.id,
			);
			return result?.type !== 'tool_result' || result.state !== 'error';
		});
		const content = message.content.filter((block) => {
			if (block.type === 'tool_call') return block.name === 'TeamSay';
			if (block.type === 'tool_result') return teamSayIds.has(block.id);
			return (
				isCustomerReply &&
				!hasActiveAgentCall &&
				(block.type === 'text' || block.type === 'data')
			);
		});
		const isRunning = !message.finished_at && !message.finished_reason;
		const hasCustomerContent = content.some(
			(block) => block.type === 'text' || block.type === 'data',
		);

		if (!isCustomerReply && !isRunning && !hasAgentCall) return [];
		if (
			isCustomerReply &&
			!isRunning &&
			!hasCustomerContent &&
			!hasAgentCall &&
			message.finished_reason !== ReplyFinishedReason.ERROR
		) {
			return [];
		}

		return [
			{
				message: { ...message, content },
				teamMode: isCustomerReply ? 'customer-reply' : 'activity',
			},
		];
	});
}
