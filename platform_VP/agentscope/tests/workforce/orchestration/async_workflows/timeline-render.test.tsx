import { expect, test } from 'bun:test';
import { renderToStaticMarkup } from '../../../../examples/web_ui/frontend/node_modules/react-dom/server';

import { TicketTimeline } from '../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/TicketTimeline';
import { createTimeline } from '../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/state';
import type { ApprovalView } from '../../../../examples/web_ui/frontend/src/features/workforce/approvals';

const state = createTimeline({ identityKey: 'owner', conversationId: 'conversation-A', workflowId: 'workflow-A',
  externalUserId: 'user-1', externalConversationId: 'chat-A', externalTicketId: 'ticket-A' });
const onClose = async () => {};

test('UI033 renders waiting and reconnecting independently', () => {
  const html = renderToStaticMarkup(<TicketTimeline state={{ ...state, state: 'waiting_external_event', revision: 2, connection: 'reconnecting' }} onClose={onClose} />);
  expect(html).toContain('Đang chờ cập nhật từ nhà cung cấp');
  expect(html).toContain('Đang kết nối lại');
  expect(html).toContain('disabled=""');
});

test('UI034 closed ticket disables close and cannot offer stop tracking', () => {
  const html = renderToStaticMarkup(<TicketTimeline state={{ ...state, state: 'closed', revision: 3 }} onClose={onClose} />);
  expect(html).toContain('Đã đóng yêu cầu'); expect(html).not.toContain('type="checkbox"');
});

test('UI035 assistant text is escaped and labeled', () => {
  const html = renderToStaticMarkup(<TicketTimeline state={{ ...state,
    messages: [{ message_id: 'message-A', workflow_id: state.binding.workflowId, sender: 'assistant',
      text: '<script>alert(1)</script>', created_at: '2026-10-10T09:00:00Z' }] }} onClose={onClose} />);
  expect(html).toContain('Trợ lý'); expect(html).toContain('&lt;script&gt;'); expect(html).not.toContain('<script>');
});

test('UI036 reuses Execution ApprovalCard only for approval bound to this timeline', () => {
  const approval: ApprovalView = { approval_id: 'approval-A', call_id: 'call-A', status: 'pending',
    arguments_hash: 'args', quote_hash: 'quote', expires_at: '2099-10-10T09:00:00Z',
    quote: { provider: 'Provider A', option: 'Option A', dates: ['10/10/2099'], amount: { amount_minor: 100, currency: 'VND' },
      fees: { amount_minor: 0, currency: 'VND' }, cancellation_terms: 'Demo', quote_ref: 'quote-A', quote_version: '1' }, decision_history: [] };
  const html = renderToStaticMarkup(<TicketTimeline state={{ ...state, state: 'awaiting_approval', revision: 2, approvalIds: ['approval-A'] }}
    onClose={onClose} approvals={[approval, { ...approval, approval_id: 'approval-B', quote: { ...approval.quote, provider: 'Provider B' } }]}
    onDecide={async () => {}} />);
  expect(html).toContain('Provider A'); expect(html).not.toContain('Provider B'); expect(html).toContain('Đồng ý giao dịch');
});
