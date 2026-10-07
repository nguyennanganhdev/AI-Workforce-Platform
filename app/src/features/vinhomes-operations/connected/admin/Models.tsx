import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus as IconPlus, RefreshCw as IconRefresh } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ModelKeyDialog } from "../ModelKeys";
import { modelsQueryOptions, type RoleModel } from "@/lib/admin/queries";
import {
  AdminBadge,
  AdminConfirm,
  AdminDrawer,
  AdminPage,
  AdminSelect,
  AdminState,
  relativeTime,
} from "./AdminUI";
import {
  adminRequest,
  registryKey,
  registryOptions,
  type RegisteredModel,
} from "./queries";
export const ROLE: Record<RoleModel["role"], [string, string]> = {
  reception: ["Lễ tân", "Trả lời cư dân và lập yêu cầu"],
  supervisor: ["Supervisor", "Điều phối phiên và lập phương án"],
  specialist: ["Agent chuyên môn", "Mặc định cho agent mới của ban quản lý"],
  factory: ["Factory", "Soạn chỉ dẫn cho agent mới"],
  embedding: [
    "Tìm kiếm tri thức",
    "Tìm trong kho tri thức. Đổi model cần nhập lại kho",
  ],
};
export const PROVIDER: Record<string, string> = {
  openai: "OpenAI",
  google: "Google",
  deepseek: "DeepSeek",
  groq: "Groq",
  custom: "Máy chủ riêng",
};
export function modelStatus(model: RoleModel) {
  return !model.configured
    ? { label: "Chưa cấu hình", tone: "wait" as const }
    : model.running === false
      ? { label: "Dịch vụ không trả lời", tone: "danger" as const }
      : model.running === true
        ? { label: "Dịch vụ đang chạy", tone: "ok" as const }
        : { label: "Đã cấu hình", tone: "neutral" as const };
}
export function ModelsPage() {
  const queryClient = useQueryClient();
  const models = useQuery({ ...modelsQueryOptions(), refetchInterval: 30_000 });
  const registry = useQuery(registryOptions());
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState("");
  const [replacing, setReplacing] = useState<RegisteredModel>();
  const [removing, setRemoving] = useState<RegisteredModel>();
  const mutation = useMutation({
    mutationFn: async (action: {
      kind: "check" | "allow" | "default" | "remove";
      id: string;
      value?: boolean;
      role?: string;
    }) => {
      if (action.kind === "check")
        return adminRequest<{ ok: boolean; message: string }>(
          `/admin/model-registry/${action.id}/check`,
          { method: "POST" },
        );
      if (action.kind === "remove")
        return adminRequest(`/admin/model-registry/${action.id}`, {
          method: "DELETE",
        });
      if (action.kind === "allow")
        return adminRequest(`/admin/model-registry/${action.id}`, {
          method: "PATCH",
          body: { allowed: action.value },
        });
      return adminRequest(`/admin/model-defaults/${action.role}`, {
        method: action.id ? "PUT" : "DELETE",
        ...(action.id ? { body: { model_id: action.id } } : {}),
      });
    },
    onSuccess: async (result, action) => {
      setNotice(
        action.kind === "check"
          ? (result as { message: string }).message
          : action.kind === "remove"
            ? "Đã xóa model"
            : action.kind === "allow"
            ? "Đã lưu quyền sử dụng model"
            : action.id
              ? "Đã lưu model cho vai trò"
              : "Vai trò đã quay lại model của bản triển khai",
      );
      await queryClient.invalidateQueries({ queryKey: registryKey });
      await queryClient.invalidateQueries({ queryKey: ["allowed-models"] });
      await models.refetch();
      setRemoving(undefined);
    },
  });
  const items = registry.data?.items || [];
  const defaults = registry.data?.defaults || [];
  return (
    <AdminPage
      title="Model"
      action={
        <div className="ops-admin-actions">
          <Button
            variant="outline"
            disabled={models.isFetching || registry.isFetching}
            onClick={() => {
              void models.refetch();
              void registry.refetch();
            }}
          >
            <IconRefresh />
            Kiểm tra lại
          </Button>
          <Button onClick={() => setCreating(true)}>
            <IconPlus />
            Thêm model
          </Button>
        </div>
      }
    >
      {notice && (
        <p className="ops-admin-success" role="status">
          {notice}
        </p>
      )}
      {mutation.error && (
        <p className="ops-admin-error" role="alert">
          {mutation.error.message}
        </p>
      )}
      <section className="ops-admin-panel">
        <header className="ops-admin-panel-title">
          <h2>Model đã đăng ký</h2>
          <span>Ban quản lý chỉ chọn được model đang bật cho đơn vị</span>
        </header>
        {registry.isPending || registry.error ? (
          <AdminState
            loading={registry.isPending}
            error={registry.error}
            onRetry={() => void registry.refetch()}
          />
        ) : items.length ? (
          <div className="ops-admin-table-wrap">
            <table className="ops-admin-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Nhà cung cấp</th>
                  <th>Cho phép đơn vị dùng</th>
                  <th>Mặc định cho vai trò</th>
                  <th>Trạng thái</th>
                  <th>Độ trễ lần kiểm tra</th>
                  <th>
                    <span className="sr-only">Kiểm tra</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((model) => (
                  <tr key={model.id}>
                    <td>
                      <strong>{model.name}</strong>
                      <small className="block ops-admin-muted">
                        {model.credential_source === "key"
                          ? `Khóa nhập trên giao diện ${model.credential_hint || ""}`
                          : `Biến ${model.credential_env}`}
                        {model.workspace_name
                          ? `, riêng của ${model.workspace_name}`
                          : ""}
                      </small>
                      {model.kind === "embedding" && (
                        <small className="block ops-admin-muted">
                          Tìm kiếm tri thức
                          {model.dimension ? `, ${model.dimension} chiều` : ""}
                        </small>
                      )}
                    </td>
                    <td>{PROVIDER[model.provider] || model.provider}</td>
                    <td>
                      <Switch
                        aria-label={`Cho phép đơn vị dùng ${model.name}`}
                        checked={model.allowed}
                        disabled={
                          model.kind !== "chat" ||
                          model.check_status !== "ok" ||
                          !!model.workspace_id ||
                          mutation.isPending
                        }
                        onCheckedChange={(allowed) =>
                          mutation.mutate({
                            kind: "allow",
                            id: model.id,
                            value: allowed,
                          })
                        }
                      />
                    </td>
                    <td>
                      {defaults
                        .filter((item) => item.model_id === model.id)
                        .map(
                          (item) =>
                            ROLE[item.role as RoleModel["role"]]?.[0] ||
                            item.role,
                        )
                        .join(", ")}
                    </td>
                    <td>
                      <AdminBadge
                        tone={
                          model.check_status === "ok"
                            ? "ok"
                            : model.check_status === "error"
                              ? "danger"
                              : "neutral"
                        }
                      >
                        {model.check_status === "ok"
                          ? "Đã kiểm tra"
                          : model.check_status === "error"
                            ? "Không trả lời"
                            : "Chưa kiểm tra"}
                      </AdminBadge>
                    </td>
                    <td>
                      {model.latency_ms !== null
                        ? `${(model.latency_ms / 1000).toLocaleString("vi-VN")} giây`
                        : ""}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        aria-label={`Kiểm tra ${model.name}`}
                        disabled={mutation.isPending}
                        onClick={() =>
                          mutation.mutate({ kind: "check", id: model.id })
                        }
                      >
                        Kiểm tra
                      </Button>
                      {model.credential_source === "key" && (
                        <Button
                          variant="ghost"
                          disabled={mutation.isPending}
                          onClick={() => setReplacing(model)}
                        >
                          Thay khóa
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        className="ops-admin-danger"
                        disabled={mutation.isPending}
                        onClick={() => setRemoving(model)}
                      >
                        Xóa
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <AdminState empty="Chưa có model đã đăng ký. Thêm model và kiểm tra trước khi cấp cho đơn vị." />
        )}
      </section>
      <section className="ops-admin-panel">
        <header className="ops-admin-panel-title">
          <h2>Model theo vai trò hệ thống</h2>
        </header>
        {models.isPending || models.error ? (
          <AdminState
            loading={models.isPending}
            error={models.error}
            onRetry={() => void models.refetch()}
          />
        ) : (
          <div className="ops-admin-table-wrap">
            <table className="ops-admin-table">
              <thead>
                <tr>
                  <th>Vai trò</th>
                  <th>Việc đảm nhận</th>
                  <th>Model đã chọn</th>
                  <th>Dịch vụ đang báo cáo</th>
                  <th>Trạng thái dịch vụ</th>
                </tr>
              </thead>
              <tbody>
                {models.data?.map((model) => {
                  const saved = defaults.find(
                    (item) => item.role === model.role,
                  );
                  const choices = items.filter(
                    (item) =>
                      item.kind ===
                        (model.role === "embedding" ? "embedding" : "chat") &&
                      item.check_status === "ok" &&
                      !item.workspace_id &&
                      (model.role !== "specialist" || item.allowed),
                  );
                  return (
                    <tr key={model.role}>
                      <td>
                        <strong>{ROLE[model.role][0]}</strong>
                      </td>
                      <td>{ROLE[model.role][1]}</td>
                      <td>
                        <AdminSelect
                          label={`Model cho ${ROLE[model.role][0]}`}
                          value={saved?.model_id || ""}
                          disabled={mutation.isPending}
                          onChange={(id) => {
                            mutation.mutate({
                              kind: "default",
                              id,
                              role: model.role,
                            });
                          }}
                          options={[
                            { value: "", label: "Theo bản triển khai" },
                            ...choices.map((item) => ({
                              value: item.id,
                              label: item.name,
                            })),
                          ]}
                        />
                        {saved && (
                          <small className="block ops-admin-muted">
                            Lưu {relativeTime(saved.updated_at).toLowerCase()}
                          </small>
                        )}
                      </td>
                      <td>
                        {model.model || (
                          <span className="ops-admin-muted">
                            {model.configured
                              ? "Dịch vụ chưa báo tên model"
                              : "Chưa cấu hình"}
                          </span>
                        )}
                      </td>
                      <td>
                        <AdminBadge tone={modelStatus(model).tone}>
                          {modelStatus(model).label}
                        </AdminBadge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {creating && <RegisterModel onClose={() => setCreating(false)} />}
      {replacing && (
        <ModelKeyDialog
          title={`Thay khóa của ${replacing.name}`}
          path={`/admin/model-registry/${replacing.id}/credential`}
          onClose={() => setReplacing(undefined)}
          onDone={async () => {
            setNotice("Đã thay khóa API. Khóa mới đã trả lời được.");
            await queryClient.invalidateQueries({ queryKey: registryKey });
          }}
        />
      )}
      {removing && (
        <AdminConfirm
          title={`Xóa ${removing.name}?`}
          consequence="Chỉ xóa được model không còn vai trò hoặc agent nào dùng. Khóa đã lưu bị xóa theo."
          confirm="Xóa model"
          busy={mutation.isPending}
          onCancel={() => setRemoving(undefined)}
          onConfirm={() => mutation.mutate({ kind: "remove", id: removing.id })}
        />
      )}
    </AdminPage>
  );
}
function RegisterModel({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    provider: "openai",
    kind: "chat",
    source: "key",
    api_key: "",
    credential_env: "OPENAI_API_KEY",
    base_url_env: "",
    dimension: "",
  });
  const entered = form.source === "key";
  const create = useMutation({
    mutationFn: () =>
      adminRequest("/admin/model-registry", {
        method: "POST",
        body: {
          name: form.name.trim(),
          provider: form.provider,
          kind: entered ? "chat" : form.kind,
          ...(entered
            ? { api_key: form.api_key.trim() }
            : {
                credential_env: form.credential_env.trim(),
                base_url_env: form.base_url_env.trim() || null,
              }),
          ...(!entered && form.kind === "embedding" && form.dimension
            ? { dimension: Number(form.dimension) }
            : {}),
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: registryKey });
      onClose();
    },
  });
  return (
    <AdminDrawer
      title="Thêm model"
      description="Khóa API được mã hóa trên máy chủ và không hiển thị lại. Sau khi thêm, bấm Kiểm tra rồi cho phép đơn vị dùng."
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
            disabled={
              !form.name.trim() ||
              (entered
                ? form.api_key.trim().length < 8
                : !form.credential_env.trim()) ||
              create.isPending
            }
            onClick={() => create.mutate()}
          >
            Thêm model
          </Button>
        </>
      }
    >
      <div className="ops-admin-form">
        <label>
          Tên model
          <Input
            aria-label="Tên model"
            placeholder="Tên model do nhà cung cấp cấp"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>
        <label>
          Cách lấy khóa
          <AdminSelect
            label="Cách lấy khóa API"
            value={form.source}
            onChange={(source) =>
              setForm({
                ...form,
                source,
                provider:
                  source === "key" && form.provider === "custom"
                    ? "openai"
                    : form.provider,
              })
            }
            options={[
              { value: "key", label: "Nhập khóa API" },
              { value: "env", label: "Biến môi trường của bản triển khai" },
            ]}
          />
        </label>
        <label>
          Nhà cung cấp
          <AdminSelect
            label="Nhà cung cấp"
            value={form.provider}
            onChange={(provider) => setForm({ ...form, provider })}
            options={Object.entries(PROVIDER)
              .filter(([value]) => !entered || value !== "custom")
              .map(([value, label]) => ({
                value,
                label,
              }))}
          />
        </label>
        {entered ? (
          <label>
            Khóa API
            <Input
              aria-label="Khóa API"
              type="password"
              autoComplete="off"
              value={form.api_key}
              onChange={(event) =>
                setForm({ ...form, api_key: event.target.value })
              }
            />
            <small>
              Dùng địa chỉ chính thức của nhà cung cấp. Máy chủ riêng cần khai
              báo bằng biến môi trường.
            </small>
          </label>
        ) : (
        <>
        <label>
          Loại model
          <AdminSelect
            label="Loại model"
            value={form.kind}
            onChange={(kind) => setForm({ ...form, kind })}
            options={[
              { value: "chat", label: "Trả lời và điều phối" },
              { value: "embedding", label: "Tìm kiếm tri thức" },
            ]}
          />
        </label>
        <label>
          Biến khóa API
          <Input
            aria-label="Biến khóa API"
            value={form.credential_env}
            onChange={(event) =>
              setForm({ ...form, credential_env: event.target.value })
            }
          />
        </label>
        <label>
          Biến địa chỉ API riêng
          <Input
            aria-label="Biến địa chỉ API riêng"
            placeholder="Để trống để dùng địa chỉ mặc định"
            value={form.base_url_env}
            onChange={(event) =>
              setForm({ ...form, base_url_env: event.target.value })
            }
          />
        </label>
        {form.kind === "embedding" && (
          <label>
            Số chiều
            <Input
              aria-label="Số chiều"
              type="number"
              min={1}
              value={form.dimension}
              onChange={(event) =>
                setForm({ ...form, dimension: event.target.value })
              }
            />
            <small>Kho tri thức hiện tại dùng 1536 chiều.</small>
          </label>
        )}
        </>
        )}
        {create.error && (
          <p role="alert" className="ops-admin-error">
            {create.error.message}
          </p>
        )}
      </div>
    </AdminDrawer>
  );
}
