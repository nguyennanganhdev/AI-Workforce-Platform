import { createFileRoute } from '@tanstack/react-router';
import { OperationsDashboard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/')({
  component: OperationsDashboard,
});
