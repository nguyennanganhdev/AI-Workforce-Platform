import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Users as IconUsers } from "lucide-react";
import { AdminBadge, AdminPage, AdminState } from "./AdminUI";
import { AuditActor, eventLabel, targetLabel } from "./Audit";
import { filteredAuditOptions, overviewOptions } from "./queries";
export function AdminOverviewPage() {
  const summary = useQuery(overviewOptions());
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
  const recent = audit.data?.pages[0]?.items.slice(0, 10) || [];
  const attention = figures?.pending_accounts || 0;
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
                to: "/operations/kanban",
                tone: "neutral",
                note: "Trên toàn hệ thống",
              },
              {
                title: "Quá hạn",
                value: figures.overdue_tickets,
                to: "/operations/kanban?overdue=true",
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
          {summary.isPending ? (
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
              {!attention && !summary.error && (
                <AdminState empty="Không còn việc nào chờ bạn." />
              )}
            </>
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
