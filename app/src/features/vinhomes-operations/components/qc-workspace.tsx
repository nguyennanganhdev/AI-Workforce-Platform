import { useState } from 'react';
import {
  IconShieldCheck,
  IconClipboardCheck,
  IconPhoto,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { QcInspectorModal } from './qc-inspector-modal';

export function QcWorkspace() {
  const { qcResults, workOrders, evidence } = useOperationsData();
  const [selectedWoForQc, setSelectedWoForQc] = useState<VhWorkOrder | null>(null);

  const eligibleWos = workOrders.filter((w) => w.status === 'COMPLETED');
  const inProgressWos = workOrders.filter((w) => w.status === 'IN_PROGRESS');

  return (
    <div className="space-y-5 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Nghiệm Thu Chất Lượng Công Việc
            </h1>
            <p className="text-xs text-slate-500">
              Kiểm tra checklist tiêu chuẩn sau khi kỹ thuật viên báo cáo hoàn thành
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-purple-50 text-purple-700 font-semibold text-xs rounded-full border border-purple-200">
            {qcResults.length} Biên bản nghiệm thu
          </span>
        </div>
      </div>

      {/* Phiếu đã hoàn tất chờ nghiệm thu */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <IconClipboardCheck className="w-4 h-4 text-purple-600" />
            <h3 className="font-bold text-xs text-slate-900">
              Phiếu thi công đã hoàn thành — Chờ nghiệm thu ({eligibleWos.length})
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">Nhấn nút để đánh giá tiêu chuẩn</span>
        </div>

        {eligibleWos.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl">
            Hiện tại không có phiếu nào đang chờ nghiệm thu.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {eligibleWos.map((wo) => {
              const hasQc = qcResults.some((q) => q.work_order_id === wo.id);
              const woEvidence = evidence.filter((e) => e.work_order_id === wo.id);
              const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
              const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');
              const evidenceReady = hasBefore && hasAfter;

              return (
                <div
                  key={wo.id}
                  className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white hover:border-purple-300 transition-all space-y-2.5 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-blue-600">{wo.id}</span>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                        Đã xong thi công
                      </span>
                    </div>

                    <p className="font-bold text-xs text-slate-900 mt-1 line-clamp-1">
                      {wo.result?.note ? String(wo.result.note) : `Phiếu thi công ${wo.id}`}
                    </p>

                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Thực hiện: <strong>{wo.executor_name || 'Kỹ thuật viên'}</strong> • Lần #{wo.attempt_no}
                    </p>

                    {/* Evidence Check indicator */}
                    <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500 flex items-center gap-1">
                        <IconPhoto className="w-3.5 h-3.5 text-slate-400" />
                        Ảnh hiện trường:
                      </span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                          evidenceReady
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {evidenceReady ? '✓ Đủ ảnh Trước / Sau' : 'Thiếu ảnh Trước / Sau'}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 flex items-center justify-between border-t border-slate-200/60">
                    <span className="text-[10px] text-slate-400">
                      {wo.checklist_version_id || 'Mặc định'}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedWoForQc(wo)}
                      className="px-3 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-bold transition-colors shadow-2xs"
                    >
                      {hasQc ? 'Xem lại' : 'Nghiệm thu ngay'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {inProgressWos.length > 0 && (
        <div className="bg-slate-50 rounded-2xl border border-slate-200 p-4 space-y-1.5">
          <div className="text-xs font-bold text-slate-700">
            Phiếu đang thực hiện ({inProgressWos.length})
          </div>
          <p className="text-[11px] text-slate-500">
            Kỹ thuật viên cần nhấn "Hoàn thành" trên phiếu thi công trước khi tiến hành nghiệm thu chất lượng.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {inProgressWos.map((wo) => (
              <span
                key={wo.id}
                className="px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs font-mono text-slate-600"
              >
                {wo.id} ({wo.executor_name || 'Đang làm'})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Lịch sử nghiệm thu */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
          <IconShieldCheck className="w-4 h-4 text-emerald-600" />
          <h3 className="font-bold text-xs text-slate-900">
            Lịch sử kết quả nghiệm thu gần đây
          </h3>
        </div>

        <div className="space-y-2.5">
          {qcResults.map((qc) => (
            <div
              key={qc.id}
              className={`p-3.5 rounded-xl border transition-colors ${
                qc.outcome === 'PASS'
                  ? 'border-emerald-200 bg-emerald-50/40'
                  : qc.outcome === 'INCONCLUSIVE'
                    ? 'border-amber-200 bg-amber-50/40'
                    : 'border-rose-200 bg-rose-50/40'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-slate-800">{qc.id}</span>
                  <span className="text-slate-400">•</span>
                  <span className="text-xs text-slate-600">
                    Phiếu thi công: <strong className="font-mono text-slate-900">{qc.work_order_id}</strong>
                  </span>
                </div>

                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-bold flex items-center gap-1 ${
                    qc.outcome === 'PASS'
                      ? 'bg-emerald-600 text-white'
                      : qc.outcome === 'INCONCLUSIVE'
                        ? 'bg-amber-500 text-white'
                        : 'bg-rose-600 text-white'
                  }`}
                >
                  {qc.outcome === 'PASS' && '✓ Đạt tiêu chuẩn'}
                  {qc.outcome === 'FAIL' && '✕ Không đạt (Làm lại)'}
                  {qc.outcome === 'INCONCLUSIVE' && '⚠ Cần kiểm tra thêm'}
                </span>
              </div>

              {qc.note && <p className="text-xs text-slate-700 italic mb-1.5">"{qc.note}"</p>}

              {qc.failed_criteria.length > 0 && (
                <div className="p-2 rounded-lg bg-rose-100/70 border border-rose-200 text-rose-800 text-[11px] font-medium space-y-0.5">
                  <p className="font-bold">Tiêu chí chưa đạt:</p>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {qc.failed_criteria.map((fc: string, idx: number) => (
                      <li key={idx}>{fc}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="pt-1.5 mt-1.5 border-t border-slate-200/60 flex items-center justify-between text-[11px] text-slate-400">
                <span>Người nghiệm thu: <strong className="text-slate-700">{qc.checked_by_name || qc.checked_by}</strong></span>
                <span>{new Date(qc.checked_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedWoForQc && (
        <QcInspectorModal
          workOrder={selectedWoForQc}
          onClose={() => setSelectedWoForQc(null)}
        />
      )}
    </div>
  );
}
