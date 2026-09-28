import { createFileRoute } from '@tanstack/react-router';
import { WorkOrderTable } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/work-orders')({
  component: WorkOrderTable,
});
