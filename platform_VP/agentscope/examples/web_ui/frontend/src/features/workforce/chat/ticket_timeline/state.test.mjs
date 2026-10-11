import assert from 'node:assert/strict';
import test from 'node:test';

import { applyEvent, applySnapshot, createTimeline } from './state.ts';

const binding = (suffix) => ({
	identityKey: 'partner-1:resident-1',
	conversationId: `conversation-${suffix}`,
	workflowId: `workflow-${suffix}`,
	externalUserId: 'resident-1',
	externalConversationId: `external-chat-${suffix}`,
	externalTicketId: `external-ticket-${suffix}`,
});

const event = (target, id, sequence, type, payload) => ({
	schema_version: '1',
	event_id: id,
	sequence,
	event_type: type,
	occurred_at: '2026-10-11T08:00:00Z',
	recorded_at: '2026-10-11T08:00:00Z',
	conversation_id: target.conversationId,
	external_ticket_id: target.externalTicketId,
	external_conversation_id: target.externalConversationId,
	external_user_id: target.externalUserId,
	workflow_id: target.workflowId,
	ticket_id: `ticket-${target.workflowId}`,
	payload,
});

test('two chat boxes never accept each other events', () => {
	const a = binding('A');
	const b = binding('B');
	const eventA = event(a, 'event-A', 1, 'assistant.message', {
		message_id: 'message-A',
		text: 'A'.repeat(500),
	});
	const stateA = applyEvent(createTimeline(a), eventA);
	const stateB = createTimeline(b);
	assert.equal(stateA.messages.length, 1);
	assert.equal(stateB.messages.length, 0);
	assert.throws(() => applyEvent(stateB, eventA), /hộp chat khác/);
});

test('replay deduplicates a bubble and rejects conflicting event ids', () => {
	const target = binding('A');
	const first = event(target, 'event-1', 1, 'assistant.message', {
		message_id: 'message-1',
		text: 'result',
	});
	const applied = applyEvent(createTimeline(target), first);
	assert.equal(applyEvent(applied, first), applied);
	const conflict = { ...first, payload: { ...first.payload, text: 'changed' } };
	assert.throws(() => applyEvent(applied, conflict), /xung đột/);
});

test('closed barrier blocks a late assistant message', () => {
	const target = binding('A');
	const closed = applyEvent(
		createTimeline(target),
		event(target, 'event-close', 1, 'workflow.closed', {
			state: 'closed',
			revision: 2,
			reason: 'customer_confirmed',
			closed_at: '2026-10-11T08:00:01Z',
		}),
	);
	assert.equal(closed.closedBarrier, true);
	assert.throws(
		() =>
			applyEvent(
				closed,
				event(target, 'event-late', 2, 'assistant.message', {
					message_id: 'message-late',
					text: 'late result',
				}),
			),
		/đã đóng/,
	);
});

test('snapshot recovery keeps exactly one workflow binding', () => {
	const target = binding('A');
	const recovered = applySnapshot(createTimeline(target), {
		conversation_id: target.conversationId,
		external_user_id: target.externalUserId,
		external_conversation_id: target.externalConversationId,
		workflows: [
			{
				workflow_id: target.workflowId,
				external_ticket_id: target.externalTicketId,
				state: 'awaiting_user',
				next_action: 'submit_reply',
				revision: 4,
			},
		],
		messages: [],
		pending_approvals: [],
		snapshot_cursor: 'event-4',
	});
	assert.equal(recovered.workflowState, 'awaiting_user');
	assert.equal(recovered.cursor, 'event-4');
});
