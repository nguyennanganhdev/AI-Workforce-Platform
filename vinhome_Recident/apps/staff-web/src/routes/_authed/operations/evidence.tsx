import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/_authed/operations/evidence')({
  component: () => <Navigate to="/operations/my-tasks" replace />,
});
