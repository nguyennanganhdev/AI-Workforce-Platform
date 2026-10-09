import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bot, ChevronRight, FileText, Play, ShieldCheck, Trash2 } from 'lucide-react';
import { api, post, put, money } from './api';
import type { Row } from './api';
import { Badge, Detail, Empty, ErrorBox, Form, Modal, NewButton, PageHead } from './components';
import type { FieldSpec } from './components';

const names: Row = {
  models: 'Model & provider',
  credentials: 'Khóa kết nối',
  embeddings: 'Embedding',
  knowledge: 'Kho tri thức',
  skills: 'Kỹ năng',
  mcp: 'MCP',
  workflows: 'Quy trình',
  schedules: 'Lịch chạy',
  channels: 'Kênh kết nối',
  memory: 'Bộ nhớ',
};
const opts = (rows: Row[]) => rows.map((r) => ({ value: r.id, label: r.name }));
const lines = (key: string, label: string, help = 'Mỗi dòng một mục'): FieldSpec => ({
  key,
  label,
  type: 'list',
  help,
});
const text = (key: string, label: string, required = true): FieldSpec => ({ key, label, required });
const select = (
  key: string,
  label: string,
  options: { value: string; label: string }[],
  required = true
): FieldSpec => ({ key, label, type: 'select', options, required });

export function useRows(path: string) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      setRows(await api<Row[]>(path));
      setError('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return { rows, error, loading, refresh };
}

export function Resources({
  kind,
  canWrite,
  isAdmin,
}: {
  kind: string;
  canWrite: boolean;
  isAdmin: boolean;
}) {
  const { rows, error, loading, refresh } = useRows('/resources/' + kind);
  const [editing, setEditing] = useState<Row | null | undefined>(undefined);
  const [deps, setDeps] = useState<Row>({});
  const [actionError, setActionError] = useState('');
  const [selected, setSelected] = useState<Row | null>(null);
  const [search, setSearch] = useState('');
  const [hits, setHits] = useState<Row[]>([]);
  const [uploading, setUploading] = useState(false);
  useEffect(() => {
    Promise.all(
      ['credentials', 'embeddings', 'agents', 'workflows'].map(async (k) => [
        k,
        await api<Row[]>('/resources/' + k),
      ])
    )
      .then((values) => setDeps(Object.fromEntries(values)))
      .catch((e) => setActionError(e.message));
    setSelected(null);
    setEditing(undefined);
  }, [kind]);
  let fields: FieldSpec[] = [text('name', 'Tên')];
  if (kind === 'credentials')
    fields.push({
      key: 'secret',
      label: 'API key / bearer token',
      type: 'password',
      required: true,
      help: 'Lưu mã hóa trên máy chủ; không trả lại trong API.',
    });
  if (kind === 'models' || kind === 'embeddings')
    fields.push(
      select(
        'adapter',
        'Adapter',
        (kind === 'models'
          ? ['openai', 'openai-responses', 'anthropic', 'dashscope', 'gemini', 'ollama']
          : ['openai', 'ollama']
        ).map((v) => ({ value: v, label: v }))
      ),
      text('model', 'Model ID'),
      select('credential_id', 'Khóa kết nối', opts(deps.credentials || []), false),
      text('base_url', 'Endpoint tùy chỉnh', false),
      text('pricing_version', 'Nguồn / phiên bản giá'),
      {
        key: 'input_micros_per_million',
        label: 'Giá input (micro USD / triệu token)',
        type: 'number',
        default: 0,
        help: '1 USD = 1.000.000 micro USD. Nhập theo giá đã kiểm chứng.',
      }
    );
  if (kind === 'models')
    fields.push(
      {
        key: 'output_micros_per_million',
        label: 'Giá output (micro USD / triệu token)',
        type: 'number',
        default: 0,
      },
      { key: 'context_tokens', label: 'Context tối đa (token)', type: 'number', default: 32000 },
      { key: 'max_output_tokens', label: 'Output tối đa (token)', type: 'number', default: 2048 },
      { key: 'rpm', label: 'Request / phút', type: 'number', default: 60 },
      { key: 'tpm', label: 'Token / phút', type: 'number', default: 120000 },
      {
        key: 'capabilities',
        label: 'Capabilities',
        type: 'multi',
        default: ['tools', 'json'],
        options: ['tools', 'json', 'vision', 'audio'].map((v) => ({ value: v, label: v })),
      },
      { key: 'enabled', label: 'Cho phép sử dụng', type: 'checkbox', default: true }
    );
  if (kind === 'embeddings')
    fields.push({ key: 'dimensions', label: 'Số chiều', type: 'number', default: 1536 });
  if (kind === 'knowledge')
    fields.push(
      { key: 'description', label: 'Mô tả', type: 'textarea' },
      select('visibility', 'Phạm vi', [
        { value: 'private', label: 'Riêng tư' },
        { value: 'workspace', label: 'Workspace' },
      ]),
      select(
        'embedding_model_id',
        'Embedding (để trống: tìm theo từ khóa)',
        opts(deps.embeddings || []),
        false
      )
    );
  if (kind === 'skills')
    fields.push({
      key: 'instructions',
      label: 'Hướng dẫn kỹ năng',
      type: 'textarea',
      required: true,
    });
  if (kind === 'mcp')
    fields.push(
      text('url', 'Streamable HTTP endpoint'),
      select('credential_id', 'Bearer token', opts(deps.credentials || []), false),
      lines('allowed_tools', 'Tool được cấp quyền'),
      {
        key: 'read_only',
        label: 'Chỉ tự chạy tool khai báo read-only',
        type: 'checkbox',
        default: true,
      },
      { key: 'enabled', label: 'Bật kết nối', type: 'checkbox' }
    );
  if (kind === 'workflows' || kind === 'channels')
    fields.push({
      key: 'agent_ids',
      label: 'Agent (đầu tiên điều phối, tối đa 3)',
      type: 'multi',
      options: opts(deps.agents || []),
    });
  if (kind === 'workflows')
    fields.push(lines('steps', 'Các bước thực hiện'), {
      key: 'human_gate',
      label: 'Duyệt thủ công giữa các bước',
      type: 'checkbox',
      default: true,
    });
  if (kind === 'schedules')
    fields.push(
      select('workflow_id', 'Quy trình', opts(deps.workflows || [])),
      text('cron', 'Cron (ví dụ: 0 9 * * 1-5)'),
      { ...text('timezone', 'Múi giờ'), default: 'Asia/Ho_Chi_Minh' },
      { key: 'enabled', label: 'Bật lịch', type: 'checkbox' }
    );
  if (kind === 'channels')
    fields.push(
      { ...text('token', 'Bearer token mới (ít nhất 32 ký tự)'), type: 'password' },
      { key: 'enabled', label: 'Bật nhận webhook', type: 'checkbox' }
    );
  const writable =
    canWrite &&
    (!['models', 'credentials', 'embeddings', 'mcp', 'channels'].includes(kind) || isAdmin) &&
    kind !== 'memory';
  async function action(fn: () => Promise<unknown>) {
    setActionError('');
    try {
      await fn();
      await refresh();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="TÀI NGUYÊN / CẤU HÌNH"
        title={names[kind]}
        description={
          kind === 'memory'
            ? 'Bộ nhớ riêng của agent, có nguồn, chủ sở hữu và trạng thái xác minh.'
            : kind === 'knowledge'
              ? 'Tài liệu dùng chung có phân quyền. Agent chỉ tra cứu các kho được gắn vào revision.'
              : 'Cấu hình có kiểm soát; mọi thay đổi được ghi vào nhật ký quản trị.'
        }
        action={
          writable && (
            <NewButton onClick={() => setEditing(null)}>Thêm {names[kind].toLowerCase()}</NewButton>
          )
        }
      />
      <ErrorBox error={error || actionError} />
      {loading ? (
        <p role="status">Đang tải…</p>
      ) : rows.length === 0 ? (
        <Empty title={'Chưa có ' + names[kind].toLowerCase()}>
          Thêm tài nguyên để agent sử dụng trong session. Không có kết nối hoặc dữ liệu mẫu tự bật.
        </Empty>
      ) : (
        <div className="resource-list">
          {rows.map((row) => (
            <article className="resource-row" key={row.id}>
              <div className="resource-symbol">
                {kind === 'knowledge' ? <FileText size={22} /> : <ShieldCheck size={22} />}
              </div>
              <div className="resource-main">
                <h3>{row.name || row.text?.slice(0, 80)}</h3>
                <p>
                  {row.description ||
                    row.model ||
                    row.url ||
                    row.cron ||
                    row.status ||
                    'Phiên bản ' + row.version}
                </p>
                <small className="mono">{row.id}</small>
                {row.status && <Badge value={row.status} />}
              </div>
              <div className="row-actions">
                {kind === 'knowledge' && (
                  <button onClick={() => setSelected(row)}>Tài liệu & tra cứu</button>
                )}
                {kind === 'workflows' && canWrite && (
                  <button
                    onClick={() =>
                      action(async () => {
                        const run = await post('/workflows/' + row.id + '/run');
                        window.location.assign('/sessions/' + run.id);
                      })
                    }
                  >
                    <Play size={16} />
                    Chạy
                  </button>
                )}
                {kind === 'memory' && isAdmin && row.status === 'candidate' && (
                  <button onClick={() => action(() => post('/memory/' + row.id + '/verify'))}>
                    Xác minh
                  </button>
                )}
                {kind === 'memory' && canWrite && (
                  <button
                    aria-label="Xóa memory"
                    onClick={() => action(() => api('/memory/' + row.id, { method: 'DELETE' }))}
                  >
                    <Trash2 size={17} />
                  </button>
                )}
                {writable && <button onClick={() => setEditing(row)}>Chỉnh sửa</button>}
                <Detail title="Thông tin">
                  <pre>{JSON.stringify(row, null, 2)}</pre>
                </Detail>
              </div>
            </article>
          ))}
        </div>
      )}
      {editing !== undefined && (
        <Modal
          title={(editing ? 'Sửa ' : 'Thêm ') + names[kind]}
          onClose={() => setEditing(undefined)}
        >
          <Form
            fields={fields}
            initial={editing || {}}
            onCancel={() => setEditing(undefined)}
            submit={async (values) => {
              if (kind === 'credentials') {
                editing
                  ? await put('/credentials/' + editing.id, values)
                  : await post('/credentials', values);
              } else if (editing) {
                await put('/resources/' + kind + '/' + editing.id, {
                  version: editing.version,
                  spec: values,
                });
              } else {
                await post('/resources/' + kind, values);
              }
              setEditing(undefined);
              await refresh();
            }}
          />
        </Modal>
      )}
      {selected && (
        <Modal title={selected.name + ' · Tài liệu'} onClose={() => setSelected(null)}>
          {canWrite && (
            <>
              <label className="upload">
                {uploading ? 'Đang tải lên…' : 'Tải PDF / TXT / MD / CSV (tối đa 4 MB)'}
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.csv"
                  disabled={uploading}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setUploading(true);
                    try {
                      const form = new FormData();
                      form.append('file', file);
                      const response = await fetch('/api/knowledge/' + selected.id + '/upload', {
                        method: 'POST',
                        body: form,
                        credentials: 'same-origin',
                      });
                      if (!response.ok) throw new Error((await response.json()).detail);
                      await refresh();
                    } catch (e) {
                      setActionError((e as Error).message);
                    } finally {
                      setUploading(false);
                    }
                  }}
                />
              </label>
              <DocumentList kid={selected.id} canWrite={canWrite} />
            </>
          )}
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              void action(async () =>
                setHits(
                  await api<Row[]>(
                    '/knowledge/' + selected.id + '/search?q=' + encodeURIComponent(search)
                  )
                )
              );
            }}
          >
            <label>
              Tra cứu nguồn
              <input value={search} onChange={(e) => setSearch(e.target.value)} required />
            </label>
            <button>Tìm</button>
          </form>
          {hits.map((h) => (
            <blockquote key={h.chunk_id}>
              <p>{h.text}</p>
              <cite>{h.source}</cite>
            </blockquote>
          ))}
        </Modal>
      )}
    </>
  );
}

function DocumentList({ kid, canWrite }: { kid: string; canWrite: boolean }) {
  const { rows, refresh } = useRows('/resources/documents');
  const [error, setError] = useState('');
  useEffect(() => {
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [refresh]);
  return (
    <>
      <ErrorBox error={error} />
      {rows
        .filter((d) => d.knowledge_id === kid)
        .map((d) => (
          <div className="doc-row" key={d.id}>
            <span>
              {d.title}
              <small>
                {d.index_status} · {d.chunk_count || 0} đoạn{d.revoked ? ' · đã thu hồi' : ''}
              </small>
            </span>
            {canWrite && !d.revoked && (
              <button
                onClick={async () => {
                  try {
                    await api('/documents/' + d.id, { method: 'DELETE' });
                    await refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Thu hồi
              </button>
            )}
          </div>
        ))}
    </>
  );
}

export function Agents({ canWrite, isAdmin }: { canWrite: boolean; isAdmin: boolean }) {
  const { rows, error, loading, refresh } = useRows('/resources/agents');
  const [agent, setAgent] = useState<Row | null>(null);
  const [versions, setVersions] = useState<Row[]>([]);
  const [edit, setEdit] = useState<Row | undefined>();
  const [creating, setCreating] = useState(false);
  const [deps, setDeps] = useState<Row>({});
  const [message, setMessage] = useState('');
  const [actionError, setActionError] = useState('');
  useEffect(() => {
    Promise.all(
      ['models', 'knowledge', 'skills', 'mcp'].map(async (k) => [
        k,
        await api<Row[]>('/resources/' + k),
      ])
    )
      .then((values) => setDeps(Object.fromEntries(values)))
      .catch((e) => setActionError(e.message));
  }, []);
  async function inspect(a: Row) {
    setAgent(a);
    setVersions(await api<Row[]>('/agents/' + a.id + '/revisions'));
  }
  const fields: FieldSpec[] = [
    text('name', 'Tên agent'),
    {
      key: 'purpose',
      label: 'Mục đích / công việc chịu trách nhiệm',
      type: 'textarea',
      required: true,
    },
    { key: 'charter', label: 'Danh tính và nguyên tắc làm việc', type: 'textarea', required: true },
    {
      key: 'limits',
      label: 'Giới hạn và cách xử lý khi không biết',
      type: 'textarea',
      default: 'Không tự suy đoán dữ kiện thiếu; yêu cầu bằng chứng.',
    },
    lines('specialties', 'Chuyên môn'),
    select('model_id', 'Model chính', opts(deps.models || [])),
    {
      key: 'fallback_model_ids',
      label: 'Model dự phòng',
      type: 'multi',
      options: opts(deps.models || []),
    },
    {
      key: 'knowledge_ids',
      label: 'Kho tri thức được truy cập',
      type: 'multi',
      options: opts(deps.knowledge || []),
    },
    {
      key: 'tools',
      label: 'Quyền tool',
      type: 'multi',
      default: ['board_read', 'knowledge_search', 'team_message'],
      options: [
        { value: 'board_read', label: 'Đọc bảng chung' },
        { value: 'knowledge_search', label: 'Tra cứu tri thức' },
        { value: 'team_message', label: 'Gửi tin đồng đội' },
        { value: 'task_update', label: 'Cập nhật tiến độ' },
        { value: 'memory_search', label: 'Tìm bộ nhớ' },
      ],
    },
    { key: 'mcp_ids', label: 'MCP được truy cập', type: 'multi', options: opts(deps.mcp || []) },
    { key: 'skill_ids', label: 'Kỹ năng', type: 'multi', options: opts(deps.skills || []) },
    select('memory_policy', 'Bộ nhớ', [
      { value: 'verified_private', label: 'Riêng tư, chỉ nguồn đã xác minh' },
      { value: 'off', label: 'Tắt' },
    ]),
    { key: 'max_iters', label: 'Số vòng reasoning tối đa (1–8)', type: 'number', default: 4 },
    { key: 'context_chars', label: 'Giới hạn context (ký tự)', type: 'number', default: 24000 },
  ];
  fields.splice(
    6,
    0,
    select('model_selection', 'Chọn model', [
      { value: 'manual', label: 'Model chính, dự phòng khi lỗi' },
      { value: 'lowest_cost', label: 'Ưu tiên chi phí thấp trong danh sách đã duyệt' },
    ])
  );
  async function run(fn: () => Promise<unknown>) {
    try {
      setActionError('');
      await fn();
      await refresh();
      if (agent) await inspect(agent);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="DANH TÍNH / VÒNG ĐỜI"
        title="Đội ngũ agent"
        description="Mỗi agent có nhiệm vụ, tri thức, bộ nhớ và quyền riêng. Session sử dụng revision đã công bố."
        action={
          canWrite && (
            <NewButton
              onClick={() => {
                setCreating(true);
                setEdit({ memory_policy: 'verified_private' });
              }}
            >
              Tạo agent
            </NewButton>
          )
        }
      />
      <ErrorBox error={error || actionError} />
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {loading ? (
        <p role="status">Đang tải…</p>
      ) : rows.length === 0 ? (
        <Empty title="Bắt đầu với một agent có trách nhiệm rõ ràng">
          Cấu hình provider và model, tạo agent, kiểm tra chính sách rồi công bố revision.
        </Empty>
      ) : (
        <div className="agent-grid">
          {rows.map((a, i) => (
            <button className="agent-card" key={a.id} onClick={() => void run(() => inspect(a))}>
              <div className="agent-card-top">
                <span className="agent-number">{String(i + 1).padStart(2, '0')}</span>
                <Bot size={23} />
              </div>
              <h2>{a.name}</h2>
              <Badge value={a.published_revision ? 'published' : 'draft'} />
              <div className="agent-card-foot">
                <span>Xem danh tính & revision</span>
                <ChevronRight size={18} />
              </div>
            </button>
          ))}
        </div>
      )}
      {agent && edit === undefined && (
        <Modal title={agent.name + ' · Revision'} onClose={() => setAgent(null)}>
          <ErrorBox error={actionError} />
          {versions.map((v) => (
            <section className="revision" key={v.id}>
              <div className="revision-head">
                <h3>Revision {v.number}</h3>
                <Badge value={v.status} />
              </div>
              <p>{v.spec.purpose}</p>
              <Detail title="Danh tính, quyền và cấu hình">
                <pre>{JSON.stringify(v.spec, null, 2)}</pre>
              </Detail>
              <div className="row-actions">
                {canWrite && <button onClick={() => setEdit(v.spec)}>Tạo bản kế tiếp</button>}
                {canWrite && (
                  <button
                    onClick={() =>
                      void run(async () => {
                        const r = await post(
                          '/agents/' + agent.id + '/revisions/' + v.id + '/test'
                        );
                        setMessage(
                          'Policy test: ' +
                            (r.passed ? 'đạt' : 'chưa đạt') +
                            '. Chưa gọi provider; cần eval hội thoại riêng.'
                        );
                      })
                    }
                  >
                    Kiểm tra chính sách
                  </button>
                )}
                {isAdmin && (
                  <>
                    <button
                      className="primary"
                      onClick={() =>
                        void run(() =>
                          post('/agents/' + agent.id + '/revisions/' + v.id + '/release', {
                            action: 'publish',
                            reason: 'Quản trị viên duyệt revision từ giao diện',
                          })
                        )
                      }
                    >
                      {v.status === 'published' ? 'Chọn làm bản hiện hành' : 'Công bố'}
                    </button>
                    {v.status === 'published' && (
                      <button
                        onClick={() =>
                          void run(() =>
                            post('/agents/' + agent.id + '/revisions/' + v.id + '/release', {
                              action: 'retire',
                              reason: 'Ngừng revision từ giao diện quản trị',
                            })
                          )
                        }
                      >
                        Ngừng sử dụng
                      </button>
                    )}
                  </>
                )}
              </div>
            </section>
          ))}
        </Modal>
      )}
      {edit !== undefined && (
        <Modal
          title={creating ? 'Tạo agent' : 'Tạo revision mới'}
          onClose={() => {
            setEdit(undefined);
            setCreating(false);
          }}
        >
          <Form
            fields={fields}
            initial={edit}
            submit={async (spec) => {
              creating
                ? await post('/agents', { spec })
                : await post('/agents/' + agent!.id + '/revisions', { spec });
              setEdit(undefined);
              setCreating(false);
              await refresh();
              if (agent) await inspect(agent);
            }}
            onCancel={() => {
              setEdit(undefined);
              setCreating(false);
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function Operations() {
  const [data, setData] = useState<Row>();
  const [error, setError] = useState('');
  const [tab, setTab] = useState('jobs');
  useEffect(() => {
    let active = true;
    const load = () =>
      api('/operations')
        .then((d) => {
          if (active) setData(d);
        })
        .catch((e) => setError(e.message));
    void load();
    const t = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);
  return (
    <>
      <PageHead
        eyebrow="VẬN HÀNH / NGÂN SÁCH"
        title="Quan sát hệ thống"
        description="Chi phí được dự toán và đối soát bằng usage; số liệu này chưa thay thế hóa đơn provider."
      />
      <ErrorBox error={error} />
      {data && (
        <>
          <div className="metric-strip">
            <div>
              <small>Đã dùng tháng này</small>
              <strong>{money(data.wallet.spent)}</strong>
            </div>
            <div>
              <small>Đang giữ ngân sách</small>
              <strong>{money(data.wallet.reserved)}</strong>
            </div>
            <div>
              <small>Trần tháng</small>
              <strong>{money(data.wallet.budget)}</strong>
            </div>
            <div>
              <small>Session hoạt động tối đa</small>
              <strong>
                {data.limits.sessions}
                <span> / {data.limits.workers} workers</span>
              </strong>
            </div>
          </div>
          <p className="muted">
            Worker: {data.workers?.filter((w: Row) => w.healthy).length || 0} tiến trình đang báo
            trạng thái · heartbeat được cập nhật mỗi 10 giây.
          </p>
          <div className="tabs" role="tablist">
            {[
              ['jobs', 'Hàng đợi'],
              ['usage', 'Lượt gọi & chi phí'],
              ['audit', 'Nhật ký'],
            ].map(([k, l]) => (
              <button role="tab" aria-selected={tab === k} key={k} onClick={() => setTab(k)}>
                {l}
              </button>
            ))}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {(tab === 'jobs'
                    ? ['Task / session', 'Trạng thái', 'Lần chạy', 'Generation', 'Lỗi']
                    : tab === 'usage'
                      ? ['Session', 'Giữ / đã tính', 'Đối soát', 'Model / usage']
                      : ['Hành động', 'Tài nguyên', 'Người thực hiện', 'Thời gian']
                  ).map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data[tab].map((row: Row) => (
                  <tr key={row.id}>
                    {tab === 'jobs' ? (
                      <>
                        <td>
                          <Link to={'/sessions/' + row.session_id}>
                            {row.session_id.slice(0, 8)}
                          </Link>
                          <small>
                            {row.id.slice(0, 8)} · {row.kind}
                          </small>
                        </td>
                        <td>
                          <Badge value={row.status} />
                        </td>
                        <td>{row.attempts}</td>
                        <td>{row.generation}</td>
                        <td>
                          {row.error || '—'}
                          {row.status === 'failed' &&
                            ['provider_error', 'agent_incomplete', 'budget_exhausted'].includes(
                              row.error
                            ) && (
                              <button
                                onClick={async () => {
                                  try {
                                    await post('/operations/jobs/' + row.id + '/retry', {});
                                    setData(await api('/operations'));
                                  } catch (e) {
                                    setError((e as Error).message);
                                  }
                                }}
                              >
                                Yêu cầu chạy lại
                              </button>
                            )}
                        </td>
                      </>
                    ) : tab === 'usage' ? (
                      <>
                        <td>
                          <Link to={'/sessions/' + row.session_id}>
                            {row.session_id.slice(0, 8)}
                          </Link>
                        </td>
                        <td>
                          {money(row.amount)} / {money(row.charged)}
                        </td>
                        <td>{row.status}</td>
                        <td>
                          <code>{JSON.stringify(row.usage)}</code>
                        </td>
                      </>
                    ) : (
                      <>
                        <td>{row.action}</td>
                        <td className="mono">{row.target.slice(0, 12)}</td>
                        <td className="mono">{row.actor.slice(0, 8)}</td>
                        <td>{new Date(row.created * 1000).toLocaleString('vi-VN')}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Detail title="Điều chỉnh trần tháng">
            <Form
              fields={[
                {
                  key: 'budget_micros',
                  label: 'Trần tháng (micro USD)',
                  type: 'number',
                  default: data.wallet.budget,
                },
              ]}
              submit={async (v) => {
                await put('/operations/budget', v);
                setData(await api('/operations'));
              }}
            />
          </Detail>
        </>
      )}
    </>
  );
}

export function Members() {
  const { rows, error, refresh } = useRows('/members');
  const [open, setOpen] = useState(false);
  const [failure, setFailure] = useState('');
  return (
    <>
      <PageHead
        eyebrow="WORKSPACE / PHÂN QUYỀN"
        title="Thành viên"
        description="Admin quản trị; operator chạy agent/session; viewer chỉ đọc dữ liệu được cấp."
        action={<NewButton onClick={() => setOpen(true)}>Thêm thành viên</NewButton>}
      />
      <ErrorBox error={error || failure} />
      {rows.map((row) => (
        <div className="resource-row" key={row.id}>
          <div className="resource-main">
            <h3>{row.email}</h3>
            <p>
              {row.role}
              {row.disabled ? ' · đã vô hiệu hóa' : ''}
            </p>
          </div>
          <select
            aria-label={'Quyền của ' + row.email}
            value={row.role}
            onChange={async (e) => {
              try {
                await put('/members/' + row.id, { role: e.target.value, disabled: row.disabled });
                await refresh();
              } catch (e) {
                setFailure((e as Error).message);
              }
            }}
          >
            {['admin', 'operator', 'viewer'].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
          <button
            onClick={async () => {
              try {
                await put('/members/' + row.id, { role: row.role, disabled: !row.disabled });
                await refresh();
              } catch (e) {
                setFailure((e as Error).message);
              }
            }}
          >
            {row.disabled ? 'Mở lại' : 'Vô hiệu hóa'}
          </button>
        </div>
      ))}
      {open && (
        <Modal title="Thêm thành viên" onClose={() => setOpen(false)}>
          <Form
            fields={[
              { ...text('email', 'Email'), type: 'email' },
              { ...text('password', 'Mật khẩu (tối thiểu 12 ký tự)'), type: 'password' },
              select(
                'role',
                'Quyền',
                ['operator', 'viewer', 'admin'].map((r) => ({ value: r, label: r }))
              ),
            ]}
            submit={async (v) => {
              await post('/members', v);
              setOpen(false);
              await refresh();
            }}
          />
        </Modal>
      )}
    </>
  );
}
