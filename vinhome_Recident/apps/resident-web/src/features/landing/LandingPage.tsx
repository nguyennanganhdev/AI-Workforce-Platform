import { useEffect, useState } from "react";
import {
  IconArrowRight, IconArrowUpRight, IconBell, IconBuildingCommunity,
  IconCalendarEvent, IconChevronDown, IconClipboardCheck, IconMenu2,
  IconMessageCircle, IconShieldCheck, IconX,
} from "@tabler/icons-react";
import { Button } from "../../components/ui/button";
import { operationsUrl } from "../auth/auth-service";
import { Brand } from "../../components/Brand";
import "./landing.css";

const services = [
  { icon: IconMessageCircle, title: "Trao đổi với trợ lý cư dân", text: "Hỏi thông tin khu dân cư và gửi yêu cầu ngay trong cuộc trò chuyện." },
  { icon: IconClipboardCheck, title: "Theo dõi từng yêu cầu", text: "Xem tiến độ xử lý, bổ sung hình ảnh và phản hồi khi công việc hoàn tất." },
  { icon: IconCalendarEvent, title: "Đặt tiện ích của khu dân cư", text: "Tra cứu tiện ích, chọn thời gian sử dụng và quản lý lịch đặt của bạn." },
  { icon: IconBell, title: "Cập nhật thông tin cần biết", text: "Nhận thông báo và tra cứu thông tin tòa nhà, căn hộ trong cùng một nơi." },
];
const questions = [
  { title: "Tôi bắt đầu sử dụng như thế nào?", answer: "Chọn “Đăng nhập” và sử dụng tài khoản cư dân đã được cấp. Nếu chưa có tài khoản, bạn có thể đăng ký; ban quản lý cần xác minh và liên kết căn hộ trước khi bạn sử dụng dịch vụ." },
  { title: "Cư dân và ban quản lý có dùng chung tài khoản không?", answer: "Hệ thống dùng chung trang đăng nhập và phân quyền theo tài khoản. Cư dân vào không gian cư dân; ban quản lý, nhân viên và quản trị viên được chuyển đến khu vực vận hành phù hợp." },
  { title: "Tôi có thể gửi hình ảnh cùng yêu cầu không?", answer: "Có. Trong không gian cư dân, bạn có thể đính kèm hình ảnh, bổ sung thông tin và theo dõi phản hồi cho yêu cầu của mình." },
  { title: "Khi có tình huống khẩn cấp, tôi nên làm gì?", answer: "Liên hệ ngay bảo vệ hoặc ban quản lý theo số điện thoại khẩn cấp của khu dân cư. Không chờ phản hồi từ trợ lý hoặc yêu cầu trực tuyến khi cần hỗ trợ ngay." },
];

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    document.title = "Vinhomes | Cổng dịch vụ cư dân";
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        document.getElementById("landing-menu-toggle")?.focus();
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);

  return (
    <div className="landing">
      <a className="landing-skip" href="#main-content">Đi đến nội dung chính</a>
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a className="landing-brand" href="/" aria-label="Vinhomes, trang chủ">
            <Brand />
          </a>
          <nav id="landing-navigation" className={`landing-nav${menuOpen ? " is-open" : ""}`} aria-label="Điều hướng chính">
            <a href="#dich-vu" onClick={() => setMenuOpen(false)}>Dịch vụ</a>
            <a href="#bat-dau" onClick={() => setMenuOpen(false)}>Cách sử dụng</a>
            <a href="#giai-dap" onClick={() => setMenuOpen(false)}>Giải đáp</a>
          </nav>
          <div className="landing-header-actions">
            <Button asChild><a href="/login">Đăng nhập <IconArrowUpRight aria-hidden="true" /></a></Button>
            <Button id="landing-menu-toggle" variant="outline" size="icon" className="landing-menu-toggle" aria-label={menuOpen ? "Đóng menu" : "Mở menu"} aria-expanded={menuOpen} aria-controls="landing-navigation" onClick={() => setMenuOpen(!menuOpen)}>
              {menuOpen ? <IconX aria-hidden="true" /> : <IconMenu2 aria-hidden="true" />}
            </Button>
          </div>
        </div>
      </header>

      <main id="main-content">
        <section className="landing-container landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-copy">
            <p className="landing-eyebrow">Không gian kết nối cư dân</p>
            <h1 id="landing-title">Sống an tâm.<br />Kết nối dễ dàng.</h1>
            <p className="landing-hero-description">Gửi yêu cầu, tra cứu tiện ích và theo dõi xử lý trong một không gian.</p>
            <div className="landing-hero-actions">
              <Button asChild size="lg"><a href="/resident">Vào ứng dụng <IconArrowRight aria-hidden="true" /></a></Button>
              <a className="landing-text-link" href={operationsUrl("/operations")}>Cổng vận hành <IconArrowUpRight aria-hidden="true" /></a>
            </div>
          </div>
          <figure className="landing-hero-visual">
            <img src="/images/ocean-park-welcome-960.webp" srcSet="/images/ocean-park-welcome-640.webp 640w, /images/ocean-park-welcome-960.webp 960w, /images/ocean-park-welcome-1600.webp 1600w" sizes="(max-width: 767px) calc(100vw - 40px), (max-width: 1100px) 50vw, 640px" alt="Không gian xanh, mặt nước và các tòa căn hộ tại Vinhomes Ocean Park" width="1600" height="900" fetchPriority="high" />
            <figcaption><IconBuildingCommunity aria-hidden="true" size={20} /> Một không gian sống, một nơi kết nối.</figcaption>
          </figure>
        </section>

        <section id="dich-vu" className="landing-container landing-services" aria-labelledby="services-title">
          <div className="landing-section-heading">
            <h2 id="services-title">Chăm sóc cuộc sống<br className="landing-desktop-break" /> từ những điều hằng ngày.</h2>
            <p>Những việc của căn hộ và khu dân cư được kết nối với đội ngũ vận hành để bạn dễ theo dõi.</p>
          </div>
          <div className="landing-service-grid">
            {services.map(({ icon: Icon, title, text }) => (
              <article key={title} className="landing-service">
                <Icon size={26} stroke={1.5} aria-hidden="true" />
                <div><h3>{title}</h3><p>{text}</p></div>
              </article>
            ))}
          </div>
        </section>

        <section id="bat-dau" className="landing-start" aria-labelledby="start-title">
          <div className="landing-container">
            <div className="landing-section-heading">
              <h2 id="start-title">Bắt đầu từ tài khoản của bạn.</h2>
              <p>Đăng nhập đúng tài khoản để vào không gian dành cho vai trò của mình.</p>
            </div>
            <div className="landing-access-grid">
              <article className="landing-access landing-access-resident">
                <IconBuildingCommunity size={34} stroke={1.5} aria-hidden="true" />
                <h3>Dành cho cư dân</h3>
                <p>Trao đổi với trợ lý, gửi phản ánh, đặt tiện ích và theo dõi yêu cầu của căn hộ.</p>
                <a className="landing-access-link" href="/login">Đăng nhập tài khoản cư dân <IconArrowRight aria-hidden="true" size={20} /></a>
                <a className="landing-register-link" href="/register">Chưa có tài khoản? Đăng ký</a>
              </article>
              <article className="landing-access">
                <IconShieldCheck size={34} stroke={1.5} aria-hidden="true" />
                <h3>Dành cho đội ngũ vận hành</h3>
                <p>Tiếp nhận yêu cầu, điều phối công việc và cập nhật kết quả theo quyền được cấp.</p>
                <a className="landing-access-link" href={operationsUrl("/operations")}>Vào cổng vận hành <IconArrowRight aria-hidden="true" size={20} /></a>
                <span className="landing-access-note">Nhân viên và quản trị Domain · Ban quản lý sử dụng Platform</span>
              </article>
            </div>
          </div>
        </section>

        <section id="giai-dap" className="landing-container landing-faq" aria-labelledby="faq-title">
          <div className="landing-section-heading"><h2 id="faq-title">Một vài điều bạn có thể cần biết.</h2></div>
          <div className="landing-faq-list">
            {questions.map(({ title, answer }) => (
              <details key={title}>
                <summary>{title}<IconChevronDown size={20} aria-hidden="true" /></summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="landing-footer-brand"><img src="/images/vinhomes-official.png" alt="Vinhomes" width="112" height="51" /><span>Cổng dịch vụ cư dân và vận hành</span></div>
          <nav aria-label="Liên kết cuối trang"><a href="/login">Đăng nhập</a><a href="/register">Đăng ký cư dân</a><a href={operationsUrl("/operations")}>Vận hành</a></nav>
          <p>Thông tin cá nhân và dịch vụ được hiển thị theo quyền của từng tài khoản.</p>
        </div>
      </footer>
    </div>
  );
}
