import { createFileRoute } from '@tanstack/react-router';
import { IncidentsWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/incidents')({
  component: () => (
    <OperationsRouteGuard menuId="incidents">
      <IncidentsWorkspace />
    </OperationsRouteGuard>
  ),
});
