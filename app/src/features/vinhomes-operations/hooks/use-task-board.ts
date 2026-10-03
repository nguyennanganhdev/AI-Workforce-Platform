import { useMemo, useCallback } from 'react';
import { useOperationsData } from './use-operations-data';
import type { VhTask, TaskStatus } from '../types/task';

export interface TaskBoardColumn {
  id: TaskStatus;
  label: string;
  color: string;
  badgeBg: string;
  tasks: VhTask[];
}

export const TASK_COLUMNS: Array<{ id: TaskStatus; label: string; color: string; badgeBg: string }> = [
  { id: 'OPEN', label: 'Chờ giao việc', color: 'text-slate-600', badgeBg: 'bg-slate-100' },
  { id: 'ASSIGNED', label: 'Đã phân công', color: 'text-blue-600', badgeBg: 'bg-blue-100' },
  { id: 'IN_PROGRESS', label: 'Đang thực hiện', color: 'text-amber-600', badgeBg: 'bg-amber-100' },
  { id: 'BLOCKED', label: 'Bị chặn / Chờ duyệt', color: 'text-rose-600', badgeBg: 'bg-rose-100' },
  { id: 'DONE', label: 'Hoàn tất / Đã QC', color: 'text-emerald-600', badgeBg: 'bg-emerald-100' },
];

export function useTaskBoard(filterDomain?: string) {
  const { tasks, incidents, workOrders, updateWorkOrderStatus } = useOperationsData();

  const columns: TaskBoardColumn[] = useMemo(() => {
    const filteredTasks = filterDomain
      ? tasks.filter((t) => t.domain_type === filterDomain)
      : tasks;

    return TASK_COLUMNS.map((col) => ({
      ...col,
      tasks: filteredTasks.filter((t) => t.status === col.id),
    }));
  }, [tasks, filterDomain]);

  const moveTask = useCallback(
    (taskId: string, targetStatus: TaskStatus) => {
      // Find related work order to synchronize status
      const relatedWo = workOrders.find((w) => w.task_id === taskId);
      if (relatedWo) {
        if (targetStatus === 'IN_PROGRESS') {
          updateWorkOrderStatus(relatedWo.id, 'IN_PROGRESS');
        } else if (targetStatus === 'DONE') {
          updateWorkOrderStatus(relatedWo.id, 'COMPLETED');
        }
      }
    },
    [workOrders, updateWorkOrderStatus],
  );

  return {
    columns,
    tasks,
    incidents,
    moveTask,
  };
}
