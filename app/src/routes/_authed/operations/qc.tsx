import { createFileRoute } from '@tanstack/react-router';
import { QcWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/qc')({
  component: QcWorkspace,
});
