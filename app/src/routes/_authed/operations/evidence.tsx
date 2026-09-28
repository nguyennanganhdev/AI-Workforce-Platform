import { createFileRoute } from '@tanstack/react-router';
import { EvidenceGallery } from '@/features/vinhomes-operations';

export const Route = createFileRoute('/_authed/operations/evidence')({
  component: EvidenceGallery,
});
