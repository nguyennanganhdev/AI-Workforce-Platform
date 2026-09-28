import { createFileRoute } from '@tanstack/react-router';
import { MyTasksWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/my-tasks')({
  component: MyTasksWorkspace,
});
