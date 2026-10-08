import { createFileRoute } from '@tanstack/react-router';
import { OperationsLayout } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations')({
  component: OperationsLayout,
});
