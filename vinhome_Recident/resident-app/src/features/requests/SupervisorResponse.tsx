import { useState } from 'react';
import type { SupervisorInteraction } from '../../services/use-connected-resident';

export function SupervisorResponse({item, busy, onRespond}: {item: SupervisorInteraction; busy: boolean;
  onRespond: (decision: 'information' | 'approve' | 'reject' | 'request_changes', note: string) => Promise<unknown>}) {
  const [note, setNote] = useState('');
  const information = item.pending_kind === 'information';
  return <section className="white-card resident-consent" aria-label="Phản hồi Ban quản lý" aria-busy={busy}>
    <span className="consent-eyebrow">Cần phản hồi của bạn</span>
    <h3>{information ? 'Ban quản lý cần bạn bổ sung thông tin' : 'Phương án cần bạn xác nhận'}</h3>
    <p className="consent-question">{item.question}</p>
    {!information && item.proposal && <>
      <strong>{item.title}</strong><ol>{item.proposal.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
      <p>Thời gian dự kiến: {item.proposal.expected_duration}. Điều kiện: {item.proposal.conditions}.</p>
      <p>Chi phí dự kiến: {item.proposal.cost ? `${item.proposal.cost.amount.toLocaleString('vi-VN')} ${item.proposal.cost.currency}` : 'Chưa xác định'}.</p>
    </>}
    <form className="consent-form" onSubmit={e => { e.preventDefault(); if (information && note.trim() && !busy) void onRespond('information', note.trim()); }}>
    <label htmlFor="supervisor-response-note">{information ? 'Thông tin bổ sung' : 'Ý kiến của bạn'}</label>
    <textarea id="supervisor-response-note" aria-describedby="supervisor-response-help" placeholder={information ? 'Nhập thông tin để Ban quản lý hỗ trợ bạn…' : 'Ghi ý kiến hoặc nội dung cần điều chỉnh…'} value={note} maxLength={2000} disabled={busy} rows={4} onChange={e => setNote(e.target.value)} />
    <div className="consent-help"><span id="supervisor-response-help">{information ? 'Trả lời các thông tin được hỏi ở trên.' : 'Vui lòng ghi lý do nếu cần sửa hoặc từ chối phương án.'}</span><span>{note.length}/2.000</span></div>
    <div className="button-row">{information ?
      <button type="submit" className="primary-button" disabled={busy || !note.trim()}>{busy ? 'Đang gửi…' : 'Gửi thông tin bổ sung'}</button> : <>
        <button type="button" className="primary-button" disabled={busy} onClick={() => void onRespond('approve', note.trim() || 'Tôi đồng ý phương án này.')}>Đồng ý phương án</button>
        <button type="button" className="secondary-button" disabled={busy || !note.trim()} onClick={() => void onRespond('request_changes', note)}>Yêu cầu sửa phương án</button>
        <button type="button" className="secondary-button" disabled={busy || !note.trim()} onClick={() => void onRespond('reject', note)}>Từ chối phương án</button>
      </>}</div></form>
  </section>;
}
