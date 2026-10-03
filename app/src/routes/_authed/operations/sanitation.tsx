import { createFileRoute } from '@tanstack/react-router';
import { SanitationWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/sanitation')({
  component: () => (
    <OperationsRouteGuard menuId="sanitation">
      <SanitationWorkspace />
    </OperationsRouteGuard>
  ),
});
