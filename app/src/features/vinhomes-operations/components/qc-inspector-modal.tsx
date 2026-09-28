import { useState, useEffect } from 'react';
import {
  IconX,
  IconShieldCheck,
  IconCheck,
  IconAlertTriangle,
  IconArrowBackUp,
  IconInfoCircle,
  IconLock,
} from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import type { VhChecklistCriterion } from '../types/qc';
import { useQcWorkflow } from '../hooks/use-qc-workflow';
import { useOperationsData } from '../hooks/use-operations-data';

interface QcInspectorModalProps {
  workOrder: VhWorkOrder;
  onClose: () => void;
}

export function QcInspectorModal({ workOrder, onClose }: QcInspectorModalProps) {
  const { checklistVersion, existingQcResult, submitQcInspection } = useQcWorkflow(workOrder.id);
  const { currentProfile, currentPersona } = useOperationsData();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Segregation of Duties Check: Only users with canQC can sign QC results (Manager does not bypass)
  const isSelfExecutor = Boolean(workOrder.executor_id && workOrder.executor_id === currentProfile.id);
  const hasQcPermission = Boolean(currentProfile.canQC);
  const isAlreadyFinalized = Boolean(existingQcResult && existingQcResult.outcome !== 'INCONCLUSIVE');

  // Criteria checkbox states
  const [criteriaState, setCriteriaState] = useState<Record<string, { passed: boolean; note: string }>>(() => {
    const initial: Record<string, { passed: boolean; note: string }> = {};
    checklistVersion?.criteria_json.forEach((c: VhChecklistCriterion) => {
      // If already inspected, match existing failure list
      const isFailedInOld = existingQcResult?.failed_criteria.includes(c.label);
      initial[c.id] = { passed: !isFailedInOld, note: '' };
    });
    return initial;
  });

  const [overallOutcome, setOverallOutcome] = useState<'PASS' | 'FAIL' | 'INCONCLUSIVE'>(
    existingQcResult ? existingQcResult.outcome : 'PASS',
  );
  const [qcNote, setQcNote] = useState(existingQcResult?.note || '');
  const [submitting, setSubmitting] = useState(false);
  const [resultSuccess, setResultSuccess] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const toggleCriterion = (id: string, passed: boolean) => {
    if (isAlreadyFinalized || isSelfExecutor || !hasQcPermission) return;
    setCriteriaState((prev) => {
      const updated = { ...prev, [id]: { ...prev[id], passed } };
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
    if (isAlreadyFinalized || isSelfExecutor || !hasQcPermission) return;
    setCriteriaState((prev) => ({
      ...prev,
      [id]: { ...prev[id], note },
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSelfExecutor) {
      setErrorMessage('Vi phạm nguyên tắc độc lập kiểm định: Người thi công không được phép tự nghiệm thu!');
      return;
    }
    if (!hasQcPermission) {
      setErrorMessage(`Vai trò "${currentProfile.roleTitle}" không có quyền ký ban hành kết quả QC.`);
      return;
    }

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
        checkedBy: currentProfile.id,
        checkedByName: currentProfile.name,
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
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="qc-modal-title"
      className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 font-sans"
    >
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[92vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-6 bg-purple-600 rounded-full" />
            <div>
              <div className="flex items-center gap-2">
                <h3 id="qc-modal-title" className="font-bold text-slate-900 text-base">Biên Bản Nghiệm Thu Chất Lượng (QC)</h3>
                <span className="font-mono text-xs px-2 py-0.5 bg-purple-50 text-purple-700 font-bold rounded">
                  {workOrder.id}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Checklist: <strong>{checklistVersion?.name || checklistVersion?.id || 'Tiêu chuẩn kiểm định'}</strong> (Phiên bản #{checklistVersion?.version_no || 1})
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng cửa sổ nghiệm thu"
            className="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <IconX className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Identity & Guard Warnings */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-slate-500">Người thực hiện thi công:</span>{' '}
              <strong className="text-slate-800">{workOrder.executor_name || workOrder.executor_id || 'Kỹ thuật'}</strong>
            </div>
            <div>
              <span className="text-slate-500">Người kiểm tra hiện tại:</span>{' '}
              <strong className="text-purple-700">{currentProfile.name}</strong> ({currentProfile.roleTitle})
            </div>
          </div>

          {/* GUARD WARNING: Self-QC prohibited */}
          {isSelfExecutor && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2.5">
              <IconAlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block font-bold">Vi phạm nguyên tắc độc lập kiểm định (Segregation of Duties):</strong>
                <span>Bạn là người trực tiếp thi công phiếu này. Theo quy chế của Ban Quản Lý, người thi công <strong>không được phép tự chấm nghiệm thu QC</strong> công việc của chính mình! Vui lòng chuyển sang vai trò QC Inspector hoặc nhờ Trưởng ca nghiệm thu.</span>
              </div>
            </div>
          )}

          {/* GUARD WARNING: No QC Permission */}
          {!hasQcPermission && !isSelfExecutor && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center gap-2">
              <IconInfoCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>Vai trò <strong>{currentProfile.roleTitle}</strong> chỉ có quyền xem lại, không có thẩm quyền ký ban hành kết quả QC.</span>
            </div>
          )}

          {/* GUARD WARNING: Already Inspected & Immutable */}
          {isAlreadyFinalized && (
            <div className="p-3.5 bg-purple-50 border border-purple-200 rounded-xl text-xs text-purple-900 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconLock className="w-4 h-4 text-purple-600 shrink-0" />
                <span>Biên bản nghiệm thu này đã được ký ban hành bởi <strong>{existingQcResult?.checked_by_name || existingQcResult?.checked_by}</strong> và được lưu trữ bất biến.</span>
              </div>
              <span className="font-bold text-xs px-2 py-0.5 bg-purple-200 rounded">
                Kết quả: {existingQcResult?.outcome}
              </span>
            </div>
          )}

          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
              <IconAlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {resultSuccess && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center gap-2">
              <IconCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{resultSuccess}</span>
            </div>
          )}

          {/* Criteria Checklist */}
          <div className="space-y-3">
            <h4 className="font-bold text-xs text-slate-800 uppercase tracking-wider">
              1. Đánh giá từng tiêu chuẩn bắt buộc:
            </h4>

            <div className="space-y-2.5">
              {checklistVersion?.criteria_json.map((c: VhChecklistCriterion) => {
                const state = criteriaState[c.id] || { passed: true, note: '' };
                const disabled = isAlreadyFinalized || isSelfExecutor || !hasQcPermission;

                return (
                  <div
                    key={c.id}
                    className={`p-3.5 rounded-xl border transition-all ${
                      state.passed
                        ? 'border-slate-200 bg-white'
                        : 'border-rose-300 bg-rose-50/40 ring-1 ring-rose-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-slate-900">{c.label}</span>
                          {c.required && (
                            <span className="text-[10px] font-bold text-rose-600 bg-rose-50 px-1.5 py-0.2 rounded">
                              Bắt buộc
                            </span>
                          )}
                        </div>
                        {c.description && <p className="text-[11px] text-slate-500 mt-0.5">{c.description}</p>}
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => toggleCriterion(c.id, true)}
                          className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                            state.passed
                              ? 'bg-emerald-600 text-white shadow-2xs'
                              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                          } ${disabled ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                          ✓ Đạt
                        </button>
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => toggleCriterion(c.id, false)}
                          className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                            !state.passed
                              ? 'bg-rose-600 text-white shadow-2xs'
                              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                          } ${disabled ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                          ✕ Chưa đạt
                        </button>
                      </div>
                    </div>

                    {!state.passed && (
                      <div className="mt-2.5 pt-2 border-t border-rose-200">
                        <input
                          type="text"
                          disabled={disabled}
                          placeholder="Ghi rõ thông số chưa đạt hoặc lý do..."
                          value={state.note}
                          onChange={(e) => handleCriterionNote(c.id, e.target.value)}
                          className="w-full p-2 bg-white border border-rose-300 rounded-lg text-xs text-rose-900 focus:outline-none"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Outcome Radio Options */}
          <div className="space-y-2">
            <h4 className="font-bold text-xs text-slate-800 uppercase tracking-wider">
              2. Kết luận nghiệm thu tổng thể:
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                {
                  id: 'PASS',
                  label: 'PASS (Đạt chất lượng)',
                  desc: 'Đủ điều kiện đóng nhiệm vụ thi công',
                  activeBorder: 'border-emerald-500 bg-emerald-50/60',
                },
                {
                  id: 'FAIL',
                  label: 'FAIL (Không đạt)',
                  desc: 'Tự động tạo phiếu làm lại (Redo)',
                  activeBorder: 'border-rose-500 bg-rose-50/60',
                },
                {
                  id: 'INCONCLUSIVE',
                  label: 'INCONCLUSIVE (Kiểm tra lại)',
                  desc: 'Yêu cầu đo đạc bổ sung thêm',
                  activeBorder: 'border-amber-500 bg-amber-50/60',
                },
              ].map((opt) => (
                <div
                  key={opt.id}
                  onClick={() => {
                    if (!isAlreadyFinalized && !isSelfExecutor && hasQcPermission) {
                      setOverallOutcome(opt.id as any);
                    }
                  }}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    overallOutcome === opt.id
                      ? opt.activeBorder + ' shadow-2xs'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  } ${isAlreadyFinalized || isSelfExecutor || !hasQcPermission ? 'cursor-not-allowed opacity-80' : ''}`}
                >
                  <div className="font-bold text-xs text-slate-900">{opt.label}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{opt.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Inspection Note */}
          <div className="space-y-1.5">
            <label className="font-bold text-xs text-slate-800">Ghi chú & kết luận của người nghiệm thu:</label>
            <textarea
              rows={2}
              disabled={isAlreadyFinalized || isSelfExecutor || !hasQcPermission}
              value={qcNote}
              onChange={(e) => setQcNote(e.target.value)}
              placeholder="VD: Đã kiểm tra áp suất nước đạt 3.8 bar, co nối siết chuẩn, không rỉ..."
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-purple-500"
            />
          </div>

          {/* Footer Controls */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
            >
              Đóng
            </button>

            {!isAlreadyFinalized && (
              <button
                type="submit"
                disabled={submitting || isSelfExecutor || !hasQcPermission}
                className={`px-5 py-2.5 rounded-xl text-xs font-bold text-white shadow-2xs transition-all flex items-center gap-1.5 ${
                  overallOutcome === 'PASS'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : overallOutcome === 'FAIL'
                      ? 'bg-rose-600 hover:bg-rose-700'
                      : 'bg-amber-600 hover:bg-amber-700'
                } ${isSelfExecutor || !hasQcPermission ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {overallOutcome === 'FAIL' ? (
                  <>
                    <IconArrowBackUp className="w-4 h-4" />
                    <span>Xác nhận FAIL & Tạo phiếu làm lại (Redo)</span>
                  </>
                ) : (
                  <>
                    <IconShieldCheck className="w-4 h-4" />
                    <span>Ký biên bản nghiệm thu ({overallOutcome})</span>
                  </>
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
