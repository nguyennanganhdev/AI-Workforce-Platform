import { Navigate, createFileRoute } from '@tanstack/react-router';

// "Tiếp nhận phản ánh" đã gộp vào "Phản ánh & Sự cố" (tab "Cần BQL xử lý")
export const Route = createFileRoute('/_authed/operations/triage')({
  component: () => <Navigate to="/operations/incidents" replace />,
});
