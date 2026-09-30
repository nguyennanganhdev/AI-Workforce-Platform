import { useState } from 'react';
import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router';
import { OperationsLayout } from '@/features/vinhomes-operations';
import { endSession, getSession } from '@/features/vinhomes-portal/auth/session';

// Staff open the operations app in the role of the account they signed in with.
function OperationsRoot() {
  const navigate = useNavigate();
  const [session] = useState(getSession);
  const signOut = () => {
    endSession();
    navigate({ to: '/vinhomes/login' });
  };
  return <OperationsLayout persona={session?.persona} onSignOut={signOut} />;
}

export const Route = createFileRoute('/_authed/operations')({
  beforeLoad: () => {
    if (getSession()?.role !== 'STAFF') throw redirect({ to: '/vinhomes/login', search: { for: 'staff' } });
  },
  component: OperationsRoot,
});
