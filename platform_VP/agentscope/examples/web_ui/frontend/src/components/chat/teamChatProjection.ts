import type {
	ContentBlock,
	Msg,
	ToolCallBlock,
} from '@agentscope-ai/agentscope/message';

export type TeamChatMode = 'customer-reply' | 'activity';

export interface VisibleTeamMessage {
	message: Msg;
	teamMode?: TeamChatMode;
}

interface PendingTrace {
	first: Msg;
	last: Msg;
	content: ContentBlock[];
	sources: Record<string, string>;
	running: boolean;
}

function teamSayTarget(message: Msg, call: ToolCallBlock): string | null {
	try {
		const input = JSON.parse(call.input) as { to?: string | null };
		const result = message.content.find(
			(block) => block.type === 'tool_result' && block.id === call.id,
		);
		const effectiveTo = result?.type === 'tool_result' ? result.metadata?.effective_to : null;
		return typeof effectiveTo === 'string' ? effectiveTo : input.to ?? null;
	} catch {
		return null;
	}
}

function isAgentTarget(target: string | null, sourceName: string): boolean {
	if (!target) return false;
	const normalized = target.trim().toLowerCase();
	const source = sourceName.trim().toLowerCase();
	return (
		!['null', 'none', 'customer'].includes(normalized) &&
		normalized.split('@')[0] !== source.split('@')[0]
	);
}

/** Collapse one customer turn's internal TeamSay traffic into one trace row. */
export function projectTeamChatMessages(
	messages: Msg[],
	agentId: string | null,
): VisibleTeamMessage[] {
	const visible: VisibleTeamMessage[] = [];
	let pending: PendingTrace | null = null;

	const flushTrace = () => {
		if (!pending || (pending.content.length === 0 && !pending.running)) {
			pending = null;
			return;
		}
		const { first, last, content, sources, running } = pending;
		visible.push({
			message: {
				...last,
				id: `team-trace:${first.id}`,
				name: '',
				content,
				metadata: { ...last.metadata, team_trace_sources: sources },
				created_at: first.created_at,
				finished_at: running ? null : last.finished_at,
				finished_reason: running ? null : last.finished_reason,
			},
			teamMode: 'activity',
		});
		pending = null;
	};

	for (const message of messages) {
		if (message.role !== 'assistant') {
			flushTrace();
			visible.push({ message });
			continue;
		}

		const ownerFlag = message.metadata?.team_reply_owner;
		const isCustomerReply =
			ownerFlag === true ||
			(ownerFlag !== false &&
				typeof message.metadata?.team_agent_id === 'string' &&
				message.metadata.team_agent_id === agentId);
		const calls = message.content.filter(
			(block): block is ToolCallBlock =>
				block.type === 'tool_call' && block.name === 'TeamSay',
		);
		const callIds = new Set(calls.map((call) => call.id));
		const hasAgentCall = calls.some((call) =>
			isAgentTarget(teamSayTarget(message, call), message.name),
		);
		const hasActiveAgentCall = calls.some((call) => {
			if (!isAgentTarget(teamSayTarget(message, call), message.name)) return false;
			const result = message.content.find(
				(block) => block.type === 'tool_result' && block.id === call.id,
			);
			return result?.type !== 'tool_result' || result.state !== 'error';
		});
		const traceContent = message.content.filter(
			(block) =>
				(block.type === 'tool_call' && block.name === 'TeamSay') ||
				(block.type === 'tool_result' && callIds.has(block.id)),
		);
		const publicContent = message.content.filter(
			(block) =>
				isCustomerReply &&
				!hasActiveAgentCall &&
				(block.type === 'text' || block.type === 'data'),
		);
		const running = !message.finished_at && !message.finished_reason;

		if (traceContent.length > 0 || running) {
			pending ??= {
				first: message,
				last: message,
				content: [],
				sources: {},
				running: false,
			};
			pending.last = message;
			pending.content.push(...traceContent);
			for (const call of calls) pending.sources[call.id] = message.name;
			pending.running ||= running;
		}

		const hasPublicContent = publicContent.length > 0;
		if (
			isCustomerReply &&
			(hasPublicContent || message.finished_reason === 'error')
		) {
			const trace = pending;
			visible.push({
				message: {
					...message,
					content: [...(trace?.content ?? []), ...publicContent],
					created_at: trace?.first.created_at ?? message.created_at,
					metadata: trace
						? { ...message.metadata, team_trace_sources: trace.sources }
						: message.metadata,
				},
				teamMode: 'customer-reply',
			});
			pending = null;
			continue;
		}

		if (!isCustomerReply && !running && !hasAgentCall) continue;
	}

	flushTrace();
	return visible;
}
