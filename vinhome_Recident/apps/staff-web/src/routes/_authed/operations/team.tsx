import { createFileRoute } from '@tanstack/react-router';
import { TeamPage } from '@/features/vinhomes-operations/workspace/TeamPage';
export const Route = createFileRoute('/_authed/operations/team')({ component: TeamPage });
