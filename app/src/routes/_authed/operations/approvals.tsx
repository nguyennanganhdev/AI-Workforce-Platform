import { createFileRoute } from '@tanstack/react-router';
import { ApprovalQueue } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/approvals')({
  component: ApprovalQueue,
});
