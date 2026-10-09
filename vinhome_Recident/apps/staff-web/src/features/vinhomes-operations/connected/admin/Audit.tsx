import { useState } from "react";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import {
  Download as IconDownload,
  Bot as IconRobot,
  Server as IconServer,
  UserRound as IconUser,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { tryClient } from "@/lib/client";
import { businessHeaders } from "@/lib/business-headers";
import {
  AdminBadge,
  AdminDrawer,
  AdminPage,
  AdminSearch,
  AdminSelect,
  AdminState,
  absoluteTime,
} from "./AdminUI";
import { filteredAuditOptions, type EnrichedAudit } from "./queries";
// What a person reads in the trail. Keys are the first word of an event ("visitor_pass.created" -> visitor_pass) and the
// kind of thing it was done to; each is something the domain records.
export const KIND: Record<string, string> = {
  access_card: "Thẻ ra vào",
  account: "Tài khoản",
  amenity_booking: "Đặt tiện ích",
  amenity_closure: "Lịch đóng tiện ích",
  announcement: "Thông báo chung",
  audit: "Nhật ký",
  audit_events: "Nhật ký",
  case: "Hồ sơ giao cho bên xử lý",
  delegation: "Quyền ngắn hạn",
  integration: "Kết nối bên ngoài",
  integration_case: "Hồ sơ giao cho bên xử lý",
  management_unit: "Đơn vị quản lý",
  plan: "Phương án xử lý",
  reception: "Lễ tân",
  reception_supervisor: "Lễ tân và bên xử lý",
  service_request: "Đơn dịch vụ",
  tenant_membership: "Tài khoản",
  ticket: "Yêu cầu",
  ticket_plan: "Phương án xử lý",
  user: "Tài khoản",
  visitor_pass: "Khách đến thăm",
};
export const EVENT: Record<string, string> = {
  "access_card.reported_lost": "Báo mất thẻ",
  "account.deleted": "Xóa tài khoản",
  "account.password_reset": "Đặt lại mật khẩu",
  "account.role_granted": "Cấp vai trò",
  "amenity_booking.created": "Đặt tiện ích",
  "amenity_booking.cancelled": "Hủy đặt tiện ích",
  "amenity_closure.created": "Đóng tiện ích để bảo trì",
  "announcement.drafted": "Soạn thông báo chung",
  "announcement.published": "Phát hành thông báo chung",
  "audit.exported": "Xuất nhật ký",
  "case.created": "Giao hồ sơ cho bên xử lý",
  "integration.delegation_issued": "Cấp quyền ngắn hạn cho agent",
  "management_unit.created": "Tạo đơn vị quản lý",
  "plan.presentation_updated": "Sửa cách trình bày phương án",
  "plan.proposed": "Đề xuất phương án",
  "reception.delegation_issued": "Lễ tân nhận quyền thay cư dân",
  "reception_supervisor.input_received": "Bên xử lý nhận yêu cầu",
  "reception_supervisor.result_received": "Bên xử lý trả kết quả",
  "service_request.drafted": "Soạn đơn dịch vụ",
  "service_request.submitted": "Gửi đơn dịch vụ",
  "service_request.transitioned": "Xử lý đơn dịch vụ",
  "service_request.cancelled": "Hủy đơn dịch vụ",
  "visitor_pass.created": "Đăng ký khách",
  "visitor_pass.approved": "Duyệt khách",
  "visitor_pass.rejected": "Từ chối khách",
  "visitor_pass.cancelled": "Hủy đăng ký khách",
};
export const eventLabel = (event: EnrichedAudit) =>
  EVENT[event.event_type] ||
  `Cập nhật ${KIND[event.event_type.split(".")[0]]?.toLowerCase() || "hệ thống"}`;
export const targetLabel = (event: EnrichedAudit) =>
  event.target_label && event.target_label !== event.target_type
    ? event.target_label
    : KIND[event.target_type] || "Hệ thống";
export function AuditActor({ event }: { event: EnrichedAudit }) {
  return (
    <span className="ops-admin-actor" data-kind={event.initiator_kind}>
      <span>
        {event.initiator_kind === "agent" ? (
          <IconRobot size={14} />
        ) : event.initiator_kind === "system" ? (
          <IconServer size={14} />
        ) : (
          <IconUser size={14} />
        )}
      </span>
      {event.actor ||
        (event.initiator_kind === "system" ? "Hệ thống" : "Người dùng")}
    </span>
  );
}
const vietnamDay = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export function AuditPage() {
  const [filters, setFilters] = useState({
    kind: "",
    from: "",
    to: "",
    actor: "",
    action: "",
    search: "",
    result: "",
  });
  const [selected, setSelected] = useState<EnrichedAudit>();
  const trail = useInfiniteQuery(filteredAuditOptions(filters));
  const events = trail.data?.pages.flatMap((page) => page.items) || [];
  const exported = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams({
        ...filters,
        from: filters.from || "1970-01-01",
        to: filters.to || vietnamDay(),
      });
      const response = await tryClient(
        `/api/business/admin/audit-events/export?${params}`,
        { headers: businessHeaders() },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : "Không xuất được nhật ký. Thử lại.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "nhat-ky.csv";
      link.click();
      URL.revokeObjectURL(url);
    },
  });
  const set = (key: keyof typeof filters, value: string) =>
    setFilters({ ...filters, [key]: value });
  return (
    <AdminPage
      title="Nhật ký"
      meta="Chỉ đọc, ghi lại mọi thao tác của người và agent"
    >
      <section className="ops-admin-panel">
        <div className="ops-admin-toolbar">
          <label className="ops-admin-muted">
            Từ ngày
            <Input
              aria-label="Nhật ký từ ngày"
              type="date"
              value={filters.from}
              max={filters.to || undefined}
              onChange={(event) => set("from", event.target.value)}
            />
          </label>
          <label className="ops-admin-muted">
            Đến ngày
            <Input
              aria-label="Nhật ký đến ngày"
              type="date"
              value={filters.to}
              min={filters.from || undefined}
              onChange={(event) => set("to", event.target.value)}
            />
          </label>
          <AdminSearch
            value={filters.actor}
            onChange={(value) => set("actor", value)}
            placeholder="Tác nhân"
          />
          <AdminSelect
            label="Loại đối tượng"
            value={filters.kind}
            onChange={(value) => set("kind", value)}
            options={[
              { value: "", label: "Đối tượng" },
              ...(trail.data?.pages[0]?.kinds || []).map((kind) => ({
                value: kind,
                label: KIND[kind] || kind,
              })),
            ]}
          />
          <AdminSelect
            label="Loại hành động"
            value={filters.action}
            onChange={(value) => set("action", value)}
            options={[
              { value: "", label: "Loại hành động" },
              ...(trail.data?.pages[0]?.actions || []).map((action) => ({
                value: action,
                label: EVENT[action] || action,
              })),
            ]}
          />
          <AdminSelect
            label="Kết quả"
            value={filters.result}
            onChange={(value) => set("result", value)}
            options={[
              { value: "", label: "Kết quả" },
              { value: "success", label: "Thành công" },
              { value: "failed", label: "Thất bại" },
              { value: "recorded", label: "Đã ghi nhận" },
            ]}
          />
          <AdminSearch
            value={filters.search}
            onChange={(value) => set("search", value)}
            placeholder="Tìm theo đối tượng"
          />
          <Button
            variant="ghost"
            className="ops-admin-export"
            disabled={exported.isPending}
            onClick={() => exported.mutate()}
          >
            <IconDownload />
            {exported.isPending ? "Đang xuất…" : "Xuất CSV"}
          </Button>
        </div>
        {exported.error && (
          <p role="alert" className="ops-admin-error px-4">
            {exported.error.message}
          </p>
        )}
        {trail.isPending || trail.error ? (
          <AdminState
            loading={trail.isPending}
            error={trail.error}
            onRetry={() => void trail.refetch()}
          />
        ) : events.length ? (
          <div className="ops-admin-table-wrap">
            <table className="ops-admin-table ops-admin-audit-table">
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>Tác nhân</th>
                  <th>Hành động</th>
                  <th>Đối tượng</th>
                  <th>Kết quả</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td className="ops-admin-muted">
                      {absoluteTime(event.created_at)}
                    </td>
                    <td>
                      <AuditActor event={event} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ops-admin-link"
                        onClick={() => setSelected(event)}
                      >
                        {eventLabel(event)}
                      </button>
                    </td>
                    <td>{targetLabel(event)}</td>
                    <td>
                      <AdminBadge
                        tone={
                          event.result === "failed"
                            ? "danger"
                            : event.result === "success"
                              ? "ok"
                              : "neutral"
                        }
                      >
                        {event.result === "failed"
                          ? "Thất bại"
                          : event.result === "success"
                            ? "Thành công"
                            : "Đã ghi nhận"}
                      </AdminBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <AdminState empty="Không có sự kiện trong bộ lọc này. Thử đổi khoảng ngày hoặc từ khóa." />
        )}
        {trail.hasNextPage && (
          <footer className="ops-admin-table-footer">
            <Button
              variant="outline"
              disabled={trail.isFetchingNextPage}
              onClick={() => void trail.fetchNextPage()}
            >
              {trail.isFetchingNextPage
                ? "Đang tải…"
                : "Xem các sự kiện cũ hơn"}
            </Button>
          </footer>
        )}
      </section>
      {selected && (
        <AdminDrawer
          title={eventLabel(selected)}
          description={absoluteTime(selected.created_at)}
          onClose={() => setSelected(undefined)}
        >
          <dl className="ops-admin-detail">
            <div>
              <dt>Tác nhân</dt>
              <dd>
                <AuditActor event={selected} />
              </dd>
            </div>
            <div>
              <dt>Đối tượng</dt>
              <dd>{targetLabel(selected)}</dd>
            </div>
            <div>
              <dt>Mã sự kiện</dt>
              <dd>{selected.event_type}</dd>
            </div>
            <div>
              <dt>Mã đối tượng</dt>
              <dd>{selected.target_id}</dd>
            </div>
            {Object.keys(selected.payload || {}).length > 0 && (
              <div>
                <dt>Chi tiết</dt>
                <dd>
                  <pre>{JSON.stringify(selected.payload, null, 2)}</pre>
                </dd>
              </div>
            )}
          </dl>
        </AdminDrawer>
      )}
    </AdminPage>
  );
}
