import { createFileRoute } from '@tanstack/react-router';
import { TriageWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/triage')({
  component: () => (
    <OperationsRouteGuard menuId="triage">
      <TriageWorkspace />
    </OperationsRouteGuard>
  ),
});
