import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ellipsis as IconDots,
  Plug as IconPlugConnected,
  Plus as IconPlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  connectionsQueryOptions,
  connectionKeys,
  type Connection,
} from "@/lib/connections/queries";
import { checkConnectionMutationOptions } from "@/lib/connections/mutations";
import { NewConnection, ConnectionEditor } from "../Connections";
import {
  AdminBadge,
  AdminConfirm,
  AdminPage,
  AdminSearch,
  AdminSelect,
  AdminState,
  relativeTime,
} from "./AdminUI";
import { adminRequest } from "./queries";
type RegistryConnection = Connection & {
  created_at?: string;
  added_by_name?: string | null;
  status?: string;
  usage_agents?: { id: string; name: string }[];
  tools: (Connection["tools"][number] & { effect?: string })[];
};
const newConnection = (connection: RegistryConnection) =>
  !!connection.created_at &&
  Date.now() - Date.parse(connection.created_at) < 86_400_000;
export function AdminConnectionsPage() {
  const queryClient = useQueryClient();
  const connections = useQuery(connectionsQueryOptions());
  const policy = useQuery({
    queryKey: ["admin", "connection-policy"],
    queryFn: () =>
      adminRequest<{ require_approval: boolean }>("/admin/connections/policy"),
  });
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState("");
  const [suspending, setSuspending] = useState<RegistryConnection>();
  const [text, setText] = useState("");
  const [tab, setTab] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [notice, setNotice] = useState("");
  const check = useMutation(checkConnectionMutationOptions(queryClient));
  const status = useMutation({
    mutationFn: (body: { id: string; status: string }) =>
      adminRequest(`/admin/connections/${body.id}/status`, {
        method: "PATCH",
        body: {
          status: body.status,
          reason:
            body.status === "suspended"
              ? "Quản trị viên tạm ngưng từ trang Kết nối"
              : "",
        },
      }),
    onSuccess: async (_, body) => {
      setNotice(
        body.status === "active"
          ? "Đã kích hoạt kết nối"
          : "Đã tạm ngưng kết nối",
      );
      setSuspending(undefined);
      await queryClient.invalidateQueries({ queryKey: connectionKeys.all });
    },
  });
  const switchPolicy = useMutation({
    mutationFn: (require_approval: boolean) =>
      adminRequest("/admin/connections/policy", {
        method: "PUT",
        body: { require_approval },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["admin", "connection-policy"],
      }),
  });
  const items: RegistryConnection[] = connections.data?.items || [];
  const recent = items.filter(newConnection);
  const errors = items.filter(
    (connection) => connection.last_error || connection.status === "suspended",
  );
  const needle = text.trim().toLowerCase();
  const shown = items.filter(
    (connection) =>
      (!needle || connection.title.toLowerCase().includes(needle)) &&
      (!workspace || connection.workspace_id === workspace) &&
      (!tab ||
        (tab === "new"
          ? newConnection(connection)
          : connection.last_error || connection.status === "suspended")),
  );
  const open = items.find((connection) => connection.id === selected);
  const toolCounts = (connection: RegistryConnection) => {
    const reads = connection.tools.filter(
      (tool) => tool.effect !== "write",
    ).length;
    const writes = connection.tools.filter(
      (tool) => tool.effect === "write",
    ).length;
    return (
      <>
        {reads} đọc
        {writes > 0 && (
          <>
            , <span style={{ color: "var(--wait)" }}>{writes} ghi</span>
          </>
        )}
      </>
    );
  };
  return (
    <AdminPage
      title="Kết nối"
      meta={
        connections.data
          ? `${items.length} kết nối ngoài trên toàn hệ thống`
          : undefined
      }
      action={
        <Button onClick={() => setCreating(true)}>
          <IconPlus />
          Thêm kết nối
        </Button>
      }
    >
      {recent.length > 0 && (
        <section className="ops-admin-panel">
          <header className="ops-admin-panel-title">
            <h2>{recent.length} kết nối mới trong 24 giờ qua</h2>
          </header>
          {recent.map((connection) => (
            <div key={connection.id} className="ops-admin-pending-row">
              <span className="ops-admin-tile">
                <IconPlugConnected size={16} />
              </span>
              <div>
                <p>{connection.title}</p>
                <small>
                  {connection.workspace || "Nền tảng"}
                  {connection.added_by_name
                    ? `, do ${connection.added_by_name} thêm`
                    : ""}
                </small>
              </div>
              <span className="ops-admin-muted">
                Cho phép {toolCounts(connection)}
              </span>
              <div className="ops-admin-actions">
                <Button
                  variant="outline"
                  onClick={() => setSelected(connection.id)}
                >
                  Xem chi tiết
                </Button>
                {connection.status !== "suspended" && (
                  <Button
                    variant="outline"
                    className="ops-admin-danger"
                    onClick={() => setSuspending(connection)}
                  >
                    Tạm ngưng
                  </Button>
                )}
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
      {(status.error || switchPolicy.error || check.error) && (
        <p role="alert" className="ops-admin-error">
          {(status.error || switchPolicy.error || check.error)?.message}
        </p>
      )}
      <section className="ops-admin-panel">
        <div className="ops-admin-toolbar">
          <div className="ops-admin-tabs" aria-label="Trạng thái kết nối">
            {[
              ["", "Tất cả", items.length],
              ["new", "Mới thêm", recent.length],
              ["error", "Có lỗi", errors.length],
            ].map(([value, label, count]) => (
              <button
                key={value}
                type="button"
                aria-pressed={tab === value}
                onClick={() => setTab(String(value))}
              >
                {label}
                <span>{count}</span>
              </button>
            ))}
          </div>
          <AdminSearch
            value={text}
            onChange={setText}
            placeholder="Tìm theo tên kết nối"
          />
          <AdminSelect
            label="Đơn vị"
            value={workspace}
            onChange={setWorkspace}
            options={[
              { value: "", label: "Đơn vị" },
              ...(connections.data?.workspaces || []).map((item) => ({
                value: item.id,
                label: item.name,
              })),
            ]}
          />
          {policy.data && (
            <label className="ops-admin-actions ml-auto ops-admin-muted">
              Kết nối mới cần bạn duyệt
              <Switch
                aria-label="Kết nối mới cần bạn duyệt"
                checked={policy.data.require_approval}
                disabled={switchPolicy.isPending}
                onCheckedChange={(value) => switchPolicy.mutate(value)}
              />
            </label>
          )}
        </div>
        {connections.isPending || connections.error ? (
          <AdminState
            loading={connections.isPending}
            error={connections.error}
            onRetry={() => void connections.refetch()}
          />
        ) : shown.length ? (
          <div className="ops-admin-table-wrap">
            <table className="ops-admin-table">
              <thead>
                <tr>
                  <th>Tên</th>
                  <th>Thuộc về</th>
                  <th>Người thêm</th>
                  <th>Công cụ</th>
                  <th>Đang dùng bởi</th>
                  <th>Trạng thái</th>
                  <th>Kiểm tra lần cuối</th>
                  <th>
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((connection) => (
                  <tr key={connection.id}>
                    <td>
                      <div className="ops-admin-row-title">
                        <span className="ops-admin-tile">
                          <IconPlugConnected size={16} />
                        </span>
                        <button
                          type="button"
                          onClick={() => setSelected(connection.id)}
                        >
                          {connection.title}
                          {newConnection(connection) && <small>Mới</small>}
                        </button>
                      </div>
                    </td>
                    <td>{connection.workspace || "Nền tảng"}</td>
                    <td>{connection.added_by_name}</td>
                    <td>{toolCounts(connection)}</td>
                    <td>
                      {connection.usage_agents?.length
                        ? `${connection.usage_agents.length} agent`
                        : "Chưa dùng"}
                    </td>
                    <td>
                      <AdminBadge
                        tone={
                          connection.status === "suspended" ||
                          connection.last_error
                            ? "danger"
                            : connection.status === "pending"
                              ? "wait"
                              : connection.tools_refreshed_at
                                ? "ok"
                                : "neutral"
                        }
                      >
                        {connection.status === "suspended"
                          ? "Đã dừng"
                          : connection.status === "pending"
                            ? "Chờ duyệt"
                            : connection.last_error
                              ? "Mất kết nối"
                              : connection.tools_refreshed_at
                                ? "Đã kết nối"
                                : "Chưa kiểm tra"}
                      </AdminBadge>
                    </td>
                    <td className="ops-admin-muted">
                      {connection.tools_refreshed_at
                        ? relativeTime(connection.tools_refreshed_at)
                        : ""}
                    </td>
                    <td>
                      <div className="ops-admin-actions">
                        <Button
                          variant="ghost"
                          disabled={check.isPending}
                          onClick={() => check.mutate(connection.id)}
                        >
                          Kiểm tra
                        </Button>
                        {connection.status === "active" ||
                        !connection.status ? (
                          <Button
                            variant="ghost"
                            className="ops-admin-danger"
                            onClick={() => setSuspending(connection)}
                          >
                            Tạm ngưng
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            disabled={status.isPending}
                            onClick={() =>
                              status.mutate({
                                id: connection.id,
                                status: "active",
                              })
                            }
                          >
                            {connection.status === "pending"
                              ? "Duyệt"
                              : "Kích hoạt"}
                          </Button>
                        )}
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={`Chi tiết ${connection.title}`}
                          title={`Chi tiết ${connection.title}`}
                          onClick={() => setSelected(connection.id)}
                        >
                          <IconDots />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <AdminState empty="Chưa có kết nối phù hợp. Thêm kết nối hoặc đổi bộ lọc." />
        )}
      </section>
      {creating && (
        <NewConnection
          workspaces={connections.data?.workspaces || []}
          onClose={(id) => {
            setCreating(false);
            if (id) setSelected(id);
          }}
        />
      )}
      {open && (
        <ConnectionEditor
          key={open.id}
          connection={open}
          onClose={() => setSelected("")}
        />
      )}{" "}
      {suspending && (
        <AdminConfirm
          title={`Tạm ngưng ${suspending.title}?`}
          consequence="Agent sẽ không gọi được các công cụ của kết nối này. Các phiên đang dùng nguồn ngoài có thể bị gián đoạn."
          confirm="Tạm ngưng kết nối"
          busy={status.isPending}
          onCancel={() => setSuspending(undefined)}
          onConfirm={() =>
            status.mutate({ id: suspending.id, status: "suspended" })
          }
        />
      )}
    </AdminPage>
  );
}
