import {
  IconArrowUpRight,
  IconBell,
  IconBuildingCommunity,
  IconChevronRight,
  IconClipboardList,
  IconInfoCircle,
  IconMapPin,
  IconMessageCircle,
  IconSwimming,
  IconBarbell,
  IconTrees,
  IconUser,
  IconHome,
} from "@tabler/icons-react";
import { Neighborhood } from "../../components/Illustrations";
import { resident } from "../../mocks/seed";
import { dateLabel } from "../requests/Requests";
import type {
  RequestStatus,
  ResidentConversation,
  ResidentRequest,
} from "../../services/types";
import type { Profile as ResidentProfile } from "../../services/resident-api";
import { exitResidentPreview } from "../auth/demo-access";

export type UtilityPage =
  | "utilities"
  | "requests"
  | "notifications"
  | "profile"
  | "building"
  | "amenities";

export function Utilities({
  onNavigate,
  pending,
}: {
  onNavigate: (page: UtilityPage) => void;
  pending: number;
}) {
  const items = [
    {
      page: "requests",
      icon: IconClipboardList,
      label: "Yêu cầu của tôi",
      sub: "Theo dõi và xác nhận kết quả",
      color: "blue",
      badge: pending,
    },
    {
      page: "notifications",
      icon: IconBell,
      label: "Thông báo",
      sub: "Cập nhật dành cho căn hộ của bạn",
      color: "orange",
    },
    {
      page: "building",
      icon: IconBuildingCommunity,
      label: "Thông tin tòa nhà",
      sub: "Hướng dẫn và Ban quản lý",
      color: "teal",
    },
    {
      page: "profile",
      icon: IconUser,
      label: "Tài khoản & căn hộ",
      sub: "Không gian sống của bạn",
      color: "coral",
    },
  ] as const;
  return (
    <div className="page-section utilities-page">
      <div className="utility-hero">
        <div>
          <span className="eyebrow">SỐNG THẢNH THƠI HƠN</span>
          <h2>
            Mọi tiện ích.
            <br />
            Một chạm là tới.
          </h2>
          <p>Những điều nhỏ cho một ngày dễ chịu.</p>
        </div>
        <Neighborhood />
      </div>
      <div className="section-heading">
        <h3>Dành cho bạn</h3>
        <span className="small muted">Thật đơn giản</span>
      </div>
      <div className="menu-card">
        {items.map(({ page, icon: Icon, label, sub, color, ...rest }) => (
          <button key={page} onClick={() => onNavigate(page)}>
            <span className={`icon-tile ${color}`}>
              <Icon size={23} stroke={1.7} />
            </span>
            <span className="menu-copy">
              <strong>{label}</strong>
              <small>{sub}</small>
            </span>
            {"badge" in rest && rest.badge > 0 && (
              <span className="count-badge">{rest.badge}</span>
            )}
            <IconChevronRight size={18} className="muted shrink" />
          </button>
        ))}
      </div>
      <div className="section-heading">
        <h3>Khám phá nơi bạn sống</h3>
        <span className="icon-tile tiny teal">
          <IconTrees size={18} />
        </span>
      </div>
      <div className="amenity-grid">
        {[
          { icon: IconSwimming, label: "Bể bơi", color: "blue" },
          { icon: IconBarbell, label: "Phòng tập", color: "coral" },
          { icon: IconTrees, label: "Công viên", color: "teal" },
        ].map(({ icon: Icon, label, color }) => (
          <button
            key={label}
            className={`amenity ${color}`}
            onClick={() => onNavigate("amenities")}
          >
            <Icon size={32} stroke={1.4} />
            <strong>{label}</strong>
            <span>
              Khám phá <IconArrowUpRight size={14} />
            </span>
          </button>
        ))}
      </div>
      <div className="community-note">
        <IconHome size={25} stroke={1.5} />
        <div>
          <strong>Nhà là nơi được quan tâm.</strong>
          <p>Một kết nối nhỏ, một cộng đồng tốt hơn.</p>
        </div>
      </div>
    </div>
  );
}

/** What a request's status means to the resident, when no event says it better. */
const statusNews: Record<RequestStatus, string> = {
  received: "Ban quản lý đã tiếp nhận yêu cầu của bạn.",
  processing: "Yêu cầu đang được xử lý.",
  confirmation: "Đã xử lý xong, mời bạn kiểm tra và xác nhận.",
  completed: "Yêu cầu đã hoàn tất.",
  cancelled: "Yêu cầu đã được hủy.",
};

export function Notifications({
  requests,
  conversations,
  onOpen,
  onOpenChat,
}: {
  requests: ResidentRequest[];
  conversations: ResidentConversation[];
  onOpen: (id: string) => void;
  onOpenChat: (id: string) => void;
}) {
  // One card per subject: a request with unread messages shows as its conversation, not twice.
  const unread = conversations.filter((c) => c.unread > 0);
  const items = [
    ...unread.map((c) => ({
      key: c.id,
      title: c.title,
      body: c.preview ?? c.messages.at(-1)?.text ?? "Bạn có tin nhắn mới.",
      at: c.updatedAt,
      unread: c.unread,
      urgent: false,
      open: () => onOpenChat(c.id),
    })),
    ...requests
      .filter((r) => !unread.some((c) => c.requestId === r.id))
      .map((r) => ({
        key: r.id,
        title: r.title,
        body: r.events.at(-1)?.label ?? statusNews[r.status],
        at: r.events.at(-1)?.at || r.createdAt,
        unread: 0,
        urgent: r.status === "confirmation",
        open: () => onOpen(r.id),
      })),
  ].sort(
    (a, b) =>
      Math.sign(b.unread) - Math.sign(a.unread) || b.at.localeCompare(a.at),
  );
  return (
    <div className="page-section stack">
      <p className="page-description">
        Tin nhắn mới và cập nhật từ các yêu cầu của bạn.
      </p>
      {items.length ? (
        items.map((item) => (
          <button
            className="notification-card"
            key={item.key}
            onClick={item.open}
          >
            <span className={`icon-tile ${item.urgent ? "orange" : "blue"}`}>
              {item.unread ? (
                <IconMessageCircle size={21} />
              ) : (
                <IconBell size={21} />
              )}
            </span>
            <span>
              <strong>{item.title}</strong>
              <p>{item.body}</p>
              <time>{dateLabel(item.at)}</time>
            </span>
            {item.unread > 0 && (
              <b aria-label={`${item.unread} tin chưa đọc`}>{item.unread}</b>
            )}
            <IconChevronRight size={18} className="muted shrink" />
          </button>
        ))
      ) : (
        <div className="empty-state">
          <IconBell />
          <h3>Bạn đã xem hết thông báo</h3>
          <p>Cập nhật mới sẽ xuất hiện tại đây.</p>
        </div>
      )}
    </div>
  );
}

export function Profile({
  onReset,
  connected,
  connectedProfile,
}: {
  onReset: () => void;
  connected?: boolean;
  connectedProfile?: ResidentProfile;
}) {
  if (connected)
    return (
      <div className="page-section stack">
        <section className="profile-card">
          <span className="avatar large">
            <IconUser />
          </span>
          <h2>{connectedProfile?.user.name || "Đang tải tài khoản…"}</h2>
          <p>{connectedProfile?.user.email}</p>
          <span className="small muted">Hồ sơ cư dân từ hệ thống</span>
        </section>
        <section className="white-card">
          <h3>Căn hộ của bạn</h3>
          {connectedProfile?.units.map((u) => (
            <div className="apartment-card" key={u.id}>
              <span className="icon-tile coral">
                <IconHome />
              </span>
              <div>
                <strong>
                  {u.building_name} · {u.code}
                </strong>
                <p>{u.site_name}</p>
              </div>
              <span className="selection-dot" />
            </div>
          ))}
          {connectedProfile && !connectedProfile.units.length && (
            <p>Chưa có căn hộ đã xác minh. Liên hệ Ban quản lý để liên kết.</p>
          )}
        </section>
        <a className="secondary-button full" href="/login">
          Quản lý đăng nhập
        </a>
      </div>
    );
  return (
    <div className="page-section stack">
      <section className="profile-card">
        <span className="avatar large">MA</span>
        <h2>{resident.name}</h2>
        <span className="small muted">Cư dân · Hồ sơ minh họa</span>
      </section>
      <section className="white-card">
        <h3>Tài khoản cư dân</h3>
        <p>
          Đăng nhập để kết nối với ngôi nhà của bạn, hoặc tạo tài khoản nếu đây
          là lần đầu bạn ghé thăm.
        </p>
        <div className="button-row">
          <a className="primary-button" href="/login">
            Đăng nhập
          </a>
          <a className="secondary-button" href="/register">
            Đăng ký
          </a>
        </div>
        <p className="small muted">
          Giao diện mẫu · Dịch vụ tài khoản chưa được kết nối.
        </p>
      </section>
      <section className="white-card">
        <h3>Căn hộ của bạn</h3>
        <div className="apartment-card">
          <span className="icon-tile coral">
            <IconHome size={24} />
          </span>
          <div>
            <strong>{resident.apartment}</strong>
            <p>{resident.project}</p>
          </div>
          <span className="selection-dot" />
        </div>
      </section>
      <div className="info-note">
        <IconInfoCircle size={21} />
        <p>
          Đây là bản trải nghiệm giao diện. Hồ sơ và căn hộ đang dùng dữ liệu
          mẫu; các phản ánh chỉ được lưu trên trình duyệt này.
        </p>
      </div>
      <button className="secondary-button full" onClick={onReset}>
        Đặt lại dữ liệu trải nghiệm
      </button>
      <button className="secondary-button full" onClick={exitResidentPreview}>
        Thoát trải nghiệm về đăng nhập
      </button>
      <p className="footnote">
        Thao tác này xóa hội thoại, ảnh và yêu cầu bạn đã tạo trên thiết bị.
      </p>
    </div>
  );
}

export function Building({
  connected,
  connectedProfile,
}: {
  connected?: boolean;
  connectedProfile?: ResidentProfile;
} = {}) {
  return (
    <div className="page-section stack">
      <div className="building-heading">
        <span className="icon-tile teal">
          <IconBuildingCommunity size={28} />
        </span>
        <h2>
          {connected
            ? connectedProfile?.units[0]?.site_name || "Thông tin nơi ở"
            : resident.project}
        </h2>
        <p>
          <IconMapPin size={16} />
          {connected
            ? connectedProfile?.units
                .map((u) => u.building_name)
                .filter((v, i, all) => all.indexOf(v) === i)
                .join(" · ")
            : "Tòa S2.02"}
        </p>
      </div>
      <section className="white-card">
        <h3>Ban quản lý</h3>
        <p>
          Danh bạ và giờ làm việc chính thức sẽ hiển thị khi hệ thống được kết
          nối với Ban quản lý tòa nhà.
        </p>
      </section>
      <section className="white-card">
        <h3>Nội quy & hướng dẫn</h3>
        <p>
          Tài liệu về sinh hoạt, sử dụng khu vực chung và hướng dẫn dành cho cư
          dân sẽ được cập nhật tại đây.
        </p>
        <span className="availability-label">
          Chưa có tài liệu được công bố
        </span>
      </section>
      <div className="info-note">
        <IconInfoCircle size={21} />
        <p>
          Nếu có tình huống nguy hiểm cần hỗ trợ ngay, hãy liên hệ bảo vệ hoặc
          đầu mối khẩn cấp chính thức của tòa nhà.
        </p>
      </div>
    </div>
  );
}

export function Amenities({ connected }: { connected?: boolean } = {}) {
  if (connected)
    return (
      <div className="page-section stack">
        <section className="white-card">
          <span className="icon-tile teal">
            <IconTrees />
          </span>
          <h2>Tiện ích khu dân cư</h2>
          <p>
            Ban quản lý chưa công bố danh mục và lịch đặt tiện ích trên hệ
            thống.
          </p>
        </section>
      </div>
    );
  return (
    <div className="page-section stack">
      <p className="page-description">
        Thêm một chút thư giãn vào ngày của bạn.
      </p>
      {[
        {
          icon: IconSwimming,
          title: "Bể bơi",
          desc: "Một khoảng nghỉ mát lành ngay gần nhà.",
          color: "blue",
        },
        {
          icon: IconBarbell,
          title: "Phòng tập",
          desc: "Dành thời gian cho sức khỏe mỗi ngày.",
          color: "coral",
        },
        {
          icon: IconTrees,
          title: "Công viên & đường dạo",
          desc: "Đi chậm lại, tận hưởng không gian xanh.",
          color: "teal",
        },
      ].map(({ icon: Icon, title, desc, color }) => (
        <section key={title} className="white-card amenity-detail">
          <span className={`icon-tile ${color}`}>
            <Icon size={30} stroke={1.5} />
          </span>
          <h3>{title}</h3>
          <p>{desc}</p>
          <span className="availability-label">
            <IconInfoCircle size={15} />
            Danh mục minh họa · Chưa hỗ trợ đặt chỗ
          </span>
        </section>
      ))}
    </div>
  );
}
