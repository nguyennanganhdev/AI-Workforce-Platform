import { describe, expect, test } from 'bun:test';
import {
  ALLOWED_WORK_ORDER_TRANSITIONS,
  type WorkOrderStatus,
} from '../src/features/vinhomes-operations/types/work-order';
import {
  PERSONA_PROFILES,
  type OperationsPersona,
} from '../src/features/vinhomes-operations/types/persona';

describe('Vinhomes Operations State Machine (ALLOWED_WORK_ORDER_TRANSITIONS)', () => {
  test('OPEN can only transition to ASSIGNED or CANCELLED', () => {
    const allowed = ALLOWED_WORK_ORDER_TRANSITIONS['OPEN'];
    expect(allowed).toContain('ASSIGNED');
    expect(allowed).toContain('CANCELLED');
    expect(allowed).not.toContain('IN_PROGRESS');
    expect(allowed).not.toContain('COMPLETED');
  });

  test('ASSIGNED can only transition to IN_PROGRESS or CANCELLED', () => {
    const allowed = ALLOWED_WORK_ORDER_TRANSITIONS['ASSIGNED'];
    expect(allowed).toContain('IN_PROGRESS');
    expect(allowed).toContain('CANCELLED');
    expect(allowed).not.toContain('COMPLETED');
    expect(allowed).not.toContain('OPEN');
  });

  test('IN_PROGRESS can transition to BLOCKED, COMPLETED, or FAILED', () => {
    const allowed = ALLOWED_WORK_ORDER_TRANSITIONS['IN_PROGRESS'];
    expect(allowed).toContain('BLOCKED');
    expect(allowed).toContain('COMPLETED');
    expect(allowed).toContain('FAILED');
    expect(allowed).not.toContain('OPEN');
    expect(allowed).not.toContain('ASSIGNED');
  });

  test('BLOCKED can resume to IN_PROGRESS or be CANCELLED', () => {
    const allowed = ALLOWED_WORK_ORDER_TRANSITIONS['BLOCKED'];
    expect(allowed).toContain('IN_PROGRESS');
    expect(allowed).toContain('CANCELLED');
    expect(allowed).not.toContain('COMPLETED');
  });

  test('COMPLETED, FAILED, CANCELLED are terminal states', () => {
    expect(ALLOWED_WORK_ORDER_TRANSITIONS['COMPLETED']).toEqual([]);
    expect(ALLOWED_WORK_ORDER_TRANSITIONS['FAILED']).toEqual([]);
    expect(ALLOWED_WORK_ORDER_TRANSITIONS['CANCELLED']).toEqual([]);
  });

  test('Rejects invalid transitions helper function', () => {
    const isValidTransition = (from: WorkOrderStatus, to: WorkOrderStatus): boolean => {
      const allowed = ALLOWED_WORK_ORDER_TRANSITIONS[from];
      return Boolean(allowed && allowed.includes(to));
    };

    expect(isValidTransition('OPEN', 'ASSIGNED')).toBe(true);
    expect(isValidTransition('OPEN', 'IN_PROGRESS')).toBe(false);
    expect(isValidTransition('OPEN', 'COMPLETED')).toBe(false);
    expect(isValidTransition('ASSIGNED', 'IN_PROGRESS')).toBe(true);
    expect(isValidTransition('ASSIGNED', 'COMPLETED')).toBe(false);
    expect(isValidTransition('IN_PROGRESS', 'COMPLETED')).toBe(true);
    expect(isValidTransition('COMPLETED', 'IN_PROGRESS')).toBe(false);
    expect(isValidTransition('CANCELLED', 'ASSIGNED')).toBe(false);
  });
});

describe('Vinhomes Operations RBAC & Persona Capability Matrix', () => {
  test('Strict Segregation of Duties: Manager does NOT have canQC permission', () => {
    const manager = PERSONA_PROFILES['MANAGER'];
    expect(manager.canQC).toBe(false);
    expect(manager.canApproveBudget).toBe(true);
    expect(manager.canAssignWork).toBe(true);
  });

  test('QC_INSPECTOR is the ONLY persona with canQC permission', () => {
    const qcInspector = PERSONA_PROFILES['QC_INSPECTOR'];
    expect(qcInspector.canQC).toBe(true);
    expect(qcInspector.canApproveBudget).toBe(false);
    expect(qcInspector.canAssignWork).toBe(false);

    // Verify all other 6 personas CANNOT sign QC
    const nonQcPersonas: OperationsPersona[] = [
      'STAFF_TECHNICAL',
      'STAFF_SANITATION_A5',
      'STAFF_SECURITY',
      'CONTRACTOR',
      'SUPERVISOR',
      'MANAGER',
    ];

    for (const p of nonQcPersonas) {
      expect(PERSONA_PROFILES[p].canQC).toBe(false);
    }
  });

  test('Budget approval is strictly restricted to MANAGER', () => {
    const manager = PERSONA_PROFILES['MANAGER'];
    expect(manager.canApproveBudget).toBe(true);

    const nonBudgetApprovers: OperationsPersona[] = [
      'STAFF_TECHNICAL',
      'STAFF_SANITATION_A5',
      'STAFF_SECURITY',
      'CONTRACTOR',
      'SUPERVISOR',
      'QC_INSPECTOR',
    ];

    for (const p of nonBudgetApprovers) {
      expect(PERSONA_PROFILES[p].canApproveBudget).toBe(false);
    }
  });

  test('Work assignment is restricted to SUPERVISOR and MANAGER', () => {
    expect(PERSONA_PROFILES['SUPERVISOR'].canAssignWork).toBe(true);
    expect(PERSONA_PROFILES['MANAGER'].canAssignWork).toBe(true);

    expect(PERSONA_PROFILES['STAFF_TECHNICAL'].canAssignWork).toBe(false);
    expect(PERSONA_PROFILES['STAFF_SANITATION_A5'].canAssignWork).toBe(false);
    expect(PERSONA_PROFILES['STAFF_SECURITY'].canAssignWork).toBe(false);
    expect(PERSONA_PROFILES['CONTRACTOR'].canAssignWork).toBe(false);
    expect(PERSONA_PROFILES['QC_INSPECTOR'].canAssignWork).toBe(false);
  });

  test('Contractor has dedicated organization ID', () => {
    const contractor = PERSONA_PROFILES['CONTRACTOR'];
    expect(contractor.contractor_organization_id).toBe('org-otis');
    expect(contractor.role).toBe('CONTRACTOR');
  });

  test('Menu routing RBAC: Field workers do not have access to QC, Approvals, or Triage, and evidence gallery is removed for all', () => {
    const tech = PERSONA_PROFILES['STAFF_TECHNICAL'];
    expect(tech.allowedMenuIds).toContain('my-tasks');
    expect(tech.allowedMenuIds).toContain('work-orders');
    expect(tech.allowedMenuIds).not.toContain('evidence');
    expect(tech.allowedMenuIds).not.toContain('qc');
    expect(tech.allowedMenuIds).not.toContain('approvals');
    expect(tech.allowedMenuIds).not.toContain('triage');

    const clean = PERSONA_PROFILES['STAFF_SANITATION_A5'];
    expect(clean.allowedMenuIds).toContain('my-tasks');
    expect(clean.allowedMenuIds).toContain('completed-tasks');
    // The A5 execution flow is opened from a concrete item in "My tasks";
    // the standalone sanitation route is reserved for Supervisor/Manager oversight.
    expect(clean.allowedMenuIds).not.toContain('sanitation');
    expect(clean.allowedMenuIds).not.toContain('qc');
    expect(clean.allowedMenuIds).not.toContain('approvals');

    // Evidence gallery menu is completely removed for all personas
    for (const profile of Object.values(PERSONA_PROFILES)) {
      expect(profile.allowedMenuIds).not.toContain('evidence');
    }
  });
});

describe('Evidence & QC Business Logic Rules', () => {
  test('Evidence requirement verification helper before COMPLETED', () => {
    const hasRequiredEvidence = (
      evidenceList: Array<{ work_order_id: string; capture_phase: string }>,
      workOrderId: string,
    ): boolean => {
      const woEvidence = evidenceList.filter((e) => e.work_order_id === workOrderId);
      const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
      const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');
      return hasBefore && hasAfter;
    };

    const emptyEv: any[] = [];
    expect(hasRequiredEvidence(emptyEv, 'WO-001')).toBe(false);

    const onlyBefore = [{ work_order_id: 'WO-001', capture_phase: 'BEFORE' }];
    expect(hasRequiredEvidence(onlyBefore, 'WO-001')).toBe(false);

    const onlyAfter = [{ work_order_id: 'WO-001', capture_phase: 'AFTER' }];
    expect(hasRequiredEvidence(onlyAfter, 'WO-001')).toBe(false);

    const both = [
      { work_order_id: 'WO-001', capture_phase: 'BEFORE' },
      { work_order_id: 'WO-001', capture_phase: 'AFTER' },
    ];
    expect(hasRequiredEvidence(both, 'WO-001')).toBe(true);
  });

  test('QC Immutability: Block duplicate final QC for same WorkOrder', () => {
    const existingQcResults = [
      { id: 'QC-001', work_order_id: 'WO-101', outcome: 'PASS' },
      { id: 'QC-002', work_order_id: 'WO-102', outcome: 'FAIL' },
      { id: 'QC-003', work_order_id: 'WO-103', outcome: 'INCONCLUSIVE' },
    ];

    const canSubmitQc = (workOrderId: string): boolean => {
      const finalResult = existingQcResults.find(
        (q) => q.work_order_id === workOrderId && q.outcome !== 'INCONCLUSIVE',
      );
      return !finalResult;
    };

    // WO-101 has PASS -> final, immutable
    expect(canSubmitQc('WO-101')).toBe(false);
    // WO-102 has FAIL -> final, immutable
    expect(canSubmitQc('WO-102')).toBe(false);
    // WO-103 has INCONCLUSIVE -> allowed to submit follow-up QC
    expect(canSubmitQc('WO-103')).toBe(true);
    // WO-104 has no QC yet -> allowed
    expect(canSubmitQc('WO-104')).toBe(true);
  });
});
