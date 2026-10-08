import { createFileRoute } from '@tanstack/react-router';
import { AccountsPage } from '@/features/vinhomes-operations/workspace/AccountsPage';
export const Route = createFileRoute('/_authed/operations/accounts')({ component: AccountsPage });
