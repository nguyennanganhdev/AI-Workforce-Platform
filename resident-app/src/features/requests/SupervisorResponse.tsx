import { useState } from 'react';
import type { SupervisorInteraction } from '../../services/use-connected-resident';

export function SupervisorResponse({item, busy, onRespond}: {item: SupervisorInteraction; busy: boolean;
  onRespond: (decision: 'information' | 'approve' | 'reject' | 'request_changes', note: string) => Promise<unknown>}) {
  const [note, setNote] = useState('');
  const information = item.pending_kind === 'information';
  return <section className="white-card resident-consent" aria-label="Phản hồi Supervisor">
    <h3>{information ? 'Ban quản lý cần bạn bổ sung thông tin' : 'Phương án cần bạn xác nhận'}</h3>
    <p>{item.question}</p>
    {!information && item.proposal && <>
      <strong>{item.title}</strong><ol>{item.proposal.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
      <p>Thời gian dự kiến: {item.proposal.expected_duration}. Điều kiện: {item.proposal.conditions}.</p>
      <p>Chi phí dự kiến: {item.proposal.cost ? `${item.proposal.cost.amount.toLocaleString('vi-VN')} ${item.proposal.cost.currency}` : 'Chưa xác định'}.</p>
    </>}
    <label htmlFor="supervisor-response-note">{information ? 'Thông tin bổ sung' : 'Ý kiến của bạn'}</label>
    <textarea id="supervisor-response-note" value={note} maxLength={2000} disabled={busy} rows={3} onChange={e => setNote(e.target.value)} />
    <div className="button-row">{information ?
      <button className="primary-button" disabled={busy || !note.trim()} onClick={() => void onRespond('information', note)}>Gửi thông tin bổ sung</button> : <>
        <button className="primary-button" disabled={busy} onClick={() => void onRespond('approve', note.trim() || 'Tôi đồng ý phương án này.')}>Đồng ý phương án</button>
        <button className="secondary-button" disabled={busy || !note.trim()} onClick={() => void onRespond('request_changes', note)}>Yêu cầu sửa phương án</button>
        <button className="secondary-button" disabled={busy || !note.trim()} onClick={() => void onRespond('reject', note)}>Từ chối phương án</button>
      </>}</div>
  </section>;
}
