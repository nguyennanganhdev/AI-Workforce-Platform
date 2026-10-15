import { createFileRoute } from '@tanstack/react-router';
import { WorkOrderTable, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/work-orders')({
  component: () => (
    <OperationsRouteGuard menuId="work-orders">
      <WorkOrderTable />
    </OperationsRouteGuard>
  ),
});
