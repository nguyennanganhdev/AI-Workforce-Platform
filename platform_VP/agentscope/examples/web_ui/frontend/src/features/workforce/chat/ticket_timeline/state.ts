import type {
	AssistantMessage,
	ConversationEvent,
	InboundReceipt,
	NextAction,
	WorkflowState,
} from '../../shared/contracts/workforce-v1';

export interface TimelineBinding {
	readonly identityKey: string;
	readonly conversationId: string;
	readonly workflowId: string;
	readonly externalUserId: string;
	readonly externalConversationId: string;
	readonly externalTicketId: string | null;
}

export interface TimelineState {
	readonly binding: TimelineBinding;
	readonly state: WorkflowState;
	readonly nextAction: NextAction;
	readonly revision: number;
	readonly messages: readonly AssistantMessage[];
	readonly cards: readonly ConversationEvent[];
	readonly approvalIds: readonly string[];
	readonly cursor: string | null;
	readonly sequence: number;
	readonly seen: readonly string[];
	readonly eventContents: Readonly<Record<string, string>>;
	readonly closedSequence: number | null;
	readonly connection: 'idle' | 'connecting' | 'live' | 'reconnecting' | 'blocked';
}

export interface TimelineSnapshot {
	conversation_id: string;
	external_user_id: string;
	external_conversation_id: string;
	workflows: {
		workflow_id: string;
		external_ticket_id: string | null;
		state: WorkflowState;
		next_action: NextAction;
		revision: number;
	}[];
	messages: AssistantMessage[];
	pending_approvals: { approval_id: string; workflow_id?: string }[];
	snapshot_cursor: string | null;
}

const actions: Record<WorkflowState, NextAction> = {
	accepted: 'watch_request',
	active: 'watch_request',
	waiting_external_event: 'watch_events',
	awaiting_user: 'submit_reply',
	awaiting_approval: 'submit_approval',
	awaiting_confirmation: 'confirm_close',
	needs_attention: 'resolve_attention',
	blocked_authorization: 'resolve_attention',
	blocked_route_changed: 'resolve_attention',
	closed: 'none',
};
const publicTypes = new Set([
	'request.accepted',
	'workflow.status_changed',
	'ticket.created',
	'ticket.status_changed',
	'assistant.message',
	'approval.required',
	'approval.resolved',
	'operation.status_changed',
	'workflow.awaiting_user',
	'workflow.needs_attention',
	'workflow.closed',
]);

export const timelineKey = (binding: TimelineBinding): string =>
	JSON.stringify([
		binding.identityKey,
		binding.conversationId,
		binding.workflowId,
		binding.externalTicketId,
		binding.externalUserId,
		binding.externalConversationId,
	]);

export function createTimeline(binding: TimelineBinding): TimelineState {
	if (
		[
			binding.identityKey,
			binding.conversationId,
			binding.workflowId,
			binding.externalUserId,
			binding.externalConversationId,
		].some((v) => !v)
	)
		throw new Error('Thiếu định danh hộp chat');
	return {
		binding,
		state: 'accepted',
		nextAction: 'watch_request',
		revision: 0,
		messages: [],
		cards: [],
		approvalIds: [],
		cursor: null,
		sequence: 0,
		seen: [],
		eventContents: {},
		closedSequence: null,
		connection: 'idle',
	};
}

function stringField(payload: Readonly<Record<string, unknown>>, field: string): string {
	const value = payload[field];
	if (typeof value !== 'string' || !value) throw new Error(`Sự kiện thiếu ${field}`);
	return value;
}

function timestamp(value: unknown): boolean {
	if (typeof value !== 'string') return false;
	const match =
		/^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$/.exec(
			value,
		);
	if (!match || !Number.isFinite(Date.parse(value))) return false;
	const [, year, month, day, hour, minute, second] = match.map(Number);
	const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
	const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
	return (
		month >= 1 &&
		month <= 12 &&
		day >= 1 &&
		day <= days[month - 1] &&
		hour < 24 &&
		minute < 60 &&
		second < 60
	);
}

function opaqueId(value: unknown): value is string {
	return (
		typeof value === 'string' &&
		value.length > 0 &&
		value.length <= 200 &&
		!/[\r\n\0]/.test(value)
	);
}

function canonical(value: unknown): unknown {
	if (Array.isArray(value)) return value.map(canonical);
	if (typeof value === 'object' && value !== null)
		return Object.fromEntries(
			Object.entries(value)
				.sort(([a], [b]) => a.localeCompare(b))
				.map(([key, item]) => [key, canonical(item)]),
		);
	return value;
}

const payloadFields: Record<string, readonly string[]> = {
	'request.accepted': ['request_id'],
	'workflow.status_changed': ['state', 'revision'],
	'ticket.created': ['ticket_id', 'status'],
	'ticket.status_changed': ['status', 'public_details'],
	'assistant.message': ['message_id', 'text'],
	'approval.required': ['approval_id', 'summary', 'expires_at'],
	'approval.resolved': ['approval_id', 'status'],
	'operation.status_changed': ['operation_type', 'status_schema', 'status', 'external_reference'],
	'workflow.awaiting_user': ['reason', 'revision'],
	'workflow.needs_attention': ['reason_code'],
	'workflow.closed': ['state', 'revision', 'reason', 'closed_at'],
};

function revisionState(state: TimelineState, value: unknown, revision: unknown): TimelineState {
	if (
		typeof value !== 'string' ||
		!Object.hasOwn(actions, value) ||
		!Number.isSafeInteger(revision) ||
		Number(revision) < 1
	)
		throw new Error('Trạng thái workflow không hợp lệ');
	if (Number(revision) < state.revision || state.state === 'closed') return state;
	if (Number(revision) === state.revision && value !== state.state)
		throw new Error('Xung đột phiên bản workflow');
	return {
		...state,
		state: value as WorkflowState,
		nextAction: actions[value as WorkflowState],
		revision: Number(revision),
	};
}

function mergeMessages(state: TimelineState, messages: readonly AssistantMessage[]): TimelineState {
	const result = [...state.messages];
	for (const message of messages) {
		if (
			message.workflow_id !== state.binding.workflowId ||
			!message.message_id ||
			message.sender !== 'assistant' ||
			typeof message.text !== 'string' ||
			!message.text ||
			!timestamp(message.created_at)
		)
			throw new Error('Tin nhắn sai workflow');
		const old = result.find((m) => m.message_id === message.message_id);
		if (old && old.text !== message.text) throw new Error('Xung đột nội dung tin nhắn');
		if (!old) result.push(message);
	}
	return { ...state, messages: result };
}

export function applyReceipt(state: TimelineState, receipt: InboundReceipt): TimelineState {
	const b = state.binding;
	if (
		receipt.conversation_id !== b.conversationId ||
		receipt.workflow_id !== b.workflowId ||
		(receipt.external_ticket_id ?? null) !== b.externalTicketId
	)
		throw new Error('Kết quả thuộc hộp chat khác');
	const pending = ['accepted', 'queued', 'running'].includes(receipt.request_status);
	const terminalFailure = ['failed', 'blocked'].includes(receipt.request_status);
	if (!pending && !terminalFailure && receipt.request_status !== 'completed')
		throw new Error('Trạng thái lượt xử lý không hợp lệ');
	const expected =
		receipt.workflow_state === 'closed'
			? 'none'
			: pending
				? 'watch_request'
				: terminalFailure
					? 'resolve_attention'
					: actions[receipt.workflow_state];
	if (receipt.next_action !== expected || (pending && receipt.result != null))
		throw new Error('Hướng xử lý tiếp theo không hợp lệ');
	const updated = revisionState(state, receipt.workflow_state, receipt.workflow_revision);
	const current =
		receipt.workflow_revision >= state.revision && updated.state === receipt.workflow_state;
	return mergeMessages(
		current ? { ...updated, nextAction: receipt.next_action } : updated,
		receipt.result?.messages ?? [],
	);
}

export function applyEvent(state: TimelineState, event: ConversationEvent): TimelineState {
	const b = state.binding;
	if (
		event.schema_version !== '1' ||
		event.conversation_id !== b.conversationId ||
		event.workflow_id !== b.workflowId ||
		event.external_user_id !== b.externalUserId ||
		event.external_conversation_id !== b.externalConversationId ||
		(event.external_ticket_id ?? null) !== b.externalTicketId
	)
		throw new Error('Sự kiện thuộc hộp chat khác');
	if (
		!opaqueId(event.event_id) ||
		!Number.isSafeInteger(event.sequence) ||
		event.sequence < 1 ||
		!publicTypes.has(event.event_type) ||
		typeof event.payload !== 'object' ||
		event.payload === null ||
		Array.isArray(event.payload) ||
		!timestamp(event.recorded_at) ||
		!timestamp(event.occurred_at)
	)
		throw new Error('Sự kiện không hợp lệ');
	if (Object.keys(event.payload).some((key) => !payloadFields[event.event_type].includes(key)))
		throw new Error('Sự kiện chứa trường ngoài hợp đồng công khai');
	const contents = JSON.stringify(canonical(event));
	if (Object.hasOwn(state.eventContents, event.event_id)) {
		if (state.eventContents[event.event_id] !== contents)
			throw new Error('Xung đột nội dung sự kiện');
		return state;
	}
	if (event.sequence <= state.sequence) throw new Error('Thứ tự sự kiện không hợp lệ');
	let updated = state;
	const p = event.payload;
	switch (event.event_type) {
		case 'assistant.message':
			if (
				state.state === 'closed' &&
				state.closedSequence !== null &&
				event.sequence > state.closedSequence &&
				!state.messages.some((m) => m.message_id === p.message_id)
			)
				throw new Error('Workflow đã đóng không nhận tin nhắn mới');
			updated = mergeMessages(state, [
				{
					message_id: stringField(p, 'message_id'),
					workflow_id: b.workflowId,
					sender: 'assistant',
					text: stringField(p, 'text'),
					created_at: event.occurred_at,
				},
			]);
			break;
		case 'workflow.closed':
			if (p.state !== 'closed') throw new Error('Sự kiện đóng không hợp lệ');
			stringField(p, 'reason');
			if (!timestamp(p.closed_at)) throw new Error('Thời gian đóng không hợp lệ');
			updated = revisionState(state, p.state, p.revision);
			break;
		case 'workflow.status_changed':
			updated = revisionState(state, p.state, p.revision);
			break;
		case 'workflow.awaiting_user':
			stringField(p, 'reason');
			updated = revisionState(state, 'awaiting_user', p.revision);
			break;
		case 'approval.required':
			if (!timestamp(p.expires_at)) throw new Error('Xác nhận thiếu hạn hiệu lực');
			updated = {
				...state,
				approvalIds: [...new Set([...state.approvalIds, stringField(p, 'approval_id')])],
			};
			stringField(p, 'summary');
			break;
		case 'approval.resolved':
			updated = {
				...state,
				approvalIds: state.approvalIds.filter((id) => id !== stringField(p, 'approval_id')),
			};
			stringField(p, 'status');
			break;
		case 'operation.status_changed':
			stringField(p, 'operation_type');
			stringField(p, 'status_schema');
			stringField(p, 'status');
			break;
		case 'ticket.status_changed':
			stringField(p, 'status');
			break;
		case 'ticket.created':
			stringField(p, 'ticket_id');
			stringField(p, 'status');
			break;
		case 'workflow.needs_attention':
			stringField(p, 'reason_code');
			break;
		case 'request.accepted':
			stringField(p, 'request_id');
			break;
	}
	return {
		...updated,
		cursor: event.event_id,
		sequence: event.sequence,
		seen: [...state.seen, event.event_id],
		eventContents: { ...state.eventContents, [event.event_id]: contents },
		closedSequence:
			event.event_type === 'workflow.closed' ? event.sequence : state.closedSequence,
		cards: event.event_type === 'assistant.message' ? updated.cards : [...updated.cards, event],
		connection: 'live',
	};
}

export class StaleTimelineSnapshotError extends Error {
	constructor() {
		super('Bản phục hồi cũ');
		this.name = 'StaleTimelineSnapshotError';
	}
}

export function applySnapshot(state: TimelineState, snapshot: TimelineSnapshot): TimelineState {
	const b = state.binding;
	if (
		snapshot.conversation_id !== b.conversationId ||
		snapshot.external_user_id !== b.externalUserId ||
		snapshot.external_conversation_id !== b.externalConversationId ||
		snapshot.workflows.length !== 1
	)
		throw new Error('Bản phục hồi thuộc hộp chat khác');
	const workflow = snapshot.workflows[0];
	if (workflow.workflow_id !== b.workflowId || workflow.external_ticket_id !== b.externalTicketId)
		throw new Error('Bản phục hồi sai ticket');
	if (
		workflow.next_action !== actions[workflow.state] ||
		(snapshot.snapshot_cursor !== null && !opaqueId(snapshot.snapshot_cursor))
	)
		throw new Error('Bản phục hồi có trạng thái hoặc cursor không hợp lệ');
	const updated = revisionState(state, workflow.state, workflow.revision);
	if (updated.revision !== workflow.revision || updated.state !== workflow.state)
		throw new StaleTimelineSnapshotError();
	if (
		snapshot.pending_approvals.some(
			(a) =>
				!opaqueId(a.approval_id) ||
				(a.workflow_id !== undefined && a.workflow_id !== b.workflowId),
		) ||
		new Set(snapshot.pending_approvals.map((a) => a.approval_id)).size !==
			snapshot.pending_approvals.length
	)
		throw new Error('Bản phục hồi thiếu định danh xác nhận');
	return {
		...mergeMessages({ ...updated, messages: [] }, snapshot.messages),
		cards: [],
		seen: [],
		eventContents: {},
		closedSequence: null,
		sequence: 0,
		cursor: snapshot.snapshot_cursor,
		approvalIds: snapshot.pending_approvals.map((a) => a.approval_id),
		connection: 'reconnecting',
	};
}
