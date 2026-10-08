import { createFileRoute } from '@tanstack/react-router';
import { OperationsDashboard, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/')({
  component: () => (
    <OperationsRouteGuard menuId="dashboard">
      <OperationsDashboard />
    </OperationsRouteGuard>
  ),
});
