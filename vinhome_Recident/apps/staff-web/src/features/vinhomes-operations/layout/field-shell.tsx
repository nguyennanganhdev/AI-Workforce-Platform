import { useState, type ReactNode } from "react";
import { IconChevronDown, IconKey, IconLogout } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
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
      <header className="shrink-0 border-b border-border bg-background pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex min-h-16 w-full max-w-2xl items-center gap-3 px-4 py-2">
          <div className="min-w-0 flex-1">
            <p className="break-words text-sm font-semibold text-foreground">{name || "Đang tải tài khoản…"}</p>
            <p className="text-xs text-muted-foreground">Nhân viên hiện trường · Vinhomes</p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" className="min-h-[44px] gap-1.5 px-2" aria-label="Tài khoản nhân viên" />}>
              <span className="text-sm">Tài khoản</span><IconChevronDown aria-hidden="true" className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem className="min-h-[44px] gap-2 px-3" onClick={() => setChanging(true)}><IconKey aria-hidden="true" />Đổi mật khẩu</DropdownMenuItem>
              <DropdownMenuItem className="min-h-[44px] gap-2 px-3" onClick={() => void leave()}><IconLogout aria-hidden="true" />Đăng xuất</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      {changing && <ChangePasswordDialog onClose={() => setChanging(false)} />}
      {notices.length > 0 && (
        <nav aria-label="Việc mới trong hàng đợi" className="shrink-0 border-b border-border bg-primary/5">
          <ul className="mx-auto w-full max-w-2xl divide-y divide-border px-4">
            {notices.slice(0, 1).map((notice) => (
              <li key={notice.id}>
                <a href={notice.to} className="flex min-h-[44px] flex-col items-start gap-1 py-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-ring sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                  <span className="min-w-0 break-words font-medium">{notice.title}</span>
                  <span className="text-sm text-primary">{notice.note} →</span>
                </a>
              </li>
            ))}
          </ul>
          {notices.length > 1 && <p className="mx-auto max-w-2xl px-4 pb-3 text-sm text-muted-foreground">Còn {notices.length - 1} việc trong hàng đợi.</p>}
        </nav>
      )}
      <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
        <div className="mx-auto w-full max-w-2xl p-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">{children}</div>
      </main>
    </div>
  );
}
