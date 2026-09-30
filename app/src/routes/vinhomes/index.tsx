import { createFileRoute } from '@tanstack/react-router';
import { LandingPage } from '@/features/vinhomes-portal';

export const Route = createFileRoute('/vinhomes/')({
  component: LandingPage,
});
