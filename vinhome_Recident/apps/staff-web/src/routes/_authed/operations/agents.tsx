import { createFileRoute } from '@tanstack/react-router';
import { TeamPage } from '@/features/vinhomes-operations/workspace/TeamPage';
// The connected layout draws this page itself; the preview workspace has no agent screen and shows its team room.
export const Route = createFileRoute('/_authed/operations/agents')({ component: TeamPage });
