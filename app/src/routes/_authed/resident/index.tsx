import { createFileRoute } from '@tanstack/react-router';
import { NewChat } from '@/features/vinhomes-resident';

export const Route = createFileRoute('/_authed/resident/')({
  component: NewChat,
});
