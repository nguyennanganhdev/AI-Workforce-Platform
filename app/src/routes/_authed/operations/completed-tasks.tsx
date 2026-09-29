import { createFileRoute } from '@tanstack/react-router';
import { CompletedTasksWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/completed-tasks')({
  component: () => (
    <OperationsRouteGuard menuId="completed-tasks">
      <CompletedTasksWorkspace />
    </OperationsRouteGuard>
  ),
});
