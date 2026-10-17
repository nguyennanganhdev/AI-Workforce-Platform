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
	pending_approvals: {
		approval_id: string;
		workflow_id: string;
		summary?: string;
		expires_at?: string;
		status?: string;
	}[];
	snapshot_cursor: string | null;
}

export interface TimelineState {
	readonly binding: TimelineBinding;
	readonly workflowState: WorkflowState;
	readonly nextAction: NextAction;
	readonly revision: number;
	readonly messages: readonly AssistantMessage[];
	readonly activity: readonly ConversationEvent[];
	readonly approvalIds: readonly string[];
	readonly cursor: string | null;
	readonly sequence: number;
	readonly eventBodies: Readonly<Record<string, string>>;
	readonly closedBarrier: boolean;
	readonly connection: 'idle' | 'connecting' | 'live' | 'reconnecting' | 'blocked';
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

const payloadFields: Record<string, readonly string[]> = {
	'request.accepted': ['request_id'],
	'workflow.status_changed': ['state', 'revision'],
	'ticket.created': ['ticket_id', 'status'],
	'ticket.status_changed': ['status', 'public_details'],
	'assistant.message': ['message_id', 'text'],
	'approval.required': ['approval_id', 'summary', 'expires_at'],
	'approval.resolved': ['approval_id', 'status'],
	'operation.status_changed': [
		'operation_type',
		'status_schema',
		'status',
		'external_reference',
	],
	'workflow.awaiting_user': ['reason', 'revision'],
	'workflow.needs_attention': ['reason_code'],
	'workflow.closed': ['state', 'revision', 'reason', 'closed_at'],
};

export const timelineKey = (binding: TimelineBinding): string =>
	JSON.stringify([
		binding.identityKey,
		binding.conversationId,
		binding.workflowId,
		binding.externalUserId,
		binding.externalConversationId,
		binding.externalTicketId,
	]);

export function createTimeline(binding: TimelineBinding): TimelineState {
	if (
		[
			binding.identityKey,
			binding.conversationId,
			binding.workflowId,
			binding.externalUserId,
			binding.externalConversationId,
		].some((value) => !value)
	)
		throw new Error('Thiếu định danh hộp chat');
	return {
		binding,
		workflowState: 'accepted',
		nextAction: 'watch_request',
		revision: 0,
		messages: [],
		activity: [],
		approvalIds: [],
		cursor: null,
		sequence: 0,
		eventBodies: {},
		closedBarrier: false,
		connection: 'idle',
	};
}

function opaque(value: unknown): value is string {
	return (
		typeof value === 'string' &&
		value.length > 0 &&
		value.length <= 200 &&
		!/[\r\n\0]/.test(value)
	);
}

function timestamp(value: unknown): value is string {
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

function canonical(value: unknown): unknown {
	if (Array.isArray(value)) return value.map(canonical);
	if (value !== null && typeof value === 'object')
		return Object.fromEntries(
			Object.entries(value)
				.sort(([left], [right]) => left.localeCompare(right))
				.map(([key, item]) => [key, canonical(item)]),
		);
	return value;
}

function stringField(payload: Readonly<Record<string, unknown>>, field: string): string {
	const value = payload[field];
	if (
		typeof value !== 'string' ||
		value.length === 0 ||
		value.length > 20_000 ||
		value.includes('\0')
	)
		throw new Error(`Sự kiện thiếu ${field}`);
	return value;
}

function opaqueField(payload: Readonly<Record<string, unknown>>, field: string): string {
	const value = payload[field];
	if (!opaque(value)) throw new Error(`Sự kiện thiếu ${field}`);
	return value;
}

function moveWorkflow(
	state: TimelineState,
	workflowState: unknown,
	revision: unknown,
): TimelineState {
	if (
		typeof workflowState !== 'string' ||
		!Object.hasOwn(actions, workflowState) ||
		!Number.isSafeInteger(revision) ||
		Number(revision) < 1
	)
		throw new Error('Trạng thái workflow không hợp lệ');
	if (Number(revision) < state.revision) return state;
	if (Number(revision) === state.revision && workflowState !== state.workflowState)
		throw new Error('Xung đột revision workflow');
	if (state.closedBarrier && workflowState !== 'closed') return state;
	return {
		...state,
		workflowState: workflowState as WorkflowState,
		nextAction: actions[workflowState as WorkflowState],
		revision: Number(revision),
	};
}

function mergeMessages(
	state: TimelineState,
	messages: readonly AssistantMessage[],
	allowNew: boolean,
): TimelineState {
	const merged = [...state.messages];
	for (const message of messages) {
		if (
			message.workflow_id !== state.binding.workflowId ||
			message.sender !== 'assistant' ||
			!opaque(message.message_id) ||
			typeof message.text !== 'string' ||
			!message.text ||
			!timestamp(message.created_at)
		)
			throw new Error('Tin nhắn không thuộc workflow này');
		const existing = merged.find((item) => item.message_id === message.message_id);
		if (existing && existing.text !== message.text)
			throw new Error('Xung đột nội dung message_id');
		if (!existing && !allowNew) throw new Error('Workflow đã đóng không nhận tin nhắn mới');
		if (!existing) merged.push(message);
	}
	return { ...state, messages: merged };
}

export function applyReceipt(state: TimelineState, receipt: InboundReceipt): TimelineState {
	const binding = state.binding;
	if (
		receipt.conversation_id !== binding.conversationId ||
		receipt.workflow_id !== binding.workflowId ||
		(receipt.external_ticket_id ?? null) !== binding.externalTicketId
	)
		throw new Error('Kết quả thuộc hộp chat khác');
	const pending = ['accepted', 'queued', 'running'].includes(receipt.request_status);
	const failed = ['failed', 'blocked'].includes(receipt.request_status);
	if (!pending && !failed && receipt.request_status !== 'completed')
		throw new Error('Trạng thái request không hợp lệ');
	const expected =
		receipt.workflow_state === 'closed'
			? 'none'
			: pending
				? 'watch_request'
				: failed
					? 'resolve_attention'
					: actions[receipt.workflow_state];
	if (receipt.next_action !== expected || (pending && receipt.result != null))
		throw new Error('next_action không phù hợp request/workflow');
	const stale = receipt.workflow_revision < state.revision;
	const moved = moveWorkflow(state, receipt.workflow_state, receipt.workflow_revision);
	const merged = mergeMessages(
		moved,
		receipt.result?.messages ?? [],
		!stale && !state.closedBarrier,
	);
	return {
		...merged,
		nextAction: stale ? merged.nextAction : receipt.next_action,
		closedBarrier:
			state.closedBarrier || (!stale && receipt.workflow_state === 'closed'),
	};
}

export function applyEvent(state: TimelineState, event: ConversationEvent): TimelineState {
	const binding = state.binding;
	if (
		event.schema_version !== '1' ||
		event.conversation_id !== binding.conversationId ||
		event.workflow_id !== binding.workflowId ||
		event.external_user_id !== binding.externalUserId ||
		event.external_conversation_id !== binding.externalConversationId ||
		(event.external_ticket_id ?? null) !== binding.externalTicketId
	)
		throw new Error('Sự kiện thuộc hộp chat khác');
	if (
		!opaque(event.event_id) ||
		!Number.isSafeInteger(event.sequence) ||
		event.sequence < 1 ||
		!Object.hasOwn(payloadFields, event.event_type) ||
		typeof event.payload !== 'object' ||
		event.payload === null ||
		Array.isArray(event.payload) ||
		!timestamp(event.occurred_at) ||
		!timestamp(event.recorded_at)
	)
		throw new Error('Envelope sự kiện không hợp lệ');
	if (
		Object.keys(event.payload).some(
			(key) => !payloadFields[event.event_type].includes(key),
		)
	)
		throw new Error('Sự kiện chứa trường không công khai');
	const body = JSON.stringify(canonical(event));
	const previousBody = state.eventBodies[event.event_id];
	if (previousBody !== undefined) {
		if (previousBody !== body) throw new Error('event_id có nội dung xung đột');
		return state;
	}
	if (state.closedBarrier)
		throw new Error('Workflow đã đóng không nhận sự kiện mới');
	if (event.sequence <= state.sequence) throw new Error('Sequence sự kiện không tăng');
	let updated = state;
	const payload = event.payload;
	switch (event.event_type) {
		case 'assistant.message': {
			const messageId = opaqueField(payload, 'message_id');
			updated = mergeMessages(
				state,
				[
					{
						message_id: messageId,
						workflow_id: binding.workflowId,
						sender: 'assistant',
						text: stringField(payload, 'text'),
						created_at: event.occurred_at,
					},
				],
				!state.closedBarrier,
			);
			break;
		}
		case 'workflow.status_changed':
			updated = moveWorkflow(state, payload.state, payload.revision);
			break;
		case 'workflow.closed':
			if (payload.state !== 'closed' || !timestamp(payload.closed_at))
				throw new Error('Sự kiện đóng workflow không hợp lệ');
			stringField(payload, 'reason');
			updated = {
				...moveWorkflow(state, 'closed', payload.revision),
				closedBarrier: true,
			};
			break;
		case 'workflow.awaiting_user':
			stringField(payload, 'reason');
			updated = moveWorkflow(state, 'awaiting_user', payload.revision);
			break;
		case 'approval.required': {
			const approvalId = opaqueField(payload, 'approval_id');
			stringField(payload, 'summary');
			if (!timestamp(payload.expires_at)) throw new Error('Approval thiếu hạn hợp lệ');
			updated = {
				...state,
				approvalIds: [...new Set([...state.approvalIds, approvalId])],
			};
			break;
		}
		case 'approval.resolved': {
			const approvalId = opaqueField(payload, 'approval_id');
			opaqueField(payload, 'status');
			updated = {
				...state,
				approvalIds: state.approvalIds.filter((id) => id !== approvalId),
			};
			break;
		}
		case 'operation.status_changed':
			opaqueField(payload, 'operation_type');
			opaqueField(payload, 'status_schema');
			opaqueField(payload, 'status');
			if (
				payload.external_reference !== undefined &&
				payload.external_reference !== null &&
				!opaque(payload.external_reference)
			)
				throw new Error('external_reference không hợp lệ');
			break;
		case 'ticket.created':
			opaqueField(payload, 'ticket_id');
			opaqueField(payload, 'status');
			break;
		case 'ticket.status_changed':
			opaqueField(payload, 'status');
			if (
				payload.public_details !== undefined &&
				payload.public_details !== null &&
				(typeof payload.public_details !== 'string' ||
					payload.public_details.length > 2000)
			)
				throw new Error('public_details không hợp lệ');
			break;
		case 'workflow.needs_attention':
			opaqueField(payload, 'reason_code');
			break;
		case 'request.accepted':
			opaqueField(payload, 'request_id');
			break;
	}
	return {
		...updated,
		cursor: event.event_id,
		sequence: event.sequence,
		eventBodies: { ...state.eventBodies, [event.event_id]: body },
		activity:
			event.event_type === 'assistant.message'
				? updated.activity
				: [...updated.activity, event],
		connection: 'live',
	};
}

export class StaleSnapshotError extends Error {
	constructor() {
		super('Snapshot cũ hơn trạng thái hiện tại');
		this.name = 'StaleSnapshotError';
	}
}

export function applySnapshot(
	state: TimelineState,
	snapshot: TimelineSnapshot,
): TimelineState {
	const binding = state.binding;
	if (
		snapshot.conversation_id !== binding.conversationId ||
		snapshot.external_user_id !== binding.externalUserId ||
		snapshot.external_conversation_id !== binding.externalConversationId ||
		snapshot.workflows.length !== 1
	)
		throw new Error('Snapshot thuộc hộp chat khác');
	const workflow = snapshot.workflows[0];
	if (
		workflow.workflow_id !== binding.workflowId ||
		workflow.external_ticket_id !== binding.externalTicketId ||
		workflow.next_action !== actions[workflow.state] ||
		(snapshot.snapshot_cursor !== null && !opaque(snapshot.snapshot_cursor))
	)
		throw new Error('Snapshot workflow không hợp lệ');
	if (workflow.revision < state.revision) throw new StaleSnapshotError();
	if (
		snapshot.pending_approvals.some(
			(approval) =>
				!opaque(approval.approval_id) || approval.workflow_id !== binding.workflowId,
		) ||
		new Set(snapshot.pending_approvals.map((approval) => approval.approval_id)).size !==
			snapshot.pending_approvals.length
	)
		throw new Error('Snapshot approval không hợp lệ');
	const base = moveWorkflow(
		{ ...state, messages: [], closedBarrier: false },
		workflow.state,
		workflow.revision,
	);
	const merged = mergeMessages(base, snapshot.messages, true);
	return {
		...merged,
		nextAction: workflow.next_action,
		activity: [],
		approvalIds: snapshot.pending_approvals.map((approval) => approval.approval_id),
		cursor: snapshot.snapshot_cursor,
		sequence: 0,
		eventBodies: {},
		closedBarrier: workflow.state === 'closed',
		connection: 'reconnecting',
	};
}

