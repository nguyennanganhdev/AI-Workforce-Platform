import { createFileRoute } from '@tanstack/react-router';
import { KanbanBoard, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/kanban')({
  component: () => (
    <OperationsRouteGuard menuId="kanban">
      <KanbanBoard />
    </OperationsRouteGuard>
  ),
});
