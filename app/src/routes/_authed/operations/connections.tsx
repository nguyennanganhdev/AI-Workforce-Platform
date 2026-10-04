import { createFileRoute } from '@tanstack/react-router';
import { TeamPage } from '@/features/vinhomes-operations/workspace/TeamPage';
// The connected layout draws this page itself, for an administrator; the preview workspace shows its team room.
export const Route = createFileRoute('/_authed/operations/connections')({ component: TeamPage });
