import { createFileRoute } from '@tanstack/react-router';

// The connected layout draws this page itself, for an administrator (the management units).
export const Route = createFileRoute('/_authed/operations/units')({});
