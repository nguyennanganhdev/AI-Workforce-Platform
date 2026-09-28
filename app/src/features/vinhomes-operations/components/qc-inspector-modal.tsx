import { useState } from 'react';
import {
  IconX,
  IconShieldCheck,
  IconCheck,
  IconAlertTriangle,
  IconArrowBackUp,
  IconInfoCircle,
} from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import type { VhChecklistCriterion } from '../types/qc';
import { useQcWorkflow } from '../hooks/use-qc-workflow';

interface QcInspectorModalProps {
  workOrder: VhWorkOrder;
  onClose: () => void;
}

export function QcInspectorModal({ workOrder, onClose }: QcInspectorModalProps) {
  const { checklistVersion, existingQcResult, submitQcInspection } = useQcWorkflow(workOrder.id);

  // Criteria checkbox states
  const [criteriaState, setCriteriaState] = useState<Record<string, { passed: boolean; note: string }>>(() => {
    const initial: Record<string, { passed: boolean; note: string }> = {};
    checklistVersion?.criteria_json.forEach((c: VhChecklistCriterion) => {
      initial[c.id] = { passed: true, note: '' };
    });
    return initial;
  });

  const [overallOutcome, setOverallOutcome] = useState<'PASS' | 'FAIL' | 'INCONCLUSIVE'>('PASS');
  const [qcNote, setQcNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [resultSuccess, setResultSuccess] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const toggleCriterion = (id: string, passed: boolean) => {
    setCriteriaState((prev) => {
      const updated = { ...prev, [id]: { ...prev[id], passed } };
      // If any required criterion is false, default overallOutcome to FAIL
      const hasFailed = Object.values(updated).some((val) => !val.passed);
      if (hasFailed) {
        setOverallOutcome('FAIL');
      } else {
        setOverallOutcome('PASS');
      }
      return updated;
    });
  };

  const handleCriterionNote = (id: string, note: string) => {
    setCriteriaState((prev) => ({
      ...prev,
      [id]: { ...prev[id], note },
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    try {
      const formattedCriteria = Object.entries(criteriaState).map(([criterionId, val]) => {
        const meta = checklistVersion?.criteria_json.find((c: VhChecklistCriterion) => c.id === criterionId);
        return {
          criterion_id: criterionId,
          label: meta?.label || criterionId,
          passed: val.passed,
          note: val.note,
        };
      });

      const res = submitQcInspection({
        workOrderId: workOrder.id,
        outcome: overallOutcome,
        criteria: formattedCriteria,
        note: qcNote || (overallOutcome === 'PASS' ? 'Nghiệm thu đạt chuẩn' : overallOutcome === 'INCONCLUSIVE' ? 'Chưa đủ cơ sở kết luận' : 'Chưa đạt tiêu chuẩn kỹ thuật'),
        checkedBy: 'usr-qc-01',
        checkedByName: 'Lê Hoàng Nam (Kỹ sư Kiểm định Độc lập)',
      });

      setSubmitting(false);
      if (res?.redoWorkOrder) {
        setResultSuccess(
          `Đã ghi nhận QC FAIL. Tự động kích hoạt phiếu làm lại (Redo): ${res.redoWorkOrder.id} (Lần ${res.redoWorkOrder.attempt_no})!`,
        );
      } else if (overallOutcome === 'INCONCLUSIVE') {
        setResultSuccess('Đã ghi nhận kết quả INCONCLUSIVE: Yêu cầu bổ sung kiểm định!');
      } else {
        setResultSuccess('Đã ghi nhận nghiệm thu QC PASS thành công!');
      }

      setTimeout(() => {
        onClose();
      }, 1800);
    } catch (err: any) {
      setSubmitting(false);
      setErrorMessage(err.message || 'Không thể lưu kết quả kiểm định');
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 font-sans">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[92vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-6 bg-purple-600 rounded-full" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-base">Kiểm Định Chất Lượng (QC Inspector)</h3>
                <span className="font-mono text-xs px-2 py-0.5 bg-purple-50 text-purple-700 font-bold rounded">
                  {workOrder.id}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Checklist: <span className="font-semibold text-slate-700">{checklistVersion?.id}</span> •
                Phiên bản #{checklistVersion?.version_no}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <IconX className="w-5 h-5" />
          </button>
        </div>

        {/* Success Alert Banner */}
        {resultSuccess && (
          <div className="m-5 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold flex items-center gap-2">
            <IconCheck className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>{resultSuccess}</span>
          </div>
        )}

        {/* Error Alert Banner */}
        {errorMessage && (
          <div className="m-5 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold flex items-center gap-2">
            <IconAlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Existing Inspection Badge */}
        {existingQcResult && !resultSuccess && (
          <div className="m-5 p-4 rounded-xl bg-purple-50 border border-purple-200 flex items-start gap-3 text-xs">
            <IconInfoCircle className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-purple-900">
                Phiếu này đã có kết quả kiểm định: {existingQcResult.outcome}
              </p>
              <p className="text-purple-700 mt-0.5">
                Người duyệt: {existingQcResult.checked_by_name} lúc{' '}
                {new Date(existingQcResult.checked_at).toLocaleTimeString('vi-VN')}
              </p>
              {existingQcResult.note && (
                <p className="text-purple-800 italic mt-1">"{existingQcResult.note}"</p>
              )}
            </div>
          </div>
        )}

        {/* Checklist Criteria Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6 text-xs text-slate-700">
          <div className="space-y-3">
            <span className="font-extrabold uppercase tracking-wider text-slate-400 text-[11px] block">
              Danh mục tiêu chí kiểm tra bắt buộc
            </span>

            <div className="space-y-2.5">
              {checklistVersion?.criteria_json.map((criterion: VhChecklistCriterion) => {
                const state = criteriaState[criterion.id] || { passed: true, note: '' };
                return (
                  <div
                    key={criterion.id}
                    className={`p-3.5 rounded-xl border transition-colors ${
                      state.passed
                        ? 'bg-slate-50/70 border-slate-200'
                        : 'bg-rose-50/60 border-rose-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[10px] text-slate-400 font-bold">
                            {criterion.code}
                          </span>
                          {criterion.required && (
                            <span className="text-[10px] text-rose-500 font-semibold">*Bắt buộc</span>
                          )}
                        </div>
                        <p className="font-bold text-slate-900 text-xs leading-relaxed">
                          {criterion.label}
                        </p>
                      </div>

                      {/* Pass / Fail Toggle */}
                      <div className="flex items-center gap-1.5 shrink-0 bg-white p-1 rounded-lg border border-slate-200">
                        <button
                          type="button"
                          onClick={() => toggleCriterion(criterion.id, true)}
                          className={`px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
                            state.passed
                              ? 'bg-emerald-600 text-white'
                              : 'text-slate-500 hover:bg-slate-100'
                          }`}
                        >
                          Đạt
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleCriterion(criterion.id, false)}
                          className={`px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
                            !state.passed
                              ? 'bg-rose-600 text-white'
                              : 'text-slate-500 hover:bg-slate-100'
                          }`}
                        >
                          Không đạt
                        </button>
                      </div>
                    </div>

                    {!state.passed && (
                      <div className="mt-2.5 pt-2 border-t border-rose-100">
                        <input
                          type="text"
                          placeholder="Ghi rõ lý do không đạt tiêu chuẩn này..."
                          value={state.note}
                          onChange={(e) => handleCriterionNote(criterion.id, e.target.value)}
                          className="w-full p-2 bg-white border border-rose-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-rose-500 text-rose-900 font-medium placeholder-rose-300"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Overall Decision Section */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <span className="font-bold text-slate-800 block text-xs">
              Quyết định kết quả tổng thể:
            </span>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              <label
                className={`p-3 rounded-xl border flex items-center gap-2.5 cursor-pointer transition-colors ${
                  overallOutcome === 'PASS'
                    ? 'border-emerald-500 bg-emerald-50/60 text-emerald-900 font-bold ring-1 ring-emerald-500'
                    : 'border-slate-200 bg-white text-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="outcome"
                  checked={overallOutcome === 'PASS'}
                  onChange={() => setOverallOutcome('PASS')}
                  className="w-4 h-4 text-emerald-600 focus:ring-emerald-500"
                />
                <div>
                  <div className="text-xs font-extrabold flex items-center gap-1 text-emerald-700">
                    <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>QC PASS (Đạt)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-normal mt-0.5">
                    Đạt chuẩn, hoàn tất Task.
                  </p>
                </div>
              </label>

              <label
                className={`p-3 rounded-xl border flex items-center gap-2.5 cursor-pointer transition-colors ${
                  overallOutcome === 'FAIL'
                    ? 'border-rose-500 bg-rose-50/60 text-rose-900 font-bold ring-1 ring-rose-500'
                    : 'border-slate-200 bg-white text-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="outcome"
                  checked={overallOutcome === 'FAIL'}
                  onChange={() => setOverallOutcome('FAIL')}
                  className="w-4 h-4 text-rose-600 focus:ring-rose-500"
                />
                <div>
                  <div className="text-xs font-extrabold flex items-center gap-1 text-rose-700">
                    <IconAlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                    <span>QC FAIL (Làm lại)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-normal mt-0.5">
                    Tạo phiếu Redo kế thừa.
                  </p>
                </div>
              </label>

              <label
                className={`p-3 rounded-xl border flex items-center gap-2.5 cursor-pointer transition-colors ${
                  overallOutcome === 'INCONCLUSIVE'
                    ? 'border-amber-500 bg-amber-50/60 text-amber-900 font-bold ring-1 ring-amber-500'
                    : 'border-slate-200 bg-white text-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="outcome"
                  checked={overallOutcome === 'INCONCLUSIVE'}
                  onChange={() => setOverallOutcome('INCONCLUSIVE')}
                  className="w-4 h-4 text-amber-600 focus:ring-amber-500"
                />
                <div>
                  <div className="text-xs font-extrabold flex items-center gap-1 text-amber-700">
                    <IconInfoCircle className="w-3.5 h-3.5 text-amber-600" />
                    <span>INCONCLUSIVE</span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-normal mt-0.5">
                    Yêu cầu bổ sung tài liệu.
                  </p>
                </div>
              </label>
            </div>

            {/* Note */}
            <div>
              <label className="text-[11px] font-semibold text-slate-600 block mb-1">
                Ghi chú nghiệm thu của Kỹ sư QC:
              </label>
              <textarea
                rows={2}
                value={qcNote}
                onChange={(e) => setQcNote(e.target.value)}
                placeholder="Nhập nhận xét tổng thể về chất lượng thi công..."
                className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
              />
            </div>
          </div>

          {/* Footer Submit */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-semibold"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={submitting}
              className={`px-5 py-2 text-white rounded-xl text-xs font-bold transition-all shadow-sm ${
                overallOutcome === 'PASS'
                  ? 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/20'
                  : 'bg-rose-600 hover:bg-rose-700 shadow-rose-500/20'
              }`}
            >
              {submitting ? 'Đang lưu kết quả...' : 'Xác nhận kết quả QC'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
