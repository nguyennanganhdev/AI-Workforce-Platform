import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CircleAlert as IconAlertCircle,
  Check as IconCheck,
  Ellipsis as IconDots,
  Plus as IconPlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  accountsQueryOptions,
  createAccountMutationOptions,
  resetPasswordMutationOptions,
  updateAccountMutationOptions,
  type Account,
} from "@/lib/admin/queries";
import {
  AdminBadge,
  AdminConfirm,
  AdminDrawer,
  AdminPage,
  AdminSearch,
  AdminSelect,
  AdminState,
  ExportButton,
  downloadCsv,
  relativeTime,
} from "./AdminUI";

const ROLES: Record<string, string> = {
  customer: "Cư dân",
  staff: "Nhân viên",
  management: "Ban quản lý",
};
const STATUS: Record<string, string> = {
  active: "Hoạt động",
  pending: "Chờ duyệt",
  suspended: "Đã khóa",
};
const roleOf = (account: Account) =>
  account.administrator ? "Quản trị viên" : ROLES[account.role] || account.role;
type EnrichedAccount = Account & {
  last_activity_at?: string | null;
  apartment_scope?: string | null;
  created_at?: string;
};
type Units = { id: string; name: string }[];
const roleOptions = Object.entries(ROLES).map(([value, label]) => ({
  value,
  label,
}));
const toneOf = (account: Account) =>
  account.status === "active"
    ? "ok"
    : account.status === "pending"
      ? "wait"
      : "danger";

export function AccountsPage() {
  const queryClient = useQueryClient();
  const data = useQuery(accountsQueryOptions());
  const update = useMutation(updateAccountMutationOptions(queryClient));
  const [text, setText] = useState("");
  const [role, setRole] = useState("");
  const [unit, setUnit] = useState("");
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState("");
  const [checked, setChecked] = useState<string[]>([]);
  const [locking, setLocking] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const accounts: EnrichedAccount[] = data.data?.accounts || [];
  const units = data.data?.units || [];
  const needle = text.trim().toLowerCase();
  const shown = accounts.filter(
    (account) =>
      (!needle ||
        `${account.name} ${account.email}`.toLowerCase().includes(needle)) &&
      (!role ||
        (role === "admin"
          ? account.administrator
          : !account.administrator && account.role === role)) &&
      (!status || account.status === status) &&
      (!unit || account.management_unit_id === unit),
  );
  const waiting = accounts.filter((account) => account.status === "pending");
  const open = accounts.find((account) => account.id === selected);
  const scopeOf = (account: EnrichedAccount) =>
    account.administrator
      ? "Toàn hệ thống"
      : units.find((item) => item.id === account.management_unit_id)?.name ||
        account.apartment_scope ||
        (account.role === "management" ? "Toàn khu" : "");
  const selectedAccounts = accounts.filter(
    (account) => checked.includes(account.id) && !account.administrator,
  );
  async function change(account: Account, next: "active" | "suspended") {
    await update.mutateAsync({
      id: account.id,
      role: account.role,
      status: next,
      ...(account.management_unit_id
        ? { management_unit_id: account.management_unit_id }
        : {}),
    });
  }
  async function lockAccounts() {
    try {
      for (const id of locking) {
        const account = accounts.find((item) => item.id === id);
        if (account) await change(account, "suspended");
      }
      setNotice(`Đã khóa ${locking.length} tài khoản`);
      setChecked([]);
      setLocking([]);
    } catch {
      /* mutation explains failure */
    }
  }
  return (
    <AdminPage
      title="Tài khoản"
      meta={data.data ? `${accounts.length} tài khoản` : undefined}
      action={
        <Button onClick={() => setCreating(true)}>
          <IconPlus />
          Tạo tài khoản
        </Button>
      }
    >
      {waiting.length > 0 && (
        <section className="ops-admin-panel ops-admin-pending">
          <header>
            <IconAlertCircle size={16} />
            {waiting.length} tài khoản đang chờ bạn duyệt
          </header>
          {waiting.slice(0, 3).map((account) => (
            <div className="ops-admin-pending-row" key={account.id}>
              <span className="ops-admin-avatar">
                {account.name.charAt(0).toUpperCase()}
              </span>
              <div>
                <p>{account.name}</p>
                <small>{account.email}</small>
              </div>
              <span className="ops-admin-muted">
                Đăng ký vai trò {roleOf(account)}
                {account.created_at
                  ? `, gửi ${relativeTime(account.created_at).toLowerCase()}`
                  : ""}
              </span>
              <div className="ops-admin-actions">
                <Button
                  variant="outline"
                  className="ops-admin-danger"
                  disabled={update.isPending}
                  onClick={() => setLocking([account.id])}
                >
                  Từ chối
                </Button>
                <Button
                  disabled={update.isPending}
                  onClick={async () => {
                    try {
                      await change(account, "active");
                      setNotice("Đã duyệt tài khoản");
                    } catch {}
                  }}
                >
                  <IconCheck />
                  Duyệt
                </Button>
              </div>
            </div>
          ))}
        </section>
      )}
      {notice && (
        <p className="ops-admin-success" role="status">
          {notice}
        </p>
      )}
      {update.error && (
        <p className="ops-admin-error" role="alert">
          {update.error.message}
        </p>
      )}
      <section className="ops-admin-panel">
        <div className="ops-admin-toolbar">
          <div className="ops-admin-tabs" aria-label="Trạng thái tài khoản">
            {[
              ["", "Tất cả"],
              ["active", "Hoạt động"],
              ["pending", "Chờ duyệt"],
              ["suspended", "Đã khóa"],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                aria-pressed={status === value}
                onClick={() => setStatus(value)}
              >
                {label}
                <span>
                  {value
                    ? accounts.filter((account) => account.status === value)
                        .length
                    : accounts.length}
                </span>
              </button>
            ))}
          </div>
          <AdminSearch
            value={text}
            onChange={setText}
            placeholder="Tìm theo tên hoặc email"
          />
          <AdminSelect
            label="Vai trò"
            value={role}
            onChange={setRole}
            options={[
              { value: "", label: "Vai trò" },
              ...roleOptions,
              { value: "admin", label: "Quản trị viên" },
            ]}
          />
          <AdminSelect
            label="Đơn vị"
            value={unit}
            onChange={setUnit}
            options={[
              { value: "", label: "Đơn vị" },
              ...units.map((item) => ({ value: item.id, label: item.name })),
            ]}
          />
          <ExportButton
            disabled={data.isPending || !!data.error}
            onClick={() =>
              downloadCsv("tai-khoan.csv", [
                [
                  "Người dùng",
                  "Email",
                  "Vai trò",
                  "Đơn vị, phạm vi",
                  "Trạng thái",
                  "Hoạt động gần nhất",
                ],
                ...shown.map((account) => [
                  account.name,
                  account.email,
                  roleOf(account),
                  scopeOf(account),
                  STATUS[account.status] || account.status,
                  account.last_activity_at
                    ? relativeTime(account.last_activity_at)
                    : "",
                ]),
              ])
            }
          />
        </div>
        {selectedAccounts.length > 0 && (
          <div className="ops-admin-bulk">
            <span>Đã chọn {selectedAccounts.length} tài khoản</span>
            <Button
              variant="outline"
              disabled={update.isPending}
              onClick={async () => {
                try {
                  for (const account of selectedAccounts)
                    await change(account, "active");
                  setNotice(`Đã duyệt ${selectedAccounts.length} tài khoản`);
                  setChecked([]);
                } catch {}
              }}
            >
              Duyệt tài khoản
            </Button>
            <Button
              variant="outline"
              className="ops-admin-danger"
              onClick={() =>
                setLocking(selectedAccounts.map((account) => account.id))
              }
            >
              Khóa truy cập
            </Button>
            <Button variant="ghost" onClick={() => setChecked([])}>
              Bỏ chọn
            </Button>
          </div>
        )}
        {data.isPending || data.error ? (
          <AdminState
            loading={data.isPending}
            error={data.error}
            onRetry={() => void data.refetch()}
          />
        ) : shown.length ? (
          <>
            <div className="ops-admin-table-wrap">
              <table className="ops-admin-table">
                <thead>
                  <tr>
                    <th>
                      <Checkbox
                        aria-label="Chọn các tài khoản đang hiển thị"
                        checked={
                          shown.filter((account) => !account.administrator)
                            .length > 0 &&
                          shown
                            .filter((account) => !account.administrator)
                            .every((account) => checked.includes(account.id))
                        }
                        onCheckedChange={(value) =>
                          setChecked(
                            value
                              ? shown
                                  .filter((account) => !account.administrator)
                                  .map((account) => account.id)
                              : [],
                          )
                        }
                      />
                    </th>
                    <th>Người dùng</th>
                    <th>Vai trò</th>
                    <th>Đơn vị, phạm vi</th>
                    <th>Trạng thái</th>
                    <th>Hoạt động gần nhất</th>
                    <th>
                      <span className="sr-only">Thao tác</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((account) => (
                    <tr
                      key={account.id}
                      data-selected={checked.includes(account.id)}
                    >
                      <td>
                        <Checkbox
                          aria-label={`Chọn ${account.name}`}
                          disabled={account.administrator}
                          checked={checked.includes(account.id)}
                          onCheckedChange={(value) =>
                            setChecked(
                              value
                                ? [...checked, account.id]
                                : checked.filter((id) => id !== account.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        <div className="ops-admin-row-title">
                          <span className="ops-admin-avatar">
                            {account.name.charAt(0).toUpperCase()}
                          </span>
                          <button
                            type="button"
                            onClick={() => setSelected(account.id)}
                          >
                            {account.name}
                            <small>{account.email}</small>
                          </button>
                        </div>
                      </td>
                      <td>{roleOf(account)}</td>
                      <td>{scopeOf(account)}</td>
                      <td>
                        <AdminBadge tone={toneOf(account)}>
                          {STATUS[account.status] || account.status}
                        </AdminBadge>
                      </td>
                      <td className="ops-admin-muted">
                        {account.last_activity_at
                          ? relativeTime(account.last_activity_at)
                          : "Chưa có hoạt động được ghi nhận"}
                      </td>
                      <td>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={`Chi tiết ${account.name}`}
                          title={`Chi tiết ${account.name}`}
                          onClick={() => setSelected(account.id)}
                        >
                          <IconDots />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="ops-admin-table-footer">
              <span>
                Hiển thị {shown.length} trên {accounts.length} tài khoản
              </span>
            </footer>
          </>
        ) : (
          <AdminState empty="Không có tài khoản phù hợp. Thử đổi bộ lọc hoặc tạo tài khoản mới." />
        )}
      </section>
      {creating && (
        <NewAccount units={units} onClose={() => setCreating(false)} />
      )}
      {open && (
        <AccountEditor
          key={open.id}
          account={open}
          units={units}
          onClose={() => setSelected("")}
        />
      )}{" "}
      {locking.length > 0 && (
        <AdminConfirm
          title={
            locking.length === 1 &&
            accounts.find((account) => account.id === locking[0])?.status ===
              "pending"
              ? "Từ chối tài khoản?"
              : "Khóa truy cập?"
          }
          consequence={`${locking.length} tài khoản sẽ không thể đăng nhập. Các phiên đăng nhập hiện tại sẽ bị kết thúc. Bạn có thể mở lại sau.`}
          confirm={
            accounts.find((account) => account.id === locking[0])?.status ===
            "pending"
              ? "Từ chối"
              : "Khóa truy cập"
          }
          busy={update.isPending}
          onCancel={() => setLocking([])}
          onConfirm={() => void lockAccounts()}
        />
      )}
    </AdminPage>
  );
}
function UnitField({
  value,
  units,
  onChange,
}: {
  value: string;
  units: Units;
  onChange: (unit: string) => void;
}) {
  return (
    <label>
      Đơn vị quản lý
      <AdminSelect
        label="Đơn vị quản lý"
        value={value}
        onChange={onChange}
        options={[
          { value: "", label: "Toàn khu" },
          ...units.map((unit) => ({ value: unit.id, label: unit.name })),
        ]}
      />
    </label>
  );
}
function NewAccount({ units, onClose }: { units: Units; onClose: () => void }) {
  const queryClient = useQueryClient();
  const create = useMutation(createAccountMutationOptions(queryClient));
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "customer",
    unit: "",
  });
  const ready =
    form.name.trim().length >= 2 &&
    /\S+@\S+\.\S+/.test(form.email) &&
    form.password.length >= 12;
  const submit = async () => {
    try {
      await create.mutateAsync({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        ...(form.role === "management" && form.unit
          ? { management_unit_id: form.unit }
          : {}),
      });
      onClose();
    } catch {}
  };
  return (
    <AdminDrawer
      title="Tạo tài khoản"
      description="Cư dân cần xác minh căn hộ trước khi gửi phản ánh."
      onClose={onClose}
      busy={create.isPending}
      footer={
        <>
          <Button
            variant="outline"
            disabled={create.isPending}
            onClick={onClose}
          >
            Hủy
          </Button>
          <Button
            disabled={!ready || create.isPending}
            onClick={() => void submit()}
          >
            {create.isPending ? "Đang tạo…" : "Tạo tài khoản"}
          </Button>
        </>
      }
    >
      <form
        className="ops-admin-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) void submit();
        }}
      >
        <label>
          Họ và tên
          <Input
            aria-label="Họ và tên"
            value={form.name}
            maxLength={100}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>
        <label>
          Email
          <Input
            aria-label="Email"
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm({ ...form, email: event.target.value })
            }
          />
        </label>
        <label>
          Mật khẩu ban đầu
          <Input
            aria-label="Mật khẩu ban đầu"
            type="password"
            autoComplete="new-password"
            value={form.password}
            maxLength={128}
            onChange={(event) =>
              setForm({ ...form, password: event.target.value })
            }
          />
          <small>Ít nhất 12 ký tự.</small>
        </label>
        <label>
          Vai trò
          <AdminSelect
            label="Vai trò tài khoản"
            value={form.role}
            options={roleOptions}
            onChange={(role) => setForm({ ...form, role })}
          />
        </label>
        {form.role === "management" && (
          <UnitField
            value={form.unit}
            units={units}
            onChange={(unit) => setForm({ ...form, unit })}
          />
        )}{" "}
        {create.error && (
          <p role="alert" className="ops-admin-error">
            {create.error.message}
          </p>
        )}
      </form>
    </AdminDrawer>
  );
}
/** 16 characters without look-alikes (0/O, 1/l/I), to read out or type from a message. */
function newPassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  return Array.from(crypto.getRandomValues(new Uint32Array(16)), (n) => alphabet[n % alphabet.length]).join("");
}
function AccountEditor({
  account,
  units,
  onClose,
}: {
  account: EnrichedAccount;
  units: Units;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const update = useMutation(updateAccountMutationOptions(queryClient));
  const reset = useMutation(resetPasswordMutationOptions());
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(account.role);
  const [unit, setUnit] = useState(account.management_unit_id || "");
  const [confirming, setConfirming] = useState(false);
  async function save(status: "active" | "suspended") {
    try {
      await update.mutateAsync({
        id: account.id,
        role,
        status,
        ...(role === "management" && unit ? { management_unit_id: unit } : {}),
      });
      onClose();
    } catch {}
  }
  return (
    <AdminDrawer
      title={account.name}
      description={account.email}
      onClose={onClose}
      busy={update.isPending}
      footer={
        account.administrator ? (
          <Button variant="outline" onClick={onClose}>
            Hủy
          </Button>
        ) : (
          <>
            {account.status !== "suspended" && (
              <Button
                variant="outline"
                className="ops-admin-danger"
                disabled={update.isPending}
                onClick={() => setConfirming(true)}
              >
                Khóa truy cập
              </Button>
            )}
            <Button
              variant="outline"
              disabled={update.isPending}
              onClick={onClose}
            >
              Hủy
            </Button>
            <Button
              disabled={update.isPending}
              onClick={() => void save("active")}
            >
              {update.isPending
                ? "Đang lưu…"
                : account.status === "pending"
                  ? "Duyệt tài khoản"
                  : account.status === "suspended"
                    ? "Mở lại và lưu"
                    : "Lưu thay đổi"}
            </Button>
          </>
        )
      }
    >
      <div className="ops-admin-form">
        <p>
          <AdminBadge tone={toneOf(account)}>
            {STATUS[account.status] || account.status}
          </AdminBadge>
        </p>
        {account.administrator ? (
          <p className="ops-admin-muted">
            Quyền quản trị viên được quản lý riêng.
          </p>
        ) : (
          <>
            <label>
              Vai trò
              <AdminSelect
                label="Vai trò tài khoản"
                value={role}
                disabled={update.isPending}
                onChange={setRole}
                options={roleOptions}
              />
            </label>
            {role === "management" && (
              <>
                <UnitField value={unit} units={units} onChange={setUnit} />
                <p className="ops-admin-muted">
                  Đổi đơn vị sẽ chuyển tài khoản sang nhóm của đơn vị mới.
                </p>
              </>
            )}
          </>
        )}
        {account.apartment_scope && <p>{account.apartment_scope}</p>}
        {account.last_activity_at && (
          <p className="ops-admin-muted">
            Hoạt động gần nhất: {relativeTime(account.last_activity_at)}
          </p>
        )}
        {update.error && (
          <p role="alert" className="ops-admin-error">
            {update.error.message}
          </p>
        )}
        {!account.administrator && (
          <form
            className="ops-admin-form"
            aria-label="Đặt lại mật khẩu"
            onSubmit={(event) => {
              event.preventDefault();
              if (password.length >= 12)
                reset.mutate({ id: account.id, password });
            }}
          >
            <label>
              Đặt lại mật khẩu
              <Input
                aria-label="Mật khẩu mới"
                autoComplete="off"
                spellCheck={false}
                value={password}
                maxLength={128}
                disabled={reset.isPending}
                onChange={(event) => {
                  setPassword(event.target.value);
                  reset.reset();
                }}
              />
              <small>
                Ít nhất 12 ký tự. Người dùng bị đăng xuất khỏi mọi thiết bị.
              </small>
            </label>
            <div className="ops-admin-actions">
              <Button
                type="button"
                variant="outline"
                disabled={reset.isPending}
                onClick={() => {
                  setPassword(newPassword());
                  reset.reset();
                }}
              >
                Tạo mật khẩu
              </Button>
              <Button
                type="submit"
                disabled={password.length < 12 || reset.isPending}
              >
                {reset.isPending ? "Đang đặt lại…" : "Đặt lại mật khẩu"}
              </Button>
            </div>
            {reset.isSuccess && (
              <p role="status" className="ops-admin-success">
                Đã đặt lại mật khẩu. Gửi mật khẩu mới cho người dùng qua kênh
                riêng; các phiên đăng nhập cũ đã kết thúc.
              </p>
            )}
            {reset.error && (
              <p role="alert" className="ops-admin-error">
                {reset.error.message}
              </p>
            )}
          </form>
        )}
      </div>
      {confirming && (
        <AdminConfirm
          title={`Khóa ${account.name}?`}
          consequence="Tài khoản sẽ không thể đăng nhập. Các phiên đăng nhập hiện tại sẽ bị kết thúc."
          confirm="Khóa truy cập"
          busy={update.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void save("suspended")}
        />
      )}
    </AdminDrawer>
  );
}
