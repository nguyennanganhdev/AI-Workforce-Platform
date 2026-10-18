import { useMemo, useState } from 'react';
import {
  IconBuilding,
  IconCheck,
  IconEye,
  IconHistory,
  IconPhoto,
  IconSearch,
  IconShieldCheck,
  IconX,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { EvidenceModal } from './evidence-modal';
import { WorkOrderDialog } from './work-order-dialog';

type HistoryFilter = 'ALL' | 'WAITING_QC' | 'PASS' | 'FAIL';

export function CompletedTasksWorkspace() {
  const { myWorkOrders, tasks, incidents, evidence, qcResults, currentProfile } = useOperationsData();
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState<HistoryFilter>('ALL');
  const [selectedWorkOrder, setSelectedWorkOrder] = useState<VhWorkOrder | null>(null);
  const [evidenceWorkOrder, setEvidenceWorkOrder] = useState<VhWorkOrder | null>(null);

  const completedRows = useMemo(() => {
    return myWorkOrders
      .filter((workOrder) => workOrder.status === 'COMPLETED')
      .map((workOrder) => {
        const task = tasks.find((item) => item.id === workOrder.task_id);
        const incident = incidents.find((item) => item.id === workOrder.incident_id);
        const qcResult = qcResults.find((item) => item.work_order_id === workOrder.id);
        const relatedEvidence = evidence.filter((item) => item.work_order_id === workOrder.id);
        return {
          workOrder,
          task,
          incident,
          qcResult,
          beforeCount: relatedEvidence.filter((item) => item.capture_phase === 'BEFORE').length,
          afterCount: relatedEvidence.filter((item) => item.capture_phase === 'AFTER').length,
        };
      })
      .sort((a, b) =>
        (b.workOrder.execution_completed_at || b.workOrder.updated_at).localeCompare(
          a.workOrder.execution_completed_at || a.workOrder.updated_at,
        ),
      );
  }, [myWorkOrders, tasks, incidents, qcResults, evidence]);

  const counts = {
    ALL: completedRows.length,
    WAITING_QC: completedRows.filter((row) => !row.qcResult).length,
    PASS: completedRows.filter((row) => row.qcResult?.outcome === 'PASS').length,
    FAIL: completedRows.filter((row) => row.qcResult?.outcome === 'FAIL').length,
  };

  const filteredRows = completedRows.filter((row) => {
    const query = searchTerm.trim().toLowerCase();
    const matchesSearch =
      !query ||
      row.workOrder.id.toLowerCase().includes(query) ||
      (row.task?.title || '').toLowerCase().includes(query) ||
      (row.incident?.location_json.towerCode || '').toLowerCase().includes(query);
    const matchesFilter =
      activeFilter === 'ALL' ||
      (activeFilter === 'WAITING_QC' && !row.qcResult) ||
      row.qcResult?.outcome === activeFilter;
    return matchesSearch && matchesFilter;
  });

  const formatCompletedAt = (workOrder: VhWorkOrder) => {
    const value = workOrder.execution_completed_at || workOrder.updated_at;
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  };

  return (
    <div className="operations-worker-view operations-plain-list operations-work-orders space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">

          <div className="min-w-0">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight text-balance">
              Công việc đã hoàn thành
            </h1>
            <p className="text-xs text-slate-500 text-pretty">
              Lịch sử hồ sơ đã nộp của {currentProfile.name}, gồm ảnh hiện trường và kết quả nghiệm thu.
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-bold">
          <IconHistory className="w-4 h-4" aria-hidden="true" />
          {completedRows.length} hồ sơ
        </span>
      </div>

      <div className="bg-white overflow-hidden">
        <div className="p-3 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <label className="flex flex-col gap-1 text-xs text-slate-500">Kết quả nghiệm thu
            <select value={activeFilter} onChange={(event) => setActiveFilter(event.target.value as HistoryFilter)} className="rounded border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="ALL">Tất cả kết quả</option><option value="WAITING_QC">Chờ nghiệm thu</option><option value="PASS">Đạt yêu cầu</option><option value="FAIL">Không đạt yêu cầu</option>
            </select>
          </label>
          <label className="relative block w-full lg:w-72">
            <span className="sr-only">Tìm công việc đã hoàn thành</span>
            <IconSearch className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <input
              name="completed-task-search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Tìm mã phiếu, công việc, tòa nhà…"
              autoComplete="off"
              className="w-full pl-9 pr-9 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus:bg-white"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                aria-label="Xóa nội dung tìm kiếm"
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 rounded focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <IconX className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            )}
          </label>
        </div>

        {/* Mobile Card View (< 768px): KHÔNG CẦN VUỐT NGANG */}
        <div className="md:hidden divide-y divide-slate-100 bg-white">
          {filteredRows.map(({ workOrder, task, incident, qcResult, beforeCount, afterCount }) => {
            const qcBadge = (
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                  qcResult?.outcome === 'PASS'
                    ? 'bg-emerald-100 text-emerald-700'
                    : qcResult?.outcome === 'FAIL'
                      ? 'bg-rose-100 text-rose-700'
                      : 'bg-amber-100 text-amber-800'
                }`}
              >
                {qcResult?.outcome === 'PASS' ? (
                  <IconCheck className="w-3 h-3" aria-hidden="true" />
                ) : (
                  <IconShieldCheck className="w-3 h-3" aria-hidden="true" />
                )}
                {qcResult?.outcome === 'PASS'
                  ? 'Đạt'
                  : qcResult?.outcome === 'FAIL'
                    ? 'Không đạt'
                    : 'Chờ nghiệm thu'}
              </span>
            );

            return (
              <div key={workOrder.id} className="p-3.5 space-y-2.5 bg-white">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => setSelectedWorkOrder(workOrder)}
                      className="font-bold text-xs text-slate-900 hover:text-blue-700 text-left line-clamp-2"
                    >
                      {task?.title || 'Công việc vệ sinh A5'}
                    </button>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1 text-[11px] text-slate-400">
                      <span className="font-mono font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                        {workOrder.id}
                      </span>
                      <span>•</span>
                      <span>Lần {workOrder.attempt_no}</span>
                      <span>•</span>
                      <span>Tòa {incident?.location_json.towerCode || '—'} · Tầng {incident?.location_json.floor || '—'}</span>
                    </div>
                  </div>
                  <div className="shrink-0">{qcBadge}</div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 bg-slate-50/70 rounded-lg px-2.5 py-1.5">
                  <div>
                    <span className="text-slate-400">Hoàn thành: </span>
                    <span className="font-medium text-slate-700">{formatCompletedAt(workOrder)}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEvidenceWorkOrder(workOrder)}
                    className="inline-flex items-center gap-1 text-emerald-700 font-bold hover:underline"
                  >
                    <IconPhoto className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>{beforeCount} trước · {afterCount} sau</span>
                  </button>
                </div>

                <div className="flex items-center justify-end pt-1 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setSelectedWorkOrder(workOrder)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold"
                  >
                    <IconEye className="w-3.5 h-3.5" aria-hidden="true" />
                    Xem hồ sơ
                  </button>
                </div>
              </div>
            );
          })}
          {filteredRows.length === 0 && (
            <div className="px-6 py-14 text-center">
              <IconHistory className="w-8 h-8 text-slate-300 mx-auto" aria-hidden="true" />
              <p className="font-bold text-slate-700 mt-2 text-xs">Chưa có hồ sơ phù hợp</p>
              <p className="text-slate-400 mt-1 text-[11px]">Thử thay đổi bộ lọc hoặc nội dung tìm kiếm.</p>
            </div>
          )}
        </div>

        {/* Desktop Table View (>= 768px) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/80 border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 min-w-[300px]">Công việc</th>
                <th className="px-4 py-3 min-w-[150px] ops-hide-mobile">Vị trí</th>
                <th className="px-4 py-3 min-w-[155px] ops-hide-mobile">Hoàn thành lúc</th>
                <th className="px-4 py-3 min-w-[135px] ops-hide-mobile">Bằng chứng</th>
                <th className="px-4 py-3 min-w-[130px]">Kết quả nghiệm thu</th>
                <th className="px-5 py-3 text-right min-w-[175px]">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRows.map(({ workOrder, task, incident, qcResult, beforeCount, afterCount }) => (
                <tr key={workOrder.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-5 py-4">
                    <button
                      type="button"
                      onClick={() => setSelectedWorkOrder(workOrder)}
                      className="font-bold text-slate-900 hover:text-blue-700 text-left focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                    >
                      {task?.title || 'Công việc vệ sinh A5'}
                    </button>
                    <p className="mt-1 text-[11px] text-slate-400 font-mono">
                      {workOrder.id} • Lần {workOrder.attempt_no}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-slate-600 ops-hide-mobile">
                    <span className="flex items-center gap-1.5 font-medium">
                      <IconBuilding className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                      Tòa {incident?.location_json.towerCode || '—'} • Tầng {incident?.location_json.floor || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-slate-600 tabular-nums ops-hide-mobile">{formatCompletedAt(workOrder)}</td>
                  <td className="px-4 py-4 ops-hide-mobile">
                    <button
                      type="button"
                      onClick={() => setEvidenceWorkOrder(workOrder)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 rounded-lg text-[11px] font-bold focus-visible:ring-2 focus-visible:ring-emerald-500"
                    >
                      <IconPhoto className="w-3.5 h-3.5" aria-hidden="true" />
                      Trước xử lý: {beforeCount} ảnh · Sau xử lý: {afterCount} ảnh
                    </button>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold ${
                      qcResult?.outcome === 'PASS'
                        ? 'bg-emerald-100 text-emerald-700'
                        : qcResult?.outcome === 'FAIL'
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-amber-100 text-amber-800'
                    }`}>
                      {qcResult?.outcome === 'PASS' ? (
                        <IconCheck className="w-3.5 h-3.5" aria-hidden="true" />
                      ) : (
                        <IconShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                      )}
                      {qcResult?.outcome === 'PASS'
                        ? 'Đạt'
                        : qcResult?.outcome === 'FAIL'
                          ? 'Không đạt'
                          : 'Chờ nghiệm thu'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <button
                      type="button"
                      onClick={() => setSelectedWorkOrder(workOrder)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold focus-visible:ring-2 focus-visible:ring-blue-500"
                    >
                      <IconEye className="w-3.5 h-3.5" aria-hidden="true" />
                      Xem hồ sơ
                    </button>
                  </td>
                </tr>
              ))}
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-14 text-center">
                    <IconHistory className="w-8 h-8 text-slate-300 mx-auto" aria-hidden="true" />
                    <p className="font-bold text-slate-700 mt-2">Chưa có hồ sơ phù hợp</p>
                    <p className="text-slate-400 mt-1">Thử thay đổi bộ lọc hoặc nội dung tìm kiếm.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedWorkOrder && (
        <WorkOrderDialog
          workOrder={selectedWorkOrder}
          canEdit={false}
          onClose={() => setSelectedWorkOrder(null)}
        />
      )}

      {evidenceWorkOrder && (
        <EvidenceModal
          workOrder={evidenceWorkOrder}
          readOnly
          onClose={() => setEvidenceWorkOrder(null)}
        />
      )}
    </div>
  );
}
