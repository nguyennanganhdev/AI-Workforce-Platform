import { useEffect, useRef } from "react";
import { IconHome, IconShieldCheck, IconClock } from "@tabler/icons-react";
import "./auth.css";

export type ResidentPendingStatus =
  | "verification-required"
  | "membership-pending";
export function ResidentAccountStatus({
  status,
  preview = false,
}: {
  status: ResidentPendingStatus;
  preview?: boolean;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const verification = status === "verification-required";
  const title = verification
    ? "Xác minh thông tin của bạn"
    : "Chờ liên kết căn hộ";
  useEffect(() => {
    document.title = `${title} — Nhà`;
    heading.current?.focus();
  }, [title]);
  return (
    <main className="resident-auth-status">
      <a className="resident-auth-status-brand" href="/login">
        <IconHome size={25} /> nhà.
      </a>
      <section>
        {preview && (
          <p className="resident-auth-status-preview">
            Xem trước giao diện · Không phải trạng thái tài khoản thật
          </p>
        )}
        <span className="resident-auth-status-icon">
          {verification ? (
            <IconShieldCheck size={36} />
          ) : (
            <IconClock size={36} />
          )}
        </span>
        <h1 tabIndex={-1} ref={heading}>
          {title}
        </h1>
        <p>
          {verification
            ? "Bạn cần hoàn tất xác minh theo hướng dẫn của hệ thống để tiếp tục sử dụng tài khoản."
            : "Thông tin cư dân cần được xác nhận và liên kết với căn hộ trước khi sử dụng dịch vụ."}
        </p>
        <ol>
          <li>Xác minh thông tin tài khoản</li>
          <li>Ban quản lý xác nhận thông tin cư dân và căn hộ</li>
          <li>Sử dụng trợ lý và các dịch vụ dành cho cư dân</li>
        </ol>
        <p className="resident-auth-status-note">
          Nếu cần hỗ trợ, vui lòng liên hệ ban quản lý nơi bạn đang cư trú.
        </p>
        <a className="resident-auth-status-action" href="/login">
          Quay lại đăng nhập
        </a>
      </section>
    </main>
  );
}
