import { createFileRoute } from '@tanstack/react-router';
import { EvidenceGallery, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/evidence')({
  component: () => (
    <OperationsRouteGuard menuId="evidence">
      <EvidenceGallery />
    </OperationsRouteGuard>
  ),
});
