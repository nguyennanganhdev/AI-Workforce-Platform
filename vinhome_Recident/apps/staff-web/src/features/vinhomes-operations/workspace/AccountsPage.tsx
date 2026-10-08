import { useEffect, useRef, useState } from "react";
import { changeAccount, createAccount } from "./service";
import {
  roleLabels,
  scopes,
  type Account,
  type Role,
  type Scope,
} from "./model";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFrame } from "./WorkspaceFrame";

export function AccountsPage() {
  const w = useWorkspace();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState<Role>("technical");
  const [scope, setScope] = useState<Scope>("S2.01");
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Account | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (deleting) dialog.current?.showModal();
    else dialog.current?.close();
  }, [deleting]);
  if (w.account?.role !== "admin")
    return <p role="alert">Chỉ quản trị viên được quản lý tài khoản.</p>;
  const actor = w.account.id;
  const rows = w.state.accounts.filter(
    (a) =>
      (!status || a.status === status) &&
      `${a.name} ${a.identifier} ${roleLabels[a.role]}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  return (
    <WorkspaceFrame
      title="Quản lý tài khoản"
      description="Cấp tài khoản nhân viên và xét duyệt hồ sơ cư dân."
      error={w.error}
      notice={w.notice}
    >
      <div className="ws-metrics">
        {(["active", "pending", "suspended"] as const).map((s, i) => (
          <div className="ws-card" key={s}>
            <span>{["Đang hoạt động", "Chờ duyệt", "Đã khóa"][i]}</span>
            <strong>
              {w.state.accounts.filter((a) => a.status === s).length}
            </strong>
          </div>
        ))}
      </div>
      <div className="ws-row">
        <label>
          Tìm tài khoản
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Họ tên, mã nhân viên, vai trò"
          />
        </label>
        <label>
          Trạng thái
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Tất cả</option>
            <option value="pending">Chờ duyệt</option>
            <option value="active">Hoạt động</option>
            <option value="suspended">Đã khóa</option>
          </select>
        </label>
        <button onClick={() => setCreating(!creating)}>
          {creating ? "Đóng biểu mẫu" : "+ Cấp tài khoản"}
        </button>
      </div>
      {creating && (
        <form
          className="ws-card ws-stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (
              w.run(
                (s) =>
                  createAccount(s, actor, { name, identifier, role, scope }),
                "Đã tạo hồ sơ mẫu. Backend sẽ gửi hướng dẫn kích hoạt khi tích hợp.",
              )
            ) {
              setName("");
              setIdentifier("");
              setCreating(false);
            }
          }}
        >
          <h2>Cấp tài khoản mới</h2>
          <p>
            Nhân viên nhận tài khoản từ admin. Mật khẩu và thư kích hoạt sẽ do
            backend quản lý.
          </p>
          <label>
            Họ tên
            <input
              required
              minLength={2}
              maxLength={100}
              autoComplete="off"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Mã nhân viên / số điện thoại
            <input
              required
              maxLength={128}
              autoComplete="off"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
          </label>
          <label>
            Vai trò
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {Object.entries(roleLabels)
                .filter(([r]) => r !== "resident")
                .map(([r, label]) => (
                  <option key={r} value={r}>
                    {label}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Phạm vi
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
            >
              {scopes.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <button type="submit">Tạo hồ sơ mẫu</button>
        </form>
      )}
      <section className="ws-card">
        <h2>Danh sách tài khoản · {rows.length}</h2>
        {!rows.length && <p>Không có tài khoản phù hợp.</p>}
        {rows.map((a) => (
          <article className="ws-account" key={a.id}>
            <div>
              <strong>{a.name}</strong>
              <p>
                {a.identifier} · {roleLabels[a.role]} · {a.scope}
              </p>
              <span className="ws-status">
                {a.status === "active"
                  ? "Hoạt động"
                  : a.status === "pending"
                    ? "Chờ duyệt"
                    : "Đã khóa"}
              </span>
            </div>
            <div className="ws-row">
              {a.status === "pending" && (
                <button
                  onClick={() =>
                    w.run((s) => changeAccount(s, actor, a.id, "approve"))
                  }
                >
                  Duyệt cư dân
                </button>
              )}
              {a.status === "suspended" && (
                <button
                  onClick={() =>
                    w.run((s) => changeAccount(s, actor, a.id, "activate"))
                  }
                >
                  Kích hoạt
                </button>
              )}
              {a.status === "active" && (
                <button
                  className="ws-secondary"
                  disabled={a.id === actor}
                  onClick={() =>
                    w.run((s) => changeAccount(s, actor, a.id, "suspend"))
                  }
                >
                  Khóa
                </button>
              )}
              <button
                className="ws-danger"
                disabled={a.id === actor}
                onClick={() => {
                  setConfirmation("");
                  w.setError("");
                  setDeleting(a);
                }}
              >
                Xóa
              </button>
            </div>
          </article>
        ))}
      </section>
      <section className="ws-card">
        <h2>Nhật ký quản trị mẫu</h2>
        {w.state.audit.length ? (
          w.state.audit.slice(0, 12).map((a) => (
            <p key={a.id}>
              {new Date(a.at).toLocaleString("vi-VN")} · {a.actor} · {a.label}
            </p>
          ))
        ) : (
          <p>Chưa có thay đổi.</p>
        )}
      </section>
      <dialog
        ref={dialog}
        className="ws-dialog"
        onCancel={() => setDeleting(null)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (
              deleting &&
              w.run((s) =>
                changeAccount(s, actor, deleting.id, "delete", confirmation),
              )
            )
              setDeleting(null);
          }}
        >
          <h2>Xóa hồ sơ mẫu?</h2>
          <p>
            Nhập <strong>{deleting?.identifier}</strong> để xác nhận xóa{" "}
            {deleting?.name}. Nhân viên đang có việc phải được bàn giao trước.
          </p>
          <label>
            Định danh xác nhận
            <input
              autoFocus
              required
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </label>
          {w.error && <p role="alert">{w.error}</p>}
          <div className="ws-row">
            <button
              type="button"
              className="ws-secondary"
              onClick={() => setDeleting(null)}
            >
              Giữ lại
            </button>
            <button
              className="ws-danger"
              disabled={confirmation !== deleting?.identifier}
            >
              Xóa hồ sơ
            </button>
          </div>
        </form>
      </dialog>
    </WorkspaceFrame>
  );
}
