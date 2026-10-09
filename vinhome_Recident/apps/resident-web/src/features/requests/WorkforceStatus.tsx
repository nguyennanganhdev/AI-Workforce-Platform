import {useState} from 'react';
import type {WorkforceApproval, WorkforceTracking} from '../../services/use-connected-resident';

const labels: Record<string, string> = {
  unbound: 'Đang gửi yêu cầu', accepted: 'Đã tiếp nhận', active: 'Đang xử lý',
  awaiting_user: 'Cần bạn bổ sung thông tin', awaiting_approval: 'Cần bạn xác nhận',
  waiting_external_event: 'Đang theo dõi công việc', awaiting_confirmation: 'Chờ xác nhận kết quả',
  needs_attention: 'Cần người phụ trách kiểm tra', closed: 'Đã dừng theo dõi',
};

export function WorkforceStatus({item, busy, onDecide, onClose}: {
  item: WorkforceTracking; busy: boolean;
  onDecide: (approval: WorkforceApproval, decision: 'approve' | 'reject') => Promise<unknown>;
  onClose: () => Promise<unknown>;
}) {
  const [stopping, setStopping] = useState(false);
  const [submitted, setSubmitted] = useState('');
  const approvals = item.snapshot.pending_approvals?.filter(a => a.workflow_id === item.workflow_id) ?? [];
  return <section className="white-card resident-consent" aria-label="Theo dõi hỗ trợ" aria-busy={busy}>
    <h3>{labels[item.state] || 'Đang đồng bộ trạng thái hỗ trợ'}</h3>
    {item.attention && <p role="status">Hệ thống đang cần kiểm tra kết nối hoặc quyền xử lý yêu cầu của bạn.</p>}
    {approvals.map(a => <div key={a.id}>
      <p className="consent-question">{a.summary}</p>
      <p>Hiệu lực đến {new Date(a.expires_at).toLocaleString('vi-VN')}.</p>
      <div className="button-row">
        <button className="primary-button" disabled={busy || submitted === a.id || Date.parse(a.expires_at) <= Date.now()}
          onClick={async () => {if (await onDecide(a, 'approve')) setSubmitted(a.id);}}>Đồng ý thao tác này</button>
        <button className="secondary-button" disabled={busy || submitted === a.id || Date.parse(a.expires_at) <= Date.now()}
          onClick={async () => {if (await onDecide(a, 'reject')) setSubmitted(a.id);}}>Từ chối</button>
      </div>
      {submitted === a.id && <p role="status">Đã gửi quyết định. Đang cập nhật kết quả.</p>}
    </div>)}
    {item.workflow_id && item.state !== 'closed' && <>
      <button className="secondary-button" disabled={busy} onClick={() => setStopping(true)}>Dừng theo dõi hỗ trợ</button>
      {stopping && <div role="group" aria-label="Xác nhận dừng theo dõi">
        <p>Thao tác này chỉ dừng theo dõi tại trợ lý. Công việc và phản ánh tại Ban quản lý vẫn được giữ nguyên.</p>
        <div className="button-row">
          <button className="secondary-button" disabled={busy} onClick={async () => {if (await onClose()) setStopping(false);}}>Xác nhận dừng theo dõi</button>
          <button className="secondary-button" disabled={busy} onClick={() => setStopping(false)}>Tiếp tục theo dõi</button>
        </div>
      </div>}
    </>}
  </section>;
}
