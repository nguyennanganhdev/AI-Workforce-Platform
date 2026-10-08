import { createFileRoute } from '@tanstack/react-router';
import { SecurityWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/security')({
  component: () => (
    <OperationsRouteGuard menuId="security">
      <SecurityWorkspace />
    </OperationsRouteGuard>
  ),
});
