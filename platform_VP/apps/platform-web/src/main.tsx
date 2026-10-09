import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Bot,
  Cable,
  CalendarClock,
  CircleDot,
  FlaskConical,
  KeyRound,
  Layers3,
  LogOut,
  Menu,
  MessageSquare,
  Network,
  Shield,
  Workflow,
  X,
} from 'lucide-react';
import { api, post } from './api';
import type { Row } from './api';
import { ErrorBox, Form } from './components';
import { Agents, Members, Operations, Resources } from './manage';
import { Evaluations, Sessions, SessionView } from './sessions';
import './style.css';

function App() {
  const [me, setMe] = useState<Row | null | undefined>();
  const [error, setError] = useState('');
  const [nav, setNav] = useState(false);
  const location = useLocation();
  useEffect(() => {
    api('/me')
      .then(setMe)
      .catch(() => setMe(null));
  }, []);
  useEffect(() => setNav(false), [location.pathname]);
  if (me === undefined)
    return (
      <div className="loading" role="status">
        Đang kết nối platform…
      </div>
    );
  if (me === null)
    return (
      <main className="login-page">
        <div className="login-brand">
          <div className="brand-symbol">VP</div>
          <p>AGENT WORKSPACE</p>
          <h1>
            Mỗi agent một vai trò.
            <br />
            Cả team cùng một mục tiêu.
          </h1>
          <p className="login-description">
            Danh tính rõ ràng. Context đúng phạm vi.
            <br />
            Tiến độ và bằng chứng có thể kiểm tra.
          </p>
          <span className="login-footer">Standalone platform · AgentScope runtime</span>
        </div>
        <section className="login-form">
          <div className="eyebrow">TRUY CẬP WORKSPACE</div>
          <h2>Đăng nhập</h2>
          <p>Dùng tài khoản do quản trị viên cấp.</p>
          <ErrorBox error={error} />
          <Form
            fields={[
              { key: 'email', label: 'Email', type: 'email', required: true },
              { key: 'password', label: 'Mật khẩu', type: 'password', required: true },
            ]}
            label="Vào workspace"
            submit={async (values) => {
              try {
                await post('/auth/login', values);
                setMe(await api('/me'));
              } catch (e) {
                setError((e as Error).message);
                throw e;
              }
            }}
          />
        </section>
      </main>
    );
  const isAdmin = me.role === 'admin',
    canWrite = me.role !== 'viewer';
  const links = [
    {
      label: 'LÀM VIỆC',
      items: [
        ['/sessions', 'Sessions', MessageSquare],
        ['/agents', 'Đội ngũ agent', Bot],
        ['/knowledge', 'Tri thức', BookOpen],
        ['/memory', 'Bộ nhớ', Layers3],
      ],
    },
    {
      label: 'TỔ CHỨC',
      items: [
        ['/workflows', 'Quy trình', Workflow],
        ['/schedules', 'Lịch chạy', CalendarClock],
        ['/evaluations', 'Đánh giá', FlaskConical],
      ],
    },
    {
      label: 'KẾT NỐI',
      items: [
        ['/models', 'Model & provider', Network],
        ['/embeddings', 'Embedding', CircleDot],
        ['/skills', 'Kỹ năng', Shield],
        ['/mcp', 'MCP', Cable],
        ['/channels', 'Kênh', Cable],
        ...(isAdmin
          ? [
              ['/credentials', 'Khóa kết nối', KeyRound],
              ['/operations', 'Vận hành & chi phí', Activity],
              ['/members', 'Thành viên', Shield],
            ]
          : []),
      ],
    },
  ];
  return (
    <div className="app-shell">
      <a className="skip" href="#content">
        Đến nội dung chính
      </a>
      <button
        className="mobile-menu"
        onClick={() => setNav(!nav)}
        aria-expanded={nav}
        aria-label="Mở điều hướng"
      >
        {nav ? <X /> : <Menu />}
      </button>
      <aside className={'sidebar ' + (nav ? 'visible' : '')}>
        <NavLink className="brand" to="/sessions">
          <span className="brand-symbol">VP</span>
          <span>
            Agent Platform<small>WORKSPACE / DEFAULT</small>
          </span>
        </NavLink>
        <nav aria-label="Điều hướng chính">
          {links.map((group) => (
            <div className="nav-group" key={group.label}>
              <span>{group.label}</span>
              {group.items.map(([path, label, Icon]) => (
                <NavLink key={String(path)} to={String(path)}>
                  {typeof Icon !== 'string' && <Icon size={18} aria-hidden="true" />}
                  {String(label)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <footer className="sidebar-footer">
          <span className="avatar">{me.email[0].toUpperCase()}</span>
          <div>
            <strong>{me.email}</strong>
            <small>{me.role}</small>
          </div>
          <button
            aria-label="Đăng xuất"
            onClick={async () => {
              await post('/auth/logout');
              setMe(null);
            }}
          >
            <LogOut size={18} />
          </button>
        </footer>
      </aside>
      <div className="main-column">
        <div className="topbar">
          <span>
            Workspace <span className="slash">/</span> <strong>Platform độc lập</strong>
          </span>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API
            <ArrowUpRight size={14} />
          </a>
        </div>
        <main id="content">
          <Routes>
            <Route path="/sessions" element={<Sessions canWrite={canWrite} />} />
            <Route
              path="/sessions/:sid"
              element={<SessionView canWrite={canWrite} isAdmin={isAdmin} />}
            />
            <Route path="/agents" element={<Agents canWrite={canWrite} isAdmin={isAdmin} />} />
            <Route
              path="/evaluations"
              element={<Evaluations canWrite={canWrite} isAdmin={isAdmin} />}
            />
            {[
              'knowledge',
              'memory',
              'models',
              'embeddings',
              'skills',
              'mcp',
              'channels',
              'credentials',
              'workflows',
              'schedules',
            ].map((kind) => (
              <Route
                key={kind}
                path={'/' + kind}
                element={<Resources key={kind} kind={kind} canWrite={canWrite} isAdmin={isAdmin} />}
              />
            ))}
            {isAdmin && (
              <>
                <Route path="/operations" element={<Operations />} />
                <Route path="/members" element={<Members />} />
              </>
            )}
            <Route path="*" element={<Navigate to="/sessions" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
