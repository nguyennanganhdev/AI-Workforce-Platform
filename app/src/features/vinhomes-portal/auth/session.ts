/**
 * Portal session, one per browser tab (sessionStorage): a resident and a staff member can be signed
 * in side by side in two tabs, which is how the demo shows the two apps talking to each other.
 */
import type { ResidentProfile } from '@/features/vinhomes-resident/types';
import { DEMO_RESIDENT } from '@/features/vinhomes-resident/mock/profile';
import type { PortalAccount } from './accounts';

const SESSION_KEY = 'vhm_portal_v1_session';

export interface PortalSession extends PortalAccount {
  signedInAt: string;
}

export function getSession(): PortalSession | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? 'null');
    if (!value || typeof value !== 'object') return null;
    const s = value as PortalSession;
    return (s.role === 'RESIDENT' || s.role === 'STAFF') && typeof s.id === 'string' ? s : null;
  } catch {
    return null;
  }
}

export function startSession(account: PortalAccount): PortalSession {
  const session: PortalSession = { ...account, signedInAt: new Date().toISOString() };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function endSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

/** Resident profile the resident app works with, from the signed-in account. */
export function residentProfileOf(session: PortalSession): ResidentProfile {
  const tower = session.towerCode ?? DEMO_RESIDENT.towerCode;
  const apartment = session.apartmentCode ?? DEMO_RESIDENT.apartmentCode;
  const phone = session.phone.replace(/^(\d{4})(\d{3})(\d{3})$/, '$1 $2 $3');
  return {
    userId: session.id,
    name: session.name,
    phone,
    projectName: DEMO_RESIDENT.projectName,
    towerCode: tower,
    floor: Number.parseInt(apartment.slice(0, -2), 10) || 1,
    apartmentCode: apartment,
    apartmentLabel: `${tower} · ${apartment}`,
  };
}
