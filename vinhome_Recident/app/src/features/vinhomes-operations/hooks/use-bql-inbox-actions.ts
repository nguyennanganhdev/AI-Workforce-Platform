/**
 * BQL actions for the "Cần BQL xử lý" inbox (docs mục 14 và 16).
 * Called inside useOperationsDataInternal so state stays in the single operations store.
 */
import { useCallback, type Dispatch, type SetStateAction } from 'react';
import type { VhIncident } from '../types/incident';
import type { UserProfile } from '../types/persona';

interface Deps {
  incidents: VhIncident[];
  setIncidents: Dispatch<SetStateAction<VhIncident[]>>;
  currentProfile: UserProfile;
}

export function useBqlInboxActions({ incidents, setIncidents, currentProfile }: Deps) {
  const assertBql = useCallback(() => {
    if (!currentProfile.canApproveBudget) throw new Error('Chỉ Ban Quản Lý mới được thực hiện thao tác này.');
  }, [currentProfile]);

  const update = useCallback(
    (incidentId: string, patch: (i: VhIncident) => Partial<VhIncident>) => {
      const now = new Date().toISOString();
      setIncidents((prev) => prev.map((i) => (i.id === incidentId ? { ...i, ...patch(i), version: i.version + 1, updated_at: now } : i)));
    },
    [setIncidents],
  );

  /** BQL đã liên hệ nhà thầu (ngoài hệ thống) → AI báo cư dân "đã có đơn vị xử lý, dự kiến …". */
  const markContractorContacted = useCallback(
    (incidentId: string, contractorName: string, eta: string) => {
      assertBql();
      const inc = incidents.find((i) => i.id === incidentId);
      const handoff = inc?.contractor_handoff;
      if (!handoff) throw new Error('Sự cố này không cần nhà thầu.');
      if (handoff.status !== 'PENDING') throw new Error('Đã ghi nhận liên hệ nhà thầu trước đó.');
      if (!contractorName.trim()) throw new Error('Nhập tên nhà thầu.');
      if (!eta) throw new Error('Chọn ngày hẹn dự kiến.');
      const now = new Date().toISOString();
      update(incidentId, () => ({
        stage: 'EXECUTION',
        contractor_handoff: { ...handoff, status: 'CONTACTED', contractor_name: contractorName.trim(), eta, contacted_at: now },
      }));
    },
    [assertBql, incidents, update],
  );

  /** Nhà thầu đã khắc phục xong → AI báo cư dân và đóng ticket. */
  const markContractorResolved = useCallback(
    (incidentId: string, note: string) => {
      assertBql();
      const inc = incidents.find((i) => i.id === incidentId);
      const handoff = inc?.contractor_handoff;
      if (handoff?.status !== 'CONTACTED') throw new Error('Cần ghi nhận "Đã liên hệ nhà thầu" trước.');
      const now = new Date().toISOString();
      update(incidentId, () => ({
        status: 'CLOSED',
        stage: 'RESIDENT_CONFIRMATION',
        resolved_at: now,
        closed_at: now,
        contractor_handoff: { ...handoff, status: 'RESOLVED', resolved_at: now, note: note.trim() || null },
      }));
    },
    [assertBql, incidents, update],
  );

  /**
   * BQL tự xử lý một ngoại lệ (cư dân tranh chấp phát sinh, hộ không hợp tác…) rồi đóng sự cố.
   * Đây là quyết định của BQL nên không áp điều kiện đóng thông thường, nhưng bắt buộc ghi chú.
   */
  const closeWithBqlResolution = useCallback(
    (incidentId: string, note: string) => {
      assertBql();
      if (!note.trim()) throw new Error('Ghi rõ cách BQL đã xử lý.');
      const now = new Date().toISOString();
      update(incidentId, () => ({
        status: 'CLOSED',
        stage: 'RESIDENT_CONFIRMATION',
        resolved_at: now,
        closed_at: now,
        bql_resolution_note: note.trim(),
      }));
    },
    [assertBql, update],
  );

  return { markContractorContacted, markContractorResolved, closeWithBqlResolution };
}
