import { useState } from 'react';
import { OperationsTable } from './operations-table';
import {
  IconInbox,
  IconSparkles,
  IconCut,
  IconGitMerge,
  IconHelpCircle,
  IconCheck,
  IconAlertTriangle,
  IconBuilding,
  IconPhone,
  IconUser,
  IconClock,
  IconArrowRight,
  IconX,
  IconHeadset,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhIssueCandidate, VhResidentRequest } from '../types/intake';
import { MOCK_RESIDENT_REQUESTS } from '../mock/intake';

export function TriageWorkspace() {
  const {
    cases,
    issueCandidates,
    materializeCandidate,
    splitIssueCandidate,
    mergeIssueCandidates,
  } = useOperationsData();

  const [selectedCaseId, setSelectedCaseId] = useState<string>('');

  // Split Modal State
  const [splitCandidate, setSplitCandidate] = useState<VhIssueCandidate | null>(null);
  const [splitPartA, setSplitPartA] = useState({ domain: 'ELEVATOR', summary: '' });
  const [splitPartB, setSplitPartB] = useState({ domain: 'MEP', summary: '' });

  // Merge Modal State
  const [mergeSource, setMergeSource] = useState<VhIssueCandidate | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState<string>('');

  // Notification State
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const selectedCase = cases.find((c) => c.id === selectedCaseId);
  const caseRequests = MOCK_RESIDENT_REQUESTS.filter((r: VhResidentRequest) => r.case_id === selectedCase?.id);
  const caseCandidates = issueCandidates.filter((ic) => ic.case_id === selectedCase?.id);

  const handleMaterialize = (candidateId: string) => {
    const inc = materializeCandidate(candidateId);
    if (inc) {
      setActionSuccessMsg(`Đã tạo sự cố xử lý ${inc.id} thành công!`);
      setTimeout(() => setActionSuccessMsg(null), 3500);
    }
  };

  const handleOpenSplit = (candidate: VhIssueCandidate) => {
    setSplitCandidate(candidate);
    setSplitPartA({ domain: candidate.domain, summary: `${candidate.normalized_summary} (Phần 1: Kỹ thuật)` });
    setSplitPartB({ domain: 'MEP', summary: `${candidate.normalized_summary} (Phần 2: Điện chiếu sáng)` });
  };

  const handleConfirmSplit = () => {
    if (!splitCandidate) return;
    splitIssueCandidate(
      splitCandidate.id,
      { domain: splitPartA.domain, summary: splitPartA.summary },
      { domain: splitPartB.domain, summary: splitPartB.summary }
    );
    setSplitCandidate(null);
    setActionSuccessMsg(`Đã tách thành 2 vấn đề riêng biệt để giao cho 2 bộ phận.`);
    setTimeout(() => setActionSuccessMsg(null), 3500);
  };

  const handleConfirmMerge = () => {
    if (!mergeSource || !mergeTargetId) return;
    mergeIssueCandidates(mergeSource.id, mergeTargetId);
    setMergeSource(null);
    setActionSuccessMsg(`Đã gộp phản ánh trùng lặp thành công.`);
    setTimeout(() => setActionSuccessMsg(null), 3500);
  };

  return (
    <div className="space-y-5 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Tiếp nhận phản ánh
            </h1>
            <p className="text-xs text-slate-500">
              Xem xét ý kiến cư dân gửi đến, xác nhận đề xuất xử lý từ AI và chuyển giao cho các bộ phận
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-semibold text-xs rounded-full border border-blue-200">
            {cases.length} Yêu cầu đang mở
          </span>
        </div>
      </div>

      {actionSuccessMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{actionSuccessMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccessMsg(null)}
            className="text-emerald-500 hover:text-emerald-700 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      <div hidden={Boolean(selectedCaseId)}>
        <OperationsTable title="Phản ánh của cư dân" columns={['Mã phản ánh', 'Nội dung', 'Cư dân', 'Căn hộ', 'Trạng thái', 'Ngày tiếp nhận']}
          rows={cases.map((item) => ({ id: item.id, search: `${item.id} ${item.summary} ${item.resident_name} ${item.apartment_id || ''}`, cells: [
            item.id, item.summary, item.resident_name, item.apartment_id || 'Chưa xác định',
            ({OPEN: 'Mới tiếp nhận', CLARIFYING: 'Đang làm rõ', READY: 'Sẵn sàng xử lý', TICKETED: 'Đã tạo sự cố', CLOSED: 'Đã đóng', CANCELLED: 'Đã hủy'})[item.status],
            new Date(item.opened_at).toLocaleDateString('vi-VN'),
          ]}))} onSelect={setSelectedCaseId} />
      </div>
      <div hidden={!selectedCaseId} className="space-y-4">
        <button type="button" className="operations-back" onClick={() => setSelectedCaseId('')}>Quay lại danh sách</button>
        <div className="space-y-4">
          {selectedCase ? (
            <>
              {/* Resident Info Card */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {selectedCase.id}
                    </span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs font-semibold text-slate-700">
                      Căn hộ: <span className="font-bold text-slate-900">{selectedCase.apartment_id}</span>
                    </span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs text-slate-600">{selectedCase.resident_name}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                    <IconPhone className="w-3.5 h-3.5 text-slate-400" />
                    <span>{selectedCase.resident_phone}</span>
                  </div>
                </div>

                {/* Resident message */}
                <div className="space-y-1.5">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    Nội dung cư dân phản ánh
                  </span>
                  {caseRequests.map((req: VhResidentRequest) => (
                    <div
                      key={req.id}
                      className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-700 leading-relaxed"
                    >
                      "{req.sanitized_content}"
                    </div>
                  ))}
                </div>

              </div>

              {/* AI Suggestions Card */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                    <IconSparkles className="w-4 h-4 text-purple-600" />
                    Phương án xử lý đề xuất
                  </h3>
                  <span className="text-[11px] text-slate-400">
                    AI tự động nhận diện vị trí và bộ phận phụ trách
                  </span>
                </div>

                <div className="space-y-3">
                  {caseCandidates.map((candidate) => {
                    const isMaterialized = candidate.status === 'MATERIALIZED';
                    const isMerged = candidate.status === 'MERGED';

                    return (
                      <div
                        key={candidate.id}
                        className={`p-4 rounded-2xl border transition-all space-y-3 ${
                          isMaterialized
                            ? 'bg-emerald-50/40 border-emerald-200'
                            : isMerged
                              ? 'bg-slate-50 border-slate-200 opacity-60'
                              : 'bg-white border-slate-200 shadow-2xs'
                        }`}
                      >
                        {/* Top Badges */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                candidate.severity === 'P1'
                                  ? 'bg-rose-100 text-rose-700'
                                  : candidate.severity === 'P2'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-blue-100 text-blue-700'
                              }`}
                            >
                              {candidate.severity === 'P1' ? 'Mức khẩn cấp (P1)' : candidate.severity === 'P2' ? 'Mức cao (P2)' : 'Bình thường'}
                            </span>
                            <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-700 rounded">
                              Bộ phận: {candidate.domain === 'MEP' ? 'Kỹ thuật Điện Nước' : candidate.domain === 'SANITATION' ? 'Vệ sinh môi trường' : candidate.domain}
                            </span>
                          </div>

                          <span className="text-[11px] text-purple-700 bg-purple-50 font-semibold px-2 py-0.5 rounded">
                            Độ khớp AI: {Math.round(candidate.confidence * 100)}%
                          </span>
                        </div>

                        {/* Summary & Location */}
                        <div className="space-y-1">
                          <p className="text-xs font-bold text-slate-900 leading-snug">
                            {candidate.normalized_summary}
                          </p>
                          <p className="text-[11px] text-slate-500">
                            Vị trí: Tòa <strong>{candidate.location_json.towerCode}</strong> • Tầng {candidate.location_json.floor || '—'} • {candidate.location_json.areaCode || 'Khu vực chung'}
                          </p>
                        </div>

                        {/* Status if already converted */}
                        {isMaterialized && candidate.materialized_incident_id && (
                          <div className="p-2.5 bg-emerald-100/70 border border-emerald-300 rounded-xl text-xs font-bold text-emerald-900 flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <IconCheck className="w-4 h-4 text-emerald-700" />
                              <span>Đã tạo sự cố chính thức: <strong>{candidate.materialized_incident_id}</strong></span>
                            </div>
                            <span className="text-[11px] text-emerald-700 underline cursor-pointer">
                              Xem chi tiết sự cố ➔
                            </span>
                          </div>
                        )}

                        {isMerged && (
                          <div className="p-2 bg-slate-100 rounded-lg text-xs text-slate-500">
                            Đã gộp vào sự cố: {candidate.merged_into_id}
                          </div>
                        )}

                        {/* Actions */}
                        {!isMaterialized && !isMerged && (
                          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleOpenSplit(candidate)}
                                className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-200 transition-colors"
                              >
                                <IconCut className="w-3.5 h-3.5 text-slate-500" />
                                <span>Tách việc</span>
                              </button>

                              <button
                                type="button"
                                onClick={() => {
                                  setMergeSource(candidate);
                                  setMergeTargetId('ISSUE-CAND-01');
                                }}
                                className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-200 transition-colors"
                              >
                                <IconGitMerge className="w-3.5 h-3.5 text-slate-500" />
                                <span>Gộp trùng</span>
                              </button>

                              <button
                                type="button"
                                onClick={() => {
                                  setActionSuccessMsg(`Đã gửi tin nhắn đề nghị cư dân gửi thêm ảnh hiện trường.`);
                                  setTimeout(() => setActionSuccessMsg(null), 3000);
                                }}
                                className="px-2.5 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-200 transition-colors"
                              >
                                <IconHelpCircle className="w-3.5 h-3.5 text-slate-500" />
                                <span>Hỏi thêm cư dân</span>
                              </button>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleMaterialize(candidate.id)}
                              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                            >
                              <IconCheck className="w-4 h-4" />
                              <span>Xác nhận & Tạo sự cố</span>
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-2xl border border-slate-200">
              Chọn một yêu cầu bên trái để xem nội dung chi tiết.
            </div>
          )}
        </div>
      </div>

      {/* Split Modal */}
      {splitCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <IconCut className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-slate-900 text-sm">
                  Tách Yêu Cầu Thành 2 Việc Riêng Biệt
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSplitCandidate(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-600">
              Khi phản ánh của cư dân gồm nhiều vấn đề thuộc các bộ phận khác nhau (ví dụ: vừa hư thang máy vừa hỏng đèn hành lang), bạn có thể tách thành 2 phiếu việc độc lập:
            </p>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <span className="font-bold text-blue-600">Phần việc 1:</span>
                <input
                  type="text"
                  value={splitPartA.summary}
                  onChange={(e) => setSplitPartA({ ...splitPartA, summary: e.target.value })}
                  className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs"
                />
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <span className="font-bold text-emerald-600">Phần việc 2:</span>
                <input
                  type="text"
                  value={splitPartB.summary}
                  onChange={(e) => setSplitPartB({ ...splitPartB, summary: e.target.value })}
                  className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setSplitCandidate(null)}
                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-semibold"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmSplit}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold"
              >
                Xác nhận tách việc
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Merge Modal */}
      {mergeSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <IconGitMerge className="w-5 h-5 text-purple-600" />
                <h3 className="font-bold text-slate-900 text-sm">Gộp Phản Ánh Trùng Lặp</h3>
              </div>
              <button
                type="button"
                onClick={() => setMergeSource(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-600">
              Chọn sự cố đã có sẵn để gộp phản ánh này vào cùng một vụ việc:
            </p>

            <select
              value={mergeTargetId}
              onChange={(e) => setMergeTargetId(e.target.value)}
              className="w-full p-2.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-800"
            >
              {issueCandidates
                .filter((c) => c.id !== mergeSource.id)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} — {c.normalized_summary.slice(0, 45)}...
                  </option>
                ))}
            </select>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setMergeSource(null)}
                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-semibold"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmMerge}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-bold"
              >
                Xác nhận gộp
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
