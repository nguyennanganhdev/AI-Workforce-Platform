import { createFileRoute } from '@tanstack/react-router';
import { IncidentsWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/incidents')({
  component: IncidentsWorkspace,
});
