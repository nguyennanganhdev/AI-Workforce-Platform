import { createFileRoute } from '@tanstack/react-router';

// The connected layout draws this page itself, for an administrator (the audit trail).
export const Route = createFileRoute('/_authed/operations/audit')({});
