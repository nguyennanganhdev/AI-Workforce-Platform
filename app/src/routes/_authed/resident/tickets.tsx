import { createFileRoute } from '@tanstack/react-router';
import { TicketsPage } from '@/features/vinhomes-resident';

export const Route = createFileRoute('/_authed/resident/tickets')({
  component: TicketsPage,
});
