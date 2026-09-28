import { createFileRoute } from '@tanstack/react-router';
import { TriageWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/triage')({
  component: TriageWorkspace,
});
