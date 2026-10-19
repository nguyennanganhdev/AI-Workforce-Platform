import { createFileRoute } from '@tanstack/react-router';
import { ContractorWorkspace, OperationsRouteGuard } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/contractor')({
  component: () => (
    <OperationsRouteGuard menuId="contractor">
      <ContractorWorkspace />
    </OperationsRouteGuard>
  ),
});
