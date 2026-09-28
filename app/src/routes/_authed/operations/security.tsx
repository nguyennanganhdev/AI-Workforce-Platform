import { createFileRoute } from '@tanstack/react-router';
import { SecurityWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/security')({
  component: SecurityWorkspace,
});
