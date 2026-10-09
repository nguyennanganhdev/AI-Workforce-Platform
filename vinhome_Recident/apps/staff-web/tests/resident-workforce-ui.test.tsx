import {afterAll, afterEach, beforeAll, expect, test, vi} from 'vitest';
import {GlobalRegistrator} from '@happy-dom/global-registrator';
import {act, cleanup, fireEvent, render, waitFor} from '@testing-library/react';
import {WorkforceStatus} from '../../resident-web/src/features/requests/WorkforceStatus';
import type {WorkforceTracking} from '../../resident-web/src/services/use-connected-resident';

beforeAll(() => GlobalRegistrator.register({url: 'http://localhost:3011'}));
afterEach(async () => {
  await act(async () => {
    cleanup();
    // Drain React's scheduled host callback before removing the DOM globals.
    await new Promise<void>(resolve => setImmediate(resolve));
  });
});
afterAll(() => GlobalRegistrator.unregister());

const approval = {id: 'approval-1', workflow_id: 'workflow-1', revision: 3, arguments_hash: 'sha256:exact',
  quote_ref: 'quote-1', summary: 'Cho phép gửi lời mời nhận việc cho nhân viên.', expires_at: '2099-01-01T00:00:00Z'};
const item: WorkforceTracking = {ticket_id: 'ticket-1', workflow_id: 'workflow-1', state: 'awaiting_approval', attention: null,
  snapshot: {workflows: [{workflow_id: 'workflow-1', revision: 5, state: 'awaiting_approval'}], pending_approvals: [approval]}};

test('resident consents to the displayed operation and cannot submit it again while awaiting sync', async () => {
  const decide = vi.fn().mockResolvedValue(true);
  const view = render(<WorkforceStatus item={item} busy={false} onDecide={decide} onClose={vi.fn()} />);
  expect(view.getByText(approval.summary)).toBeTruthy();
  fireEvent.click(view.getByText('Đồng ý thao tác này'));
  await waitFor(() => expect(decide).toHaveBeenCalledWith(approval, 'approve'));
  await waitFor(() => expect((view.getByText('Đồng ý thao tác này') as HTMLButtonElement).disabled).toBe(true));
  expect(view.getByRole('status').textContent).toContain('Đã gửi quyết định');
});

test('stopping tracking explains business work continues and needs a separate resident action', async () => {
  const close = vi.fn().mockResolvedValue(true);
  const view = render(<WorkforceStatus item={item} busy={false} onDecide={vi.fn()} onClose={close} />);
  fireEvent.click(view.getByText('Dừng theo dõi hỗ trợ'));
  expect(close).not.toHaveBeenCalled();
  expect(view.getByText(/Công việc và phản ánh tại Ban quản lý vẫn được giữ nguyên/)).toBeTruthy();
  fireEvent.click(view.getByText('Xác nhận dừng theo dõi'));
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1));
});

test('expired consent cannot authorize an operation', () => {
  const view = render(<WorkforceStatus item={{...item, snapshot: {pending_approvals: [{...approval, expires_at: '2000-01-01T00:00:00Z'}]}}}
    busy={false} onDecide={vi.fn()} onClose={vi.fn()} />);
  expect((view.getByText('Đồng ý thao tác này') as HTMLButtonElement).disabled).toBe(true);
  expect((view.getByText('Từ chối') as HTMLButtonElement).disabled).toBe(true);
});
