import { createFileRoute } from '@tanstack/react-router';
import { LoginPage } from '@/features/vinhomes-portal';

function LoginRoute() {
  const search = Route.useSearch();
  return <LoginPage requiredRole={search.for} />;
}

export const Route = createFileRoute('/vinhomes/login')({
  // `for`: which app sent the visitor here, so the page can say which account to use.
  validateSearch: (search: Record<string, unknown>): { for?: 'resident' | 'staff' } =>
    search.for === 'resident' || search.for === 'staff' ? { for: search.for } : {},
  component: LoginRoute,
});
