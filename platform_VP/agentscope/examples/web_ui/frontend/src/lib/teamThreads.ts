/**
 * Pure helpers for the team panel: turn the flat activity feed into
 * "who talks to whom" threads, and summarise tool inputs for people.
 *
 * Kept free of runtime imports so node tests can transpile and run it alone.
 */

export interface TeamActivityItem {
	id: string;
	sessionId: string;
	sourceName: string;
	targetName: string | null;
	type: 'communication' | 'tool';
	/** TeamSay kind, `assign` for AgentInvite, null when unknown. */
	kind: string | null;
	toolName: string;
	detail: string | null;
	state: 'running' | 'success' | 'error';
	createdAt: string;
	handoffId: string | null;
	threadId: string | null;
	inReplyTo: string | null;
	/** Short human summary of a tool's input, e.g. "Đà Nẵng · 15/11/2026 · 09:00". */
	argsSummary: string | null;
}

export interface TeamThreadMessage {
	item: TeamActivityItem;
	/** Tool calls the recipient made while working on this request. */
	tools: TeamActivityItem[];
}

export interface TeamThread {
	id: string;
	sourceName: string;
	targetName: string | null;
	messages: TeamThreadMessage[];
	participants: string[];
	lastAt: string;
	state: TeamActivityItem['state'];
}

export interface TeamToolGroup {
	agentName: string;
	tools: TeamActivityItem[];
	lastAt: string;
}

export interface TeamThreadView {
	threads: TeamThread[];
	otherTools: TeamToolGroup[];
	/** Every name that appears as a sender, recipient or tool caller. */
	agents: string[];
}

/** Kinds that ask the recipient to do work; its tools nest under them. */
const REQUEST_KINDS = new Set(['assign', 'handoff', 'question']);
/** Kinds that answer an earlier request; unlinked ones chain to it. */
const REPLY_KINDS = new Set(['answer', 'result', 'error', 'progress', 'conflict']);

const ARG_PRIORITY = [
	'city',
	'location',
	'area',
	'origin',
	'from',
	'departure',
	'destination',
	'to',
	'arrival',
	'date',
	'start_date',
	'end_date',
	'check_in',
	'check_out',
	'departure_date',
	'return_date',
	'time',
	'start_time',
	'end_time',
	'datetime',
	'flight_number',
	'flight_no',
	'flight',
	'name',
	'category',
	'query',
	'keyword',
	'guests',
	'adults',
	'children',
	'passengers',
];
const ARG_PRIORITY_HINT = /(date|time|city|origin|destination|flight)/i;
const SKIP_ARG_KEY =
	/(^|_)(ids?|uuid|key|token|session|handoff|thread|hash|secret|password|signature|cursor|page|limit|offset)$/i;
const INTERNAL_ID = /^[0-9a-f]{24,}$/i;
const MAX_ARG_LENGTH = 40;
const MAX_ARGS = 4;

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_DATETIME = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/;
const CLOCK = /^(\d{2}):(\d{2}):\d{2}$/;

/** ISO dates read as dd/mm/yyyy; datetimes keep the written wall-clock time. */
export function formatArgValue(value: unknown): string | null {
	if (typeof value === 'number') return Number.isFinite(value) ? String(value) : null;
	if (typeof value !== 'string') return null;
	const text = value.trim();
	if (!text || text.length > MAX_ARG_LENGTH || INTERNAL_ID.test(text)) return null;
	let match = ISO_DATE.exec(text);
	if (match) return `${match[3]}/${match[2]}/${match[1]}`;
	match = ISO_DATETIME.exec(text);
	if (match) return `${match[3]}/${match[2]}/${match[1]} ${match[4]}:${match[5]}`;
	match = CLOCK.exec(text);
	if (match) return `${match[1]}:${match[2]}`;
	return text.replace(/@[0-9a-f]{8,}\b/gi, '');
}

const argRank = (key: string, order: number): number => {
	const normalized = key.toLowerCase();
	const index = ARG_PRIORITY.indexOf(normalized);
	if (index >= 0) return index;
	if (ARG_PRIORITY_HINT.test(normalized)) return ARG_PRIORITY.length;
	return ARG_PRIORITY.length + 1 + order;
};

/**
 * Up to four meaningful scalar values of a tool input, joined by " · ".
 * Ids, flags and long text are skipped; one nested object level is read.
 */
export function summarizeToolArgs(input: unknown): string | null {
	let value: unknown = input;
	if (typeof input === 'string') {
		try {
			value = JSON.parse(input);
		} catch {
			return null;
		}
	}
	if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
	const candidates: Array<{ rank: number; text: string }> = [];
	let order = 0;
	const visit = (entries: Array<[string, unknown]>, depth: number) => {
		for (const [key, field] of entries) {
			order += 1;
			if (SKIP_ARG_KEY.test(key)) continue;
			if (Array.isArray(field)) {
				const parts = field.map(formatArgValue);
				if (parts.length > 0 && parts.every(Boolean)) {
					const joined = parts.join(', ');
					if (joined.length <= MAX_ARG_LENGTH) candidates.push({ rank: argRank(key, order), text: joined });
				}
				continue;
			}
			if (field && typeof field === 'object') {
				if (depth === 0) visit(Object.entries(field as Record<string, unknown>), 1);
				continue;
			}
			const text = formatArgValue(field);
			if (text) candidates.push({ rank: argRank(key, order), text });
		}
	};
	visit(Object.entries(value as Record<string, unknown>), 0);
	const picked: string[] = [];
	for (const { text } of candidates.sort((left, right) => left.rank - right.rank)) {
		if (picked.includes(text)) continue;
		picked.push(text);
		if (picked.length === MAX_ARGS) break;
	}
	return picked.length > 0 ? picked.join(' · ') : null;
}

/** `mcp__Travel__search_attractions` reads as "search attractions". */
export function readableToolName(name: string): string {
	const bare = name.replace(/^mcp__.+?__/, '');
	return bare.replace(/_+/g, ' ').trim() || name;
}

/** `Name@abcd1234` reads as `Name`. */
export function stripHandle(value: string): string {
	return value.split('@')[0]?.trim() || value;
}

const timeOf = (item: TeamActivityItem): number => {
	const parsed = Date.parse(item.createdAt);
	return Number.isNaN(parsed) ? 0 : parsed;
};

const chronological = (left: TeamActivityItem, right: TeamActivityItem) =>
	timeOf(left) - timeOf(right) || left.id.localeCompare(right.id);

interface DraftThread {
	id: string;
	messages: TeamThreadMessage[];
}

/**
 * Group communications into threads (thread_id, then the in_reply_to chain,
 * then a reply to the latest request of the opposite pair), nest each
 * recipient's tool calls under the request it was working on, and collect
 * the remaining tool calls per agent.
 */
export function groupTeamThreads(items: TeamActivityItem[]): TeamThreadView {
	const communications = items.filter((item) => item.type === 'communication').sort(chronological);
	const tools = items.filter((item) => item.type === 'tool').sort(chronological);

	const drafts = new Map<string, DraftThread>();
	const threadOfHandoff = new Map<string, string>();
	const draftOrder: DraftThread[] = [];

	const reversedPairThread = (item: TeamActivityItem): DraftThread | null => {
		for (let index = draftOrder.length - 1; index >= 0; index -= 1) {
			const draft = draftOrder[index];
			const root = draft?.messages[0]?.item;
			if (
				draft &&
				root &&
				REQUEST_KINDS.has(root.kind ?? '') &&
				root.sourceName === item.targetName &&
				root.targetName === item.sourceName
			) {
				return draft;
			}
		}
		return null;
	};

	for (const item of communications) {
		const linked =
			(item.threadId && (threadOfHandoff.get(item.threadId) ?? item.threadId)) ||
			(item.inReplyTo && (threadOfHandoff.get(item.inReplyTo) ?? item.inReplyTo)) ||
			null;
		let draft = linked ? drafts.get(linked) : undefined;
		if (!draft && !linked && REPLY_KINDS.has(item.kind ?? '')) {
			draft = reversedPairThread(item) ?? undefined;
		}
		if (!draft) {
			const id = linked ?? item.handoffId ?? item.id;
			draft = { id, messages: [] };
			drafts.set(id, draft);
			draftOrder.push(draft);
		}
		draft.messages.push({ item, tools: [] });
		if (item.handoffId) threadOfHandoff.set(item.handoffId, draft.id);
	}

	const leftovers = new Map<string, TeamActivityItem[]>();
	for (const tool of tools) {
		const at = timeOf(tool);
		// The innermost (latest) open request addressed to this agent wins.
		let best: TeamThreadMessage | null = null;
		let bestStart = Number.NEGATIVE_INFINITY;
		for (const draft of draftOrder) {
			for (let index = 0; index < draft.messages.length; index += 1) {
				const message = draft.messages[index] as TeamThreadMessage;
				const request = message.item;
				if (request.targetName !== tool.sourceName || !REQUEST_KINDS.has(request.kind ?? '')) continue;
				const start = timeOf(request);
				const reply = draft.messages
					.slice(index + 1)
					.find((later) => later.item.sourceName === tool.sourceName);
				const end = reply ? timeOf(reply.item) : Number.POSITIVE_INFINITY;
				if (at < start || at > end || start < bestStart) continue;
				best = message;
				bestStart = start;
			}
		}
		if (best) {
			best.tools.push(tool);
		} else {
			const list = leftovers.get(tool.sourceName) ?? [];
			list.push(tool);
			leftovers.set(tool.sourceName, list);
		}
	}

	const agents = new Set<string>();
	const threads: TeamThread[] = draftOrder.map((draft) => {
		const root = draft.messages[0]?.item as TeamActivityItem;
		const participants = new Set<string>();
		let last = root;
		let running = false;
		for (const { item, tools: nested } of draft.messages) {
			participants.add(item.sourceName);
			if (item.targetName) participants.add(item.targetName);
			for (const entry of [item, ...nested]) {
				if (entry.state === 'running') running = true;
				if (timeOf(entry) >= timeOf(last)) last = entry;
			}
		}
		for (const name of participants) agents.add(name);
		const tail = draft.messages[draft.messages.length - 1]?.item ?? root;
		return {
			id: draft.id,
			sourceName: root.sourceName,
			targetName: root.targetName,
			messages: draft.messages,
			participants: [...participants],
			lastAt: last.createdAt,
			state: running ? 'running' : tail.state === 'error' ? 'error' : 'success',
		};
	});
	threads.sort((left, right) => (Date.parse(right.lastAt) || 0) - (Date.parse(left.lastAt) || 0));

	const otherTools: TeamToolGroup[] = [...leftovers.entries()].map(([agentName, list]) => {
		agents.add(agentName);
		const newestFirst = [...list].reverse();
		return { agentName, tools: newestFirst, lastAt: newestFirst[0]?.createdAt ?? '' };
	});
	otherTools.sort((left, right) => (Date.parse(right.lastAt) || 0) - (Date.parse(left.lastAt) || 0));

	return { threads, otherTools, agents: [...agents] };
}

/** Only the threads and lookups that involve `agentName`; all when null. */
export function filterTeamThreads(view: TeamThreadView, agentName: string | null): TeamThreadView {
	if (!agentName) return view;
	return {
		threads: view.threads.filter((thread) => thread.participants.includes(agentName)),
		otherTools: view.otherTools.filter((group) => group.agentName === agentName),
		agents: view.agents,
	};
}
