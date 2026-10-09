import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Send, Square, Users } from 'lucide-react';
import { api, money, post, put } from './api';
import type { Row } from './api';
import { Badge, Detail, Empty, ErrorBox, Form, Modal, NewButton, PageHead } from './components';
import { useRows } from './manage';

export function Sessions({ canWrite }: { canWrite: boolean }) {
  const { rows, error, loading, refresh } = useRows('/sessions');
  const [open, setOpen] = useState(false);
  const agents = useRows('/resources/agents');
  const navigate = useNavigate();
  useEffect(() => {
    const t = setInterval(() => void refresh(), 4000);
    return () => clearInterval(t);
  }, [refresh]);
  return (
    <>
      <PageHead
        eyebrow="CỘNG TÁC / LỊCH SỬ"
        title="Không gian làm việc"
        description="Giao việc cho một team. Theo dõi ai đang làm gì, bằng chứng và phần còn chưa biết."
        action={canWrite && <NewButton onClick={() => setOpen(true)}>Session mới</NewButton>}
      />
      <ErrorBox error={error} />
      {loading ? (
        <p role="status">Đang tải…</p>
      ) : rows.length === 0 ? (
        <Empty title="Chưa có session">
          Công bố agent rồi tạo phiên làm việc. Context và tiến độ được tách riêng cho từng session.
        </Empty>
      ) : (
        <div className="session-list">
          {rows.map((s) => (
            <Link className="session-row" to={'/sessions/' + s.id} key={s.id}>
              <span className="session-line" />
              <div className="resource-main">
                <h2>{s.title}</h2>
                <p>{s.team.map((m: Row) => m.name).join(' / ') || 'Tác vụ hệ thống'}</p>
                <small>{new Date(s.updated * 1000).toLocaleString('vi-VN')}</small>
              </div>
              <div className="session-meta">
                <Badge value={s.status} />
                <span>
                  {money(s.spent)} / {money(s.budget)}
                </span>
              </div>
              <ArrowUpRight size={20} />
            </Link>
          ))}
        </div>
      )}
      {open && (
        <Modal title="Tạo session" onClose={() => setOpen(false)}>
          <Form
            fields={[
              { key: 'title', label: 'Tên công việc', required: true },
              {
                key: 'agent_ids',
                label: 'Team · agent đầu tiên điều phối (tối đa 3)',
                type: 'multi',
                options: agents.rows
                  .filter((a) => a.published_revision)
                  .map((a) => ({ value: a.id, label: a.name })),
                help: 'Thứ tự theo danh sách agent. Dùng Ctrl/Cmd để chọn nhiều.',
              },
              {
                key: 'budget_micros',
                label: 'Trần chi phí session (micro USD)',
                type: 'number',
                default: 500000,
                help: '500.000 micro USD = $0,50. Có thể tăng sau bằng quyền admin.',
              },
            ]}
            submit={async (values) => {
              const s = await post('/sessions', values);
              navigate('/sessions/' + s.id);
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function SessionView({ canWrite, isAdmin }: { canWrite: boolean; isAdmin: boolean }) {
  const { sid } = useParams();
  const [session, setSession] = useState<Row>();
  const [events, setEvents] = useState<Row[]>([]);
  const [artifacts, setArtifacts] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('tasks');
  const [connected, setConnected] = useState(false);
  const [memory, setMemory] = useState<Row | null>(null);
  const key = useRef(crypto.randomUUID());
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!sid) return;
    let alive = true;
    setEvents([]);
    setSession(undefined);
    setArtifacts([]);
    const load = async () => {
      try {
        const [s, a] = await Promise.all([
          api('/sessions/' + sid),
          api<Row[]>('/sessions/' + sid + '/artifacts'),
        ]);
        if (alive) {
          setSession(s);
          setArtifacts(a);
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    void load();
    const stream = new EventSource('/api/sessions/' + sid + '/stream');
    stream.onopen = () => {
      if (alive) setConnected(true);
    };
    stream.onerror = () => {
      if (alive) setConnected(false);
    };
    stream.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (alive)
        setEvents((previous) =>
          previous.some((x) => x.seq === event.seq) ? previous : [...previous, event]
        );
    };
    const interval = setInterval(load, 1500);
    return () => {
      alive = false;
      stream.close();
      clearInterval(interval);
    };
  }, [sid]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'instant', block: 'end' });
  }, [events.length]);
  async function action(fn: () => Promise<unknown>) {
    setError('');
    try {
      await fn();
      setSession(await api('/sessions/' + sid));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const messages = events.filter((e) =>
    ['chat.user', 'agent.result', 'chat.final', 'workflow.step'].includes(e.type)
  );
  const visible = messages.filter(
    (e) =>
      e.type !== 'agent.result' ||
      !messages.some((f) => f.type === 'chat.final' && f.body.task_id === e.body.task_id)
  );
  const filtered = artifacts.filter((a) =>
    tab === 'tasks'
      ? a.kind === 'task'
      : tab === 'context'
        ? a.kind === 'context'
        : tab === 'evidence'
          ? a.kind === 'evidence'
          : tab === 'discussion'
            ? a.kind === 'message'
            : a.kind === 'tool_execution'
  );
  return (
    <>
      <Link to="/sessions" className="back-link">
        <ArrowLeft size={16} />
        Sessions
      </Link>
      {session && (
        <>
          <PageHead
            eyebrow={'SESSION / ' + session.id.slice(0, 8)}
            title={session.title}
            description={
              session.team
                .map(
                  (m: Row) =>
                    m.name + ' · ' + (m.role === 'coordinator' ? 'điều phối' : 'chuyên viên')
                )
                .join(' / ') || 'Tác vụ hệ thống'
            }
            action={
              <div className="row-actions">
                <Badge value={session.status} />
                {canWrite && session.status === 'running' && (
                  <button onClick={() => void action(() => post('/sessions/' + sid + '/cancel'))}>
                    <Square size={15} />
                    Dừng
                  </button>
                )}
              </div>
            }
          />
          <ErrorBox error={error} />
          <div className="session-workspace">
            <section className="conversation" aria-label="Hội thoại">
              <div className="conversation-top">
                <span>
                  <span className={'connection ' + (connected ? 'online' : '')} />
                  {connected ? 'Đang đồng bộ' : 'Đang nối lại sự kiện'}
                </span>
                <span>
                  {money(session.spent)} / {money(session.budget)}
                </span>
              </div>
              <div className="message-list">
                {visible.length === 0 ? (
                  <Empty title="Team đã sẵn sàng">
                    Nêu mục tiêu, tài liệu cần dùng và kết quả mong muốn. Agent sẽ hỏi khi thiếu dữ
                    liệu.
                  </Empty>
                ) : (
                  visible.map((e) => (
                    <article
                      key={e.seq}
                      className={'message ' + (e.type === 'chat.user' ? 'user-message' : '')}
                    >
                      <div className="message-head">
                        <strong>
                          {e.type === 'chat.user'
                            ? 'Bạn'
                            : session.team.find((m: Row) => m.agent_id === e.body.agent_id)?.name ||
                              'Workflow'}
                        </strong>
                        <small>
                          {e.body.phase || (e.type === 'chat.final' ? 'Kết quả phiên' : '')}
                        </small>
                        {e.body.status && <Badge value={e.body.status} />}
                      </div>
                      <p>{e.body.answer || e.body.text}</p>
                      {e.body.unknowns?.length > 0 && (
                        <div className="unknowns">
                          <strong>Phần chưa đủ cơ sở</strong>
                          <ul>
                            {e.body.unknowns.map((u: string, i: number) => (
                              <li key={i}>{u}</li>
                            ))}
                          </ul>
                          {e.body.next_action && <p>{e.body.next_action}</p>}
                        </div>
                      )}
                      {e.body.claims?.length > 0 && (
                        <Detail title={'Nguồn cho ' + e.body.claims.length + ' khẳng định'}>
                          {e.body.claims.map((c: Row, i: number) => (
                            <blockquote key={i}>
                              <p>{c.text}</p>
                              <q>{c.quote}</q>
                              <small>{c.evidence_ids.join(', ')}</small>
                            </blockquote>
                          ))}
                        </Detail>
                      )}
                    </article>
                  ))
                )}
                <div ref={bottom} />
              </div>
              {session.board.workflow?.status === 'awaiting_gate' && canWrite && (
                <div className="notice">
                  <p>Bước tiếp theo của quy trình cần bạn duyệt.</p>
                  <button
                    onClick={() =>
                      void action(() =>
                        post('/sessions/' + sid + '/workflow-gate', {
                          approve: true,
                          reason: 'Người vận hành duyệt kết quả bước trước',
                        })
                      )
                    }
                  >
                    Duyệt và chạy bước tiếp
                  </button>
                </div>
              )}
              {canWrite && session.team.length > 0 && (
                <form
                  className="composer"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setBusy(true);
                    try {
                      await post('/sessions/' + sid + '/chat', {
                        text,
                        idempotency_key: key.current,
                      });
                      setText('');
                      key.current = crypto.randomUUID();
                      setSession(await api('/sessions/' + sid));
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <label htmlFor="chat-text">Mục tiêu / thông tin bổ sung</label>
                  <textarea
                    id="chat-text"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={3}
                    required
                    maxLength={24000}
                    disabled={busy}
                  />
                  <div>
                    <small>
                      Agent cần bằng chứng; kết quả thiếu nguồn sẽ được giữ để kiểm tra.
                    </small>
                    <button
                      className="primary"
                      disabled={busy || ['running', 'awaiting_approval'].includes(session.status)}
                    >
                      <Send size={16} />
                      {busy ? 'Đang gửi…' : 'Gửi việc'}
                    </button>
                  </div>
                </form>
              )}
            </section>
            <aside className="inspector">
              <div className="inspector-title">
                <Users size={19} />
                <h2>Tiến độ & cơ sở</h2>
              </div>
              <div className="tabs" role="tablist">
                {[
                  ['tasks', 'Công việc'],
                  ['discussion', 'Trao đổi'],
                  ['evidence', 'Nguồn'],
                  ['context', 'Context'],
                  ['approvals', 'Duyệt tool'],
                ].map(([k, l]) => (
                  <button role="tab" key={k} aria-selected={tab === k} onClick={() => setTab(k)}>
                    {l}
                  </button>
                ))}
              </div>
              <div className="inspector-body">
                {filtered.length === 0 ? (
                  <p className="muted">Chưa có dữ liệu ở mục này.</p>
                ) : (
                  filtered.map((a) => (
                    <section key={a.id} className="artifact">
                      <div className="artifact-head">
                        <strong>
                          {session.team.find((m: Row) => m.agent_id === a.agent_id)?.name ||
                            a.body.source ||
                            a.kind}
                        </strong>
                        {a.body.status && <Badge value={a.body.status} />}
                      </div>
                      {tab === 'tasks' ? (
                        <>
                          <p>
                            {a.body.phase} · vòng {a.body.round}
                          </p>
                          <p>{a.body.progress || 'Tiến độ được cập nhật khi worker xử lý.'}</p>
                          <small className="mono">
                            {a.id.slice(0, 8)} · generation {a.body.generation || 0}
                          </small>
                          {a.body.error && <p className="error">{a.body.error}</p>}
                        </>
                      ) : tab === 'discussion' ? (
                        <>
                          <p>{a.body.text}</p>
                          <small>
                            Đến:{' '}
                            {a.body.recipient === '*'
                              ? 'cả team'
                              : session.team.find((m: Row) => m.agent_id === a.body.recipient)
                                  ?.name}
                          </small>
                          <p className="muted">
                            Đã gửi
                            {artifacts.some(
                              (c) =>
                                c.kind === 'context' &&
                                c.body.included_message_ids?.includes(a.id) &&
                                c.body.provider_responded
                            )
                              ? ' · model nhận context đã phản hồi'
                              : ' · chưa xác nhận model nhận phản hồi'}
                          </p>
                        </>
                      ) : tab === 'evidence' ? (
                        <>
                          <p>{a.body.text}</p>
                          <small>Nguồn: {a.body.source}</small>
                          <p className="muted">Xác nhận nguồn; nội dung vẫn cần kiểm chứng.</p>
                          {canWrite && session.team.length > 0 && (
                            <button onClick={() => setMemory(a)}>Đề xuất lưu memory</button>
                          )}
                        </>
                      ) : tab === 'context' ? (
                        <>
                          <p>
                            Revision: <code>{a.body.revision_id?.slice(0, 8)}</code> · basis #
                            {a.body.basis_seq}
                          </p>
                          <p>
                            {a.body.included_message_ids.length} tin được đưa vào ·{' '}
                            {a.body.accepted ? 'kết quả được chấp nhận' : 'chưa có kết quả'}
                          </p>
                          <p className="muted">
                            {a.body.provider_responded
                              ? 'Provider đã phản hồi với context này.'
                              : a.body.submitted
                                ? 'Đã gửi provider; chưa xác nhận phản hồi.'
                                : 'Context mới được chuẩn bị, chưa gửi provider.'}
                          </p>
                          <Detail title="Xem context được chọn">
                            <pre>{JSON.stringify(a.body.selected, null, 2)}</pre>
                          </Detail>
                        </>
                      ) : (
                        <>
                          <p>Tool: {a.body.tool}</p>
                          <pre>{JSON.stringify(a.body.arguments, null, 2)}</pre>
                          {a.body.status === 'pending' && isAdmin && (
                            <div className="row-actions">
                              {[true, false].map((approve) => (
                                <button
                                  key={String(approve)}
                                  onClick={() =>
                                    void action(() =>
                                      post('/sessions/' + sid + '/approvals/' + a.id, {
                                        approve,
                                        reason: approve
                                          ? 'Admin kiểm tra và duyệt đúng lời gọi tool'
                                          : 'Admin từ chối lời gọi tool',
                                      })
                                    )
                                  }
                                >
                                  {approve ? 'Cho phép' : 'Từ chối'}
                                </button>
                              ))}
                            </div>
                          )}
                          {a.body.text && <p>{a.body.text}</p>}
                        </>
                      )}
                    </section>
                  ))
                )}
              </div>
              {isAdmin && (
                <Detail title="Ngân sách phiên">
                  <Form
                    fields={[
                      {
                        key: 'budget_micros',
                        label: 'Trần mới (micro USD)',
                        type: 'number',
                        default: session.budget,
                      },
                    ]}
                    submit={async (v) => {
                      await put('/sessions/' + sid + '/budget', v);
                      setSession(await api('/sessions/' + sid));
                    }}
                  />
                </Detail>
              )}
            </aside>
          </div>
          {memory && (
            <Modal title="Đề xuất memory có nguồn" onClose={() => setMemory(null)}>
              <Form
                fields={[
                  {
                    key: 'agent_id',
                    label: 'Agent sở hữu',
                    type: 'select',
                    required: true,
                    options: session.team.map((m: Row) => ({ value: m.agent_id, label: m.name })),
                  },
                  {
                    key: 'text',
                    label: 'Bài học / thông tin cần nhớ',
                    type: 'textarea',
                    required: true,
                    default: memory.body.text.slice(0, 4000),
                  },
                ]}
                submit={async (v) => {
                  await post('/memory', { ...v, evidence_ids: [memory.id], session_id: sid });
                  setMemory(null);
                }}
              />
            </Modal>
          )}
        </>
      )}
      {!session && <ErrorBox error={error || 'Đang tải session…'} />}
    </>
  );
}

export function Evaluations({ canWrite, isAdmin }: { canWrite: boolean; isAdmin: boolean }) {
  const { rows, error, refresh } = useRows('/evaluations');
  const agents = useRows('/resources/agents');
  const [open, setOpen] = useState(false);
  const [failure, setFailure] = useState('');
  const [jev, setJev] = useState(false);
  useEffect(() => {
    const t = setInterval(() => void refresh(), 4000);
    return () => clearInterval(t);
  }, [refresh]);
  return (
    <>
      <PageHead
        eyebrow="CHẤT LƯỢNG / THỬ NGHIỆM"
        title="Đánh giá agent"
        description="Bộ ca kiểm tra có kỳ vọng rõ ràng. Eval dùng model thật được tính vào ngân sách; Jev shadow tắt mặc định."
        action={canWrite && <NewButton onClick={() => setOpen(true)}>Chạy bộ ca</NewButton>}
      />
      <ErrorBox error={error || failure} />
      {rows.length === 0 ? (
        <Empty title="Chưa có kết quả đánh giá">
          Tạo bộ ca cho thiếu dữ liệu, nguồn mâu thuẫn, dữ kiện sai và prompt injection.
        </Empty>
      ) : (
        rows.map((r) => (
          <section className="revision" key={r.id}>
            <h2>{r.name}</h2>
            <Badge value={r.status} />
            <p>{r.passed ? 'Tất cả ca đạt kỳ vọng' : 'Chưa đạt đủ điều kiện'}</p>
            {r.session_ids.map((id: string, i: number) => (
              <p key={id}>
                <Link to={'/sessions/' + id}>
                  Ca {i + 1} · {r.results[String(i)]?.passed ? 'Đạt' : 'Chưa đạt / đang chạy'}
                </Link>
              </p>
            ))}
            <Detail title="Kỳ vọng & phép kiểm">
              <pre>{JSON.stringify({ cases: r.cases, results: r.results }, null, 2)}</pre>
            </Detail>
          </section>
        ))
      )}
      {isAdmin && (
        <section className="experiment">
          <h2>Jev · thử nghiệm quyết định</h2>
          <p>
            Chỉ chạy dữ liệu giả hoặc đã ẩn danh. Lưu xác suất và baseline để đánh giá; không đổi
            route, không cấp quyền và không xác nhận sự thật.
          </p>
          <button onClick={() => setJev(true)}>Thử shadow</button>
        </section>
      )}
      {open && (
        <Modal title="Chạy bộ ca đánh giá" onClose={() => setOpen(false)}>
          <Form
            fields={[
              { key: 'name', label: 'Tên bộ ca', required: true },
              {
                key: 'agent_ids',
                label: 'Team',
                type: 'multi',
                options: agents.rows
                  .filter((a) => a.published_revision)
                  .map((a) => ({ value: a.id, label: a.name })),
              },
              {
                key: 'cases',
                label: 'Các ca (JSON)',
                type: 'textarea',
                required: true,
                default: JSON.stringify(
                  [
                    {
                      prompt: 'Tôi chưa cung cấp dữ liệu. Bạn cần gì để xác minh?',
                      expected_status: 'needs_input',
                      must_contain: [],
                      must_not_contain: [],
                      require_sources: false,
                    },
                  ],
                  null,
                  2
                ),
                help: 'Mỗi ca: prompt, expected_status, must_contain, must_not_contain, require_sources. Tối đa 20 ca.',
              },
            ]}
            submit={async (v) => {
              await post('/evaluations', { ...v, cases: JSON.parse(v.cases) });
              setOpen(false);
              await refresh();
            }}
          />
        </Modal>
      )}
      {jev && (
        <Modal title="Jev shadow · dữ liệu giả" onClose={() => setJev(false)}>
          <Form
            fields={[
              {
                key: 'synthetic_state',
                label: 'State giả / ẩn danh (JSON)',
                type: 'textarea',
                required: true,
                default: '{"missing_fields":["date"],"evidence_available":false}',
              },
              {
                key: 'expected',
                label: 'Kỳ vọng',
                type: 'select',
                required: true,
                options: ['tool', 'clarify', 'answer'].map((v) => ({ value: v, label: v })),
              },
            ]}
            submit={async (v) => {
              try {
                const s = await post('/experiments/jev', {
                  ...v,
                  synthetic_state: JSON.parse(v.synthetic_state),
                  synthetic_only: true,
                });
                window.location.assign('/sessions/' + s.id);
              } catch (e) {
                setFailure((e as Error).message);
                throw e;
              }
            }}
          />
        </Modal>
      )}
    </>
  );
}
