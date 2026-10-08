import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  Cpu as IconCpu,
  Plug as IconPlugConnected,
  Users as IconUsers,
} from "lucide-react";
import { modelsQueryOptions } from "@/lib/admin/queries";
import { connectionsQueryOptions } from "@/lib/connections/queries";
import { AdminBadge, AdminPage, AdminState, relativeTime } from "./AdminUI";
import { AuditActor, eventLabel, targetLabel } from "./Audit";
import { modelStatus, ROLE } from "./Models";
import { filteredAuditOptions, overviewOptions } from "./queries";
export function AdminOverviewPage() {
  const summary = useQuery(overviewOptions());
  const models = useQuery({ ...modelsQueryOptions(), refetchInterval: 30_000 });
  const connections = useQuery(connectionsQueryOptions());
  const audit = useInfiniteQuery(
    filteredAuditOptions({
      kind: "",
      from: "",
      to: "",
      actor: "",
      action: "",
      search: "",
      result: "",
    }),
  );
  const figures = summary.data;
  const chart = figures?.requests_per_day || [];
  const highest = Math.max(1, ...chart.map((day) => day.count));
  const unconfigured = models.data?.filter((model) => !model.configured) || [];
  const recent = audit.data?.pages[0]?.items.slice(0, 10) || [];
  const connectionItems = connections.data?.items || [];
  const attention = (figures?.pending_accounts || 0) + unconfigured.length;
  return (
    <AdminPage
      title="Tổng quan"
      meta={new Intl.DateTimeFormat("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date())}
    >
      {summary.isPending || summary.error ? (
        <AdminState
          loading={summary.isPending}
          error={summary.error}
          onRetry={() => void summary.refetch()}
        />
      ) : (
        figures && (
          <div className="ops-admin-metrics">
            {[
              {
                title: "Yêu cầu đang mở",
                value: figures.open_tickets,
                to: "/operations/team",
                tone: "neutral",
                note: "Trên toàn hệ thống",
              },
              {
                title: "Quá hạn",
                value: figures.overdue_tickets,
                to: "/operations/team?overdue=true",
                tone: "danger",
                note: "Yêu cầu đã quá hạn xử lý",
              },
              {
                title: "Tài khoản chờ duyệt",
                value: figures.pending_accounts,
                to: "/operations/accounts",
                tone: "wait",
                note: "Cần bạn quyết định",
              },
              {
                title: "Kết nối mới",
                value: figures.new_connections,
                to: "/operations/connections",
                tone: "neutral",
                note: "Được thêm trong 24 giờ qua",
              },
            ].map((figure) => (
              <a
                className="ops-admin-metric"
                data-tone={figure.tone}
                href={figure.to}
                key={figure.title}
              >
                <span>{figure.title}</span>
                <strong>{figure.value}</strong>
                <small>{figure.note}</small>
              </a>
            ))}
          </div>
        )
      )}
      <div className="ops-admin-grid">
        <section className="ops-admin-panel">
          <header className="ops-admin-panel-title">
            <h2>
              Cần bạn xử lý{" "}
              {attention > 0 && (
                <AdminBadge tone="wait">{attention}</AdminBadge>
              )}
            </h2>
          </header>
          {summary.isPending || models.isPending ? (
            <AdminState loading />
          ) : (
            <>
              {figures?.pending_accounts_preview.map((account) => (
                <div key={account.email} className="ops-admin-attention-row">
                  <span className="ops-admin-tile">
                    <IconUsers size={16} />
                  </span>
                  <div>
                    <strong>Duyệt tài khoản {account.name}</strong>
                    <p>{account.email}</p>
                  </div>
                  <a className="ops-admin-link" href="/operations/accounts">
                    Xem
                  </a>
                </div>
              ))}
              {unconfigured.map((model) => (
                <div key={model.role} className="ops-admin-attention-row">
                  <span className="ops-admin-tile">
                    <IconCpu size={16} />
                  </span>
                  <div>
                    <strong>Chọn model cho {ROLE[model.role][0]}</strong>
                    <p>{ROLE[model.role][1]}</p>
                  </div>
                  <a className="ops-admin-link" href="/operations/models">
                    Chọn
                  </a>
                </div>
              ))}
              {!attention && !summary.error && !models.error && (
                <AdminState empty="Không còn việc nào chờ bạn." />
              )}
            </>
          )}
        </section>
        <section className="ops-admin-panel">
          <header className="ops-admin-panel-title">
            <h2>Sức khỏe hệ thống</h2>
            <button
              type="button"
              className="ops-admin-link"
              onClick={() => {
                void models.refetch();
                void connections.refetch();
              }}
            >
              Kiểm tra lại
            </button>
          </header>
          {models.isPending || models.error ? (
            <AdminState
              loading={models.isPending}
              error={models.error}
              onRetry={() => void models.refetch()}
            />
          ) : (
            models.data?.map((model) => (
              <div className="ops-admin-health-row" key={model.role}>
                <IconCpu size={16} />
                <strong>{ROLE[model.role][0]}</strong>
                {model.model && <small>{model.model}</small>}
                <AdminBadge tone={modelStatus(model).tone}>
                  {modelStatus(model).label}
                </AdminBadge>
              </div>
            ))
          )}
          {connections.isPending || connections.error ? (
            <AdminState
              loading={connections.isPending}
              error={connections.error}
              onRetry={() => void connections.refetch()}
            />
          ) : (
            connectionItems.map((connection) => {
              const status = (
                connection as typeof connection & { status?: string }
              ).status;
              return (
                <div className="ops-admin-health-row" key={connection.id}>
                  <IconPlugConnected size={16} />
                  <strong>{connection.title}</strong>
                  <AdminBadge
                    tone={
                      status === "suspended" || connection.last_error
                        ? "danger"
                        : status === "pending"
                          ? "wait"
                          : connection.tools_refreshed_at
                            ? "ok"
                            : "neutral"
                    }
                  >
                    {status === "suspended"
                      ? "Đã dừng"
                      : status === "pending"
                        ? "Chờ duyệt"
                        : connection.last_error
                          ? "Mất kết nối"
                          : connection.tools_refreshed_at
                            ? "Đã kết nối"
                            : "Chưa kiểm tra"}
                  </AdminBadge>
                  {connection.tools_refreshed_at && (
                    <small>{relativeTime(connection.tools_refreshed_at)}</small>
                  )}
                </div>
              );
            })
          )}
        </section>
        <section className="ops-admin-panel">
          <header className="ops-admin-panel-title">
            <h2>Yêu cầu mới theo ngày</h2>
            <span>14 ngày qua</span>
          </header>
          {summary.isPending || summary.error ? (
            <AdminState
              loading={summary.isPending}
              error={summary.error}
              onRetry={() => void summary.refetch()}
            />
          ) : (
            <>
              <div
                className="ops-admin-chart"
                role="img"
                aria-label={chart
                  .map((day) => `${day.date}: ${day.count} yêu cầu`)
                  .join("; ")}
              >
                {chart.map((day) => (
                  <div
                    key={day.date}
                    title={`${day.date}: ${day.count} yêu cầu`}
                  >
                    <span
                      style={{ height: `${(day.count / highest) * 100}%` }}
                    />
                  </div>
                ))}
              </div>
              <div className="ops-admin-chart-labels">
                <span>
                  {chart[0]?.date?.slice(5).split("-").reverse().join("/")}
                </span>
                <span>Hôm nay, {chart.at(-1)?.count || 0} yêu cầu</span>
              </div>
            </>
          )}
        </section>
        <section className="ops-admin-panel">
          <header className="ops-admin-panel-title">
            <h2>Nhật ký mới nhất</h2>
            <a className="ops-admin-link" href="/operations/audit">
              Xem tất cả
            </a>
          </header>
          {audit.isPending || audit.error ? (
            <AdminState
              loading={audit.isPending}
              error={audit.error}
              onRetry={() => void audit.refetch()}
            />
          ) : recent.length ? (
            recent.map((event) => (
              <div className="ops-admin-health-row" key={event.id}>
                <small>
                  {new Intl.DateTimeFormat("vi-VN", {
                    timeZone: "Asia/Ho_Chi_Minh",
                    hour: "2-digit",
                    minute: "2-digit",
                  }).format(new Date(event.created_at))}
                </small>
                <AuditActor event={event} />
                <span>
                  {eventLabel(event)}{" "}
                  <span className="ops-admin-muted">{targetLabel(event)}</span>
                </span>
              </div>
            ))
          ) : (
            <AdminState empty="Chưa có sự kiện được ghi nhận." />
          )}
        </section>
      </div>
    </AdminPage>
  );
}
