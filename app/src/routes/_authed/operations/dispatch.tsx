import { createFileRoute } from '@tanstack/react-router';
import { DispatchPage } from '@/features/vinhomes-operations/workspace/DispatchPage';
export const Route = createFileRoute('/_authed/operations/dispatch')({ component: DispatchPage });
