import type { ReactNode } from "react";
import { previewAccount } from "../auth/demo-access";
import "./workspace.css";
export function WorkspaceFrame({
  title,
  description,
  children,
  error,
  notice,
}: {
  title: string;
  description: string;
  children: ReactNode;
  error?: string;
  notice?: string;
}) {
  const a = previewAccount();
  if (!a)
    return (
      <div className="ops-workspace">
        <p className="ws-notice error">
          Tài khoản mẫu đã bị khóa hoặc không còn tồn tại.
        </p>
        <a href="/operations/login">Về đăng nhập</a>
      </div>
    );
  return (
    <div className="ops-workspace">
      <header className="ws-head">
        <div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <span className="ws-scope">
          {a.role === "admin" ? "Toàn hệ thống" : `Phạm vi ${a.scope}`}
        </span>
      </header>
      <nav className="ws-tabs" aria-label="Không gian làm việc">
        {(a.role === "admin"
          ? [["accounts", "Tài khoản"]]
          : a.role === "manager"
            ? [
                ["team", "Nhóm điều phối"],
                ["dispatch", "Ticket & hiện trường"],
                ["reports", "Báo cáo"],
              ]
            : [["dispatch", "Ticket & hiện trường"]]
        ).map(([path, label]) => (
          <a
            key={path}
            href={`/operations/${path}`}
            aria-current={
              location.pathname === `/operations/${path}` ? "page" : undefined
            }
          >
            {label}
          </a>
        ))}
      </nav>
      {error && (
        <p className="ws-notice error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="ws-notice" role="status">
          {notice}
        </p>
      )}
      {children}
      <p className="ws-helper">
        Workspace FE · Dữ liệu và hành động mô phỏng trên trình duyệt. Chưa gửi
        lệnh, cảnh báo hay yêu cầu đến hệ thống thật.
      </p>
    </div>
  );
}
