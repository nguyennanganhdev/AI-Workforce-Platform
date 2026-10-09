import type { ReactNode } from "react";
import { previewAccount } from "../auth/demo-access";
import "./workspace.css";
export function WorkspaceFrame({
  title,
  description,
  children,
  error,
  notice,
  connectedAccount,
  contentOnly = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  error?: string;
  notice?: string;
  connectedAccount?: { role: string; scope: string };
  contentOnly?: boolean;
}) {
  const a = connectedAccount ?? previewAccount();
  if (!a)
    return (
      <div className="ops-workspace">
        <p className="ws-notice error">
          Tài khoản mẫu đã bị khóa hoặc không còn tồn tại.
        </p>
        <a href="/operations/login">Về đăng nhập</a>
      </div>
    );
  if (contentOnly) return <div className="ops-workspace">{children}</div>;
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
      {/* The connected shell already has this navigation in its sidebar. */}
      {!connectedAccount && (a.role === "manager" || a.role === "admin") && (
        <nav className="ws-tabs" aria-label="Không gian làm việc">
          {(a.role === "admin"
            ? [["accounts", "Tài khoản"]]
            : a.role === "manager"
              ? [
                  ["kanban", "Phân công công việc"],
                  ["reports", "Báo cáo"],
                ]
              : [["my-tasks", "Việc của tôi"]]
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
      )}
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
        {connectedAccount
          ? "Dữ liệu được tải từ hệ thống vận hành. Thao tác được kiểm tra quyền và lưu trên máy chủ."
          : "Workspace FE · Dữ liệu và hành động mô phỏng trên trình duyệt. Chưa gửi lệnh, cảnh báo hay yêu cầu đến hệ thống thật."}
      </p>
    </div>
  );
}
