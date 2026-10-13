import { useEffect, useRef } from "react";
import { IconShieldCheck, IconClock } from "@tabler/icons-react";
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
    ? "Chờ xác minh căn hộ"
    : "Chờ duyệt tài khoản";
  useEffect(() => {
    document.title = `${title} — Vinhomes`;
    heading.current?.focus();
  }, [title]);
  return (
    <main className="resident-auth-status">
      <a className="resident-auth-status-brand" href="/login">
        <img src="/images/vinhomes-logo.png" alt="Vinhomes" width={120} height={48} style={{objectFit: "contain"}} />
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
            ? "Tài khoản đã được duyệt. Ban quản lý cần liên kết và xác minh đúng căn hộ của bạn trước khi bạn sử dụng dịch vụ cư dân."
            : "Đăng ký đã được tiếp nhận. Quản trị viên cần duyệt tài khoản và xác nhận thông tin cư trú của bạn."}
        </p>
        <ol>
          <li>{verification ? "Tài khoản đã được duyệt" : "Quản trị viên duyệt tài khoản"}</li>
          <li>Ban quản lý xác nhận thông tin cư dân và căn hộ</li>
          <li>Sử dụng trợ lý và các dịch vụ dành cho cư dân</li>
        </ol>
        <p className="resident-auth-status-note">
          Liên hệ ban quản lý và cung cấp tòa nhà, căn hộ cùng quan hệ cư trú. Sau khi hoàn tất, đăng nhập lại để cập nhật quyền truy cập.
        </p>
        <a className="resident-auth-status-action" href="/login">
          Đăng nhập lại để kiểm tra
        </a>
      </section>
    </main>
  );
}
