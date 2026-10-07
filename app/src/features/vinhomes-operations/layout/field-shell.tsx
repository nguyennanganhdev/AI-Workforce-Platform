import { useState, type ReactNode } from "react";
import { ChangePasswordDialog } from "./change-password";
import type { ShellNotice } from "./connected-operations-shell";

/**
 * The frame of someone who does the work on site: one column sized for a phone, who is signed in,
 * what is newly offered, and the work. Nothing of management's menu and nothing of OpenBot's.
 */
export function FieldShell({ name, notices = [], children }: { name?: string; notices?: ShellNotice[]; children: ReactNode }) {
  const [changing, setChanging] = useState(false);
  const leave = async () => {
    // The sign-in page is where they go either way; a failed call leaves a session that expires on its own.
    await fetch("/api/business/auth/logout", { method: "POST", credentials: "include" }).catch(() => undefined);
    location.assign("/operations/login");
  };
  return (
    <div lang="vi" translate="no" className="operations-app field-shell notranslate flex h-[100dvh] w-full flex-col overflow-hidden font-sans">
      <header className="shrink-0 border-b border-border bg-background">
        <div className="mx-auto flex h-14 w-full max-w-2xl items-center gap-3 px-4">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900">{name || "Đang tải tài khoản…"}</p>
            <p className="truncate text-xs text-slate-500">Nhân viên hiện trường · Vinhomes</p>
          </div>
          <button type="button" onClick={() => setChanging(true)}
            className="min-h-11 shrink-0 rounded-md px-3 text-sm text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600">
            Đổi mật khẩu
          </button>
          <button type="button" onClick={() => void leave()}
            className="min-h-11 shrink-0 rounded-md px-3 text-sm text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600">
            Đăng xuất
          </button>
        </div>
      </header>
      {changing && <ChangePasswordDialog onClose={() => setChanging(false)} />}
      {notices.length > 0 && (
        <nav aria-label="Việc mới chờ bạn nhận" className="shrink-0 border-b border-blue-100 bg-blue-50">
          <ul className="mx-auto w-full max-w-2xl divide-y divide-blue-100 px-4">
            {notices.slice(0, 1).map((notice) => (
              <li key={notice.id}>
                <a href={notice.to} className="flex min-h-11 items-center justify-between gap-3 py-2 text-sm text-blue-900">
                  <span className="min-w-0 truncate font-medium">{notice.title}</span>
                  <span className="shrink-0 text-[13px] text-blue-800">{notice.note} →</span>
                </a>
              </li>
            ))}
          </ul>
          {notices.length > 1 && <p className="mx-auto max-w-2xl px-4 pb-2 text-xs text-blue-800">Còn {notices.length - 1} công việc chờ nhận trong danh sách.</p>}
        </nav>
      )}
      <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
        <div className="mx-auto w-full max-w-2xl p-4">{children}</div>
      </main>
    </div>
  );
}
