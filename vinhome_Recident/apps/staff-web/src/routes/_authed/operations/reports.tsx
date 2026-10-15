import { createFileRoute } from '@tanstack/react-router';
import { ReportsPage } from '@/features/vinhomes-operations/workspace/ReportsPage';
export const Route = createFileRoute('/_authed/operations/reports')({ component: ReportsPage });
