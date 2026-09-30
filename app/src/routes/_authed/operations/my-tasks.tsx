import { Navigate, createFileRoute } from '@tanstack/react-router';
import { MyTasksWorkspace, TechnicianWorkspace, useOperationsData } from '@/features/vinhomes-operations';

function MyTasksRoute() {
  const { currentPersona, canAccessMenu } = useOperationsData();
  // Ban quản lý không nhận việc hiện trường: đưa về trang Tổng quan
  if (!canAccessMenu('my-tasks')) return <Navigate to="/operations" replace />;
  const usesFieldFlow =
    currentPersona === 'STAFF_TECHNICAL' || currentPersona === 'STAFF_SANITATION_A5' || currentPersona === 'STAFF_SECURITY';
  return usesFieldFlow ? <TechnicianWorkspace /> : <MyTasksWorkspace />;
}

export const Route = createFileRoute('/_authed/operations/my-tasks')({
  validateSearch: (search: Record<string, unknown>): { job?: string } =>
    typeof search.job === 'string' && search.job ? { job: search.job } : {},
  component: MyTasksRoute,
});
