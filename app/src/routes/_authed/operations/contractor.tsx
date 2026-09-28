import { createFileRoute } from '@tanstack/react-router';
import { ContractorWorkspace } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/contractor')({
  component: ContractorWorkspace,
});
