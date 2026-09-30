import { useState } from 'react';
import { Outlet, createFileRoute, redirect, useNavigate } from '@tanstack/react-router';
import { OperationsProvider } from '@/features/vinhomes-operations/hooks/use-operations-data';
import { endSession, getSession, residentProfileOf } from '@/features/vinhomes-portal/auth/session';
import { ResidentGatewayProvider, ResidentLayout } from '@/features/vinhomes-resident';

/*
 * The resident app reads tickets from the same operations store as the staff app (bản trải nghiệm,
 * synced across tabs through localStorage). When the resident API exists, only the gateway changes.
 */
function ResidentRoot() {
  const navigate = useNavigate();
  const [profile] = useState(() => {
    const session = getSession();
    return session ? residentProfileOf(session) : null;
  });
  if (!profile) return null;
  const signOut = () => {
    endSession();
    navigate({ to: '/vinhomes/login' });
  };
  return (
    <OperationsProvider>
      <ResidentGatewayProvider profile={profile}>
        <ResidentLayout onSignOut={signOut}>
          <Outlet />
        </ResidentLayout>
      </ResidentGatewayProvider>
    </OperationsProvider>
  );
}

export const Route = createFileRoute('/_authed/resident')({
  beforeLoad: () => {
    if (getSession()?.role !== 'RESIDENT') throw redirect({ to: '/vinhomes/login', search: { for: 'resident' } });
  },
  component: ResidentRoot,
});
