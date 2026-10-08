import { createFileRoute } from '@tanstack/react-router';
import { ApprovalQueue, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/approvals')({
  component: () => (
    <OperationsRouteGuard menuId="approvals">
      <ApprovalQueue />
    </OperationsRouteGuard>
  ),
});
