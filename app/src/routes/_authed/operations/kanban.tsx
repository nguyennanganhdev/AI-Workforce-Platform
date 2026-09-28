import { createFileRoute } from '@tanstack/react-router';
import { KanbanBoard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/kanban')({
  component: KanbanBoard,
});
