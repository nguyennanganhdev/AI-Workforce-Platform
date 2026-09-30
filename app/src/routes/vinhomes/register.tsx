import { createFileRoute } from '@tanstack/react-router';
import { RegisterPage } from '@/features/vinhomes-portal';

export const Route = createFileRoute('/vinhomes/register')({
  component: RegisterPage,
});
