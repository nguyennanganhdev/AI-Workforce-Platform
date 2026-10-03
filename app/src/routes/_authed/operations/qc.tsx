import { createFileRoute } from '@tanstack/react-router';
import { QcWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/qc')({
  component: () => (
    <OperationsRouteGuard menuId="qc">
      <QcWorkspace />
    </OperationsRouteGuard>
  ),
});
