import {
  IconArrowUpRight,
  IconBell,
  IconBuildingCommunity,
  IconChevronRight,
  IconClipboardList,
  IconInfoCircle,
  IconMapPin,
  IconSwimming,
  IconBarbell,
  IconTrees,
  IconUser,
  IconHome,
} from "@tabler/icons-react";
import { Neighborhood } from "../../components/Illustrations";
import { resident } from "../../mocks/seed";
import { dateLabel } from "../requests/Requests";
import type { ResidentRequest } from "../../services/types";

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

export function Notifications({
  requests,
  onOpen,
}: {
  requests: ResidentRequest[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="page-section stack">
      <p className="page-description">
        Cập nhật mới nhất từ các yêu cầu của bạn.
      </p>
      {requests.length ? (
        [...requests]
          .sort((a, b) =>
            b.events.at(-1)!.at.localeCompare(a.events.at(-1)!.at),
          )
          .map((r) => (
            <button
              className="notification-card"
              key={r.id}
              onClick={() => onOpen(r.id)}
            >
              <span
                className={`icon-tile ${r.status === "confirmation" ? "orange" : "blue"}`}
              >
                <IconBell size={21} />
              </span>
              <span>
                <strong>{r.events.at(-1)?.label}</strong>
                <p>{r.title}</p>
                <time>{dateLabel(r.events.at(-1)!.at)}</time>
              </span>
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

export function Profile({ onReset }: { onReset: () => void }) {
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
          <a className="primary-button" href="#/login">
            Đăng nhập
          </a>
          <a className="secondary-button" href="#/register">
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
      <p className="footnote">
        Thao tác này xóa hội thoại, ảnh và yêu cầu bạn đã tạo trên thiết bị.
      </p>
    </div>
  );
}

export function Building() {
  return (
    <div className="page-section stack">
      <div className="building-heading">
        <span className="icon-tile teal">
          <IconBuildingCommunity size={28} />
        </span>
        <h2>{resident.project}</h2>
        <p>
          <IconMapPin size={16} />
          Tòa S2.02
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
          đầu mối khẩn cấp chính thức của tòa nhà. Bản trải nghiệm chưa tiếp
          nhận yêu cầu thực tế.
        </p>
      </div>
    </div>
  );
}

export function Amenities() {
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
