import { createFileRoute } from '@tanstack/react-router';
import { SanitationWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/sanitation')({
  component: SanitationWorkspace,
});
