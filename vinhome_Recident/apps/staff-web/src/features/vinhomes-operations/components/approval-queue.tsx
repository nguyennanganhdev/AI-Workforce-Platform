import { useState } from 'react';
import { OperationsTable } from './operations-table';
import {
  IconCheck,
  IconX,
  IconClock,
  IconCash,
  IconAlertTriangle,
  IconShieldCheck,
  IconArrowRight,
  IconCertificate,
} from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';
import { useApprovalQueue } from '../hooks/use-approval-queue';
import type { VhActionApproval, VhExecutionGrant } from '../types/action';

export function ApprovalQueue() {
  const {
    pendingApprovals,
    decidedApprovals,
    executionGrants,
    totalPendingCost,
    approveAction,
    rejectAction,
  } = useApprovalQueue();

  const [activeTab, setActiveTab] = useState<'PENDING' | 'GRANTS' | 'HISTORY'>('PENDING');
  const [selectedApproval, setSelectedApproval] = useState<VhActionApproval | null>(null);
  const [decisionReason, setDecisionReason] = useState('');
  const [decisionType, setDecisionType] = useState<'APPROVE' | 'REJECT'>('APPROVE');
  const [historyId, setHistoryId] = useState('');
  const [detailId, setDetailId] = useState('');
  const [modalOpen, setModalOpen] = useState(false);

  const handleOpenDecisionModal = (approval: VhActionApproval, type: 'APPROVE' | 'REJECT') => {
    setSelectedApproval(approval);
    setDecisionType(type);
    setDecisionReason(
      type === 'APPROVE'
        ? 'Ban Quản Lý đồng ý xuất kho và thanh toán gói kinh phí xử lý sự cố kỹ thuật.'
        : 'Yêu cầu kiểm tra lại báo giá từ nhà thầu phụ trước khi xuất kinh phí.',
    );
    setModalOpen(true);
  };

  const handleConfirmDecision = () => {
    if (!selectedApproval) return;
    if (decisionType === 'APPROVE') {
      approveAction(selectedApproval.id, decisionReason);
    } else {
      rejectAction(selectedApproval.id, decisionReason);
    }
    setModalOpen(false);
    setDetailId('');
  };

  return (
    <div className="space-y-5 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Phê duyệt chi phí
            </h1>
            <p className="text-xs text-slate-500">
              Ban Quản Lý xem xét và phê duyệt các đề xuất mua sắm, sửa chữa vượt hạn mức cho phép
            </p>
          </div>
        </div>

        {/* Total Cost Badge */}
        <div className="flex items-center gap-2 bg-white px-3.5 py-2 rounded-xl border border-slate-200/80 shadow-2xs">
          <IconCash className="w-5 h-5 text-emerald-600" />
          <div className="text-right">
            <span className="text-[10px] text-slate-400 font-bold uppercase block">Tổng kinh phí chờ duyệt</span>
            <span className="text-xs font-bold text-slate-900">
              {totalPendingCost.toLocaleString('vi-VN')} đ
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="ops-scroll-tabs flex items-center gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => { setActiveTab('PENDING'); setDetailId(''); }}
          className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors whitespace-nowrap shrink-0 ${
            activeTab === 'PENDING'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Chờ phê duyệt</span>
          {pendingApprovals.length > 0 && (
            <span className="px-2 py-0.2 text-[10px] font-bold bg-rose-500 text-white rounded-full">
              {pendingApprovals.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('GRANTS')}
          className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors whitespace-nowrap shrink-0 ${
            activeTab === 'GRANTS'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <IconCertificate className="w-4 h-4 text-emerald-600" />
          <span>Đã duyệt — Cho phép thi công</span>
          <span className="px-2 py-0.2 text-[10px] font-bold bg-emerald-100 text-emerald-800 rounded-full">
            {executionGrants.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('HISTORY')}
          className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors whitespace-nowrap shrink-0 ${
            activeTab === 'HISTORY'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Lịch sử đã quyết định ({decidedApprovals.length})</span>
        </button>
      </div>

      <div hidden={activeTab !== 'PENDING' || Boolean(detailId)}>
        <OperationsTable title="Đề xuất chờ phê duyệt" titleColumn={1} columns={['Mã đề xuất', 'Nội dung', 'Kinh phí dự kiến', 'Hạn phê duyệt']}
          rows={pendingApprovals.map((item) => ({id: item.id, search: `${item.id} ${item.action_request?.action_type === 'PURCHASE_MATERIAL' ? 'Mua sắm vật tư' : 'Giải ngân'}`, cells: [
            item.id, item.action_request?.action_type === 'PURCHASE_MATERIAL' ? 'Mua sắm vật tư' : 'Phê duyệt giải ngân',
            `${(item.estimated_cost_vnd || 0).toLocaleString('vi-VN')} đồng`, new Date(item.expires_at).toLocaleString('vi-VN'),
          ]}))} onSelect={setDetailId} />
      </div>
      {activeTab === 'PENDING' && detailId && <button type="button" className="operations-back" onClick={() => setDetailId('')}>Quay lại danh sách</button>}
      {/* Content */}
      {activeTab === 'PENDING' && detailId && (
        <div className="space-y-3.5">
          {pendingApprovals.length === 0 ? (
            <div className="p-12 bg-white rounded-2xl border border-slate-200 text-center text-slate-400 text-xs">
              Hiện tại không có đề xuất nào đang chờ phê duyệt.
            </div>
          ) : (
            pendingApprovals.filter((item) => item.id === detailId).map((app: VhActionApproval) => {
              const isExpired = new Date(app.expires_at).getTime() < Date.now();

              return (
                <div
                  key={app.id}
                  className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3.5 hover:border-blue-300 transition-colors"
                >
                  {/* Top Row: Type & Urgency */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                        {app.id}
                      </span>
                      <span className="text-xs text-slate-400">•</span>
                      <span className="text-xs font-bold text-slate-800">
                        {app.action_request?.action_type === 'PURCHASE_MATERIAL' ? 'Mua sắm vật tư thay thế' : 'Phê duyệt giải ngân'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {app.urgency_level === 'CRITICAL' && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700 flex items-center gap-1">
                          <IconAlertTriangle className="w-3.5 h-3.5" /> Khẩn cấp
                        </span>
                      )}
                      <span
                        className={`text-xs flex items-center gap-1 font-medium ${
                          isExpired ? 'text-rose-600 font-bold' : 'text-slate-400'
                        }`}
                      >
                        <IconClock className="w-3.5 h-3.5" />
                        {isExpired ? 'Đã quá hạn' : 'Hạn xử lý: Trong vòng 24h'}
                      </span>
                    </div>
                  </div>

                  {/* Reason Banner */}
                  <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl text-xs space-y-0.5">
                    <span className="font-bold text-amber-900">
                      Lý do cần BQL phê duyệt:
                    </span>
                    <p className="text-amber-800 text-[11px] leading-relaxed">
                      Chi phí vật tư vượt hạn mức tự động phê duyệt (trên 500.000 VNĐ). Cần Trưởng BQL xác nhận trước khi kỹ thuật viên mua và lắp đặt.
                    </p>
                  </div>

                  {/* Details */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5 text-xs">
                    <div className="text-slate-500">
                      Người đề xuất: <strong className="text-slate-800">{app.action_request?.requested_by_name || 'Kỹ sư Trưởng MEP'}</strong>
                    </div>

                    <p className="font-bold text-slate-900 text-sm">
                      {String(app.action_request?.payload?.item || 'Gói vật tư thay thế thiết bị')}
                    </p>

                    <p className="text-slate-600 leading-relaxed">
                      {String(app.action_request?.payload?.reason || 'Phục vụ xử lý dứt điểm sự cố rò rỉ tại trục kỹ thuật')}
                    </p>

                    <div className="pt-2 flex flex-wrap items-center gap-4 text-slate-500 border-t border-slate-200/60 text-[11px]">
                      <div>
                        <span>Kinh phí dự toán: </span>
                        <strong className="text-emerald-700 text-xs">
                          {(app.estimated_cost_vnd || 0).toLocaleString('vi-VN')} đ
                        </strong>
                      </div>
                      <div>
                        <span>Đơn vị cung cấp: </span>
                        <strong className="text-slate-700">
                          {String(app.action_request?.payload?.vendor || 'VinCons / Đối tác ủy quyền')}
                        </strong>
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                    <button
                      type="button"
                      disabled={isExpired}
                      onClick={() => handleOpenDecisionModal(app, 'REJECT')}
                      className="px-4 py-1.5 border border-slate-200 hover:bg-rose-50 hover:border-rose-200 text-rose-600 rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                      Từ chối
                    </button>
                    <button
                      type="button"
                      disabled={isExpired}
                      onClick={() => handleOpenDecisionModal(app, 'APPROVE')}
                      className="px-5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-2xs disabled:opacity-50"
                    >
                      Phê duyệt chi phí
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Approved Execution Grants Tab */}
      {activeTab === 'GRANTS' && (
        <div className="space-y-3">
          {executionGrants.length === 0 ? (
            <div className="p-12 bg-white rounded-2xl border border-slate-200 text-center text-slate-400 text-xs">
              Chưa có khoản chi phí nào được phê duyệt thi công.
            </div>
          ) : (
            executionGrants.map((grant: VhExecutionGrant) => (
              <div
                key={grant.id}
                className="bg-white rounded-2xl border border-emerald-200 p-4 shadow-2xs space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-emerald-700">{grant.id}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs font-bold text-slate-800">
                      {grant.allowed_action_type === 'PURCHASE_MATERIAL' ? 'Mua sắm vật tư thay thế' : grant.allowed_action_type}
                    </span>
                  </div>

                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      grant.status === 'ACTIVE'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {grant.status === 'ACTIVE' ? 'Đã duyệt — Có hiệu lực' : `Đã dùng cho phiếu ${grant.consumed_by_work_order_id}`}
                  </span>
                </div>

                <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between text-slate-600">
                  <span>Hạn sử dụng: 24 giờ kể từ khi duyệt</span>
                  <span className="text-slate-400 text-[11px] font-mono">✓ Đã xác thực an toàn</span>
                </div>

                {grant.status === 'ACTIVE' && (
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-emerald-700 font-medium">
                      ✓ Đã đủ điều kiện giao việc cho kỹ thuật viên
                    </span>
                    <Link
                      to="/operations/work-orders"
                      search={{ action: 'new', grantId: grant.id }}
                      className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center gap-1 transition-colors shadow-2xs"
                    >
                      <IconArrowRight className="w-3.5 h-3.5" />
                      <span>Tạo phiếu giao việc ngay</span>
                    </Link>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      <div hidden={activeTab !== 'HISTORY' || Boolean(historyId)}>
        <OperationsTable title="Lịch sử phê duyệt" titleColumn={1} columns={['Mã đề xuất', 'Nội dung', 'Kết quả', 'Người duyệt', 'Ngày quyết định']}
          rows={decidedApprovals.map((item) => ({id: item.id, search: `${item.id} ${String(item.action_request?.payload?.item || '')} ${item.reviewer_name || ''}`, cells: [
            item.id, String(item.action_request?.payload?.item || 'Đề xuất'),
            item.status === 'APPROVED' ? 'Đã phê duyệt' : item.status === 'EXPIRED' ? 'Hết hạn' : 'Đã từ chối',
            item.reviewer_name || 'Hệ thống', item.decided_at ? new Date(item.decided_at).toLocaleString('vi-VN') : 'Chưa có',
          ]}))} onSelect={setHistoryId} />
      </div>
      {activeTab === 'HISTORY' && historyId && <button type="button" className="operations-back" onClick={() => setHistoryId('')}>Quay lại lịch sử phê duyệt</button>}
      {/* History Tab */}
      {activeTab === 'HISTORY' && (
        <div className="space-y-2.5">
          {decidedApprovals.filter((item) => item.id === historyId).map((app: VhActionApproval) => (
            <div
              key={app.id}
              className="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-slate-800">{app.id}</span>
                  <span className="text-slate-400">•</span>
                  <span className="font-semibold text-slate-700">
                    {app.action_request?.payload?.item ? String(app.action_request.payload.item) : 'Đề xuất'}
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                    app.status === 'APPROVED'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  {app.status === 'APPROVED' ? 'Đã duyệt' : app.status === 'EXPIRED' ? 'Hết hạn' : 'Từ chối'}
                </span>
              </div>

              <p className="text-slate-600 italic">"{app.reason}"</p>

              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-100">
                <span>Người duyệt: {app.reviewer_name || 'Hệ thống'}</span>
                <span>
                  {app.decided_at ? new Date(app.decided_at).toLocaleString('vi-VN') : 'Hết hạn'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Decision Modal */}
      {modalOpen && selectedApproval && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-4 sm:p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-base">
                {decisionType === 'APPROVE' ? 'Xác Nhận Phê Duyệt Chi Phí' : 'Xác Nhận Từ Chối'}
              </h3>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <IconX className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-slate-600">
                Xác nhận {decisionType === 'APPROVE' ? 'chấp thuận' : 'từ chối'} đề xuất{' '}
                <strong className="font-mono">{selectedApproval.id}</strong> với kinh phí:{' '}
                <strong className="text-emerald-700">
                  {(selectedApproval.estimated_cost_vnd || 0).toLocaleString()} VNĐ
                </strong>.
              </p>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Ý kiến chỉ đạo / Lý do quyết định:
                </label>
                <textarea
                  rows={3}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl focus:outline-none focus:border-blue-500 text-xs"
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-xl font-semibold text-xs"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmDecision}
                className={`px-5 py-2 text-white rounded-xl font-bold text-xs shadow-sm ${
                  decisionType === 'APPROVE'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                Xác nhận
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
