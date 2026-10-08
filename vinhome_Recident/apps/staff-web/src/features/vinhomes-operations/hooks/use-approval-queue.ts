import { useMemo } from 'react';
import { useOperationsData } from './use-operations-data';
import type { VhActionApproval } from '../types/action';

export function useApprovalQueue() {
  const { approvals, executionGrants, approveAction, rejectAction } = useOperationsData();

  const pendingApprovals = useMemo(
    () => approvals.filter((a: VhActionApproval) => a.status === 'PENDING'),
    [approvals],
  );

  const decidedApprovals = useMemo(
    () => approvals.filter((a: VhActionApproval) => a.status !== 'PENDING'),
    [approvals],
  );

  const totalPendingCost = useMemo(() => {
    return pendingApprovals.reduce((acc: number, curr: VhActionApproval) => acc + (curr.estimated_cost_vnd || 0), 0);
  }, [pendingApprovals]);

  const criticalCount = useMemo(() => {
    return pendingApprovals.filter((a: VhActionApproval) => a.urgency_level === 'CRITICAL').length;
  }, [pendingApprovals]);

  return {
    approvals,
    executionGrants,
    pendingApprovals,
    decidedApprovals,
    totalPendingCost,
    criticalCount,
    approveAction,
    rejectAction,
  };
}
