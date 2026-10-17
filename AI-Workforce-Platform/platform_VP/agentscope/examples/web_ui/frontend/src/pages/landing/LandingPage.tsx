import {
	ArrowRight,
	BadgeCheck,
	Bot,
	Check,
	ChevronDown,
	CirclePlay,
	Globe2,
	Layers3,
	Link2,
	Menu,
	Sparkles,
	X,
} from 'lucide-react';
import { useState } from 'react';

import coordinatorImage from '@/assets/images/agent/Dieu_phoi.jpeg';
import plannerImage from '@/assets/images/agent/Ke_hoach.png';
import technicianImage from '@/assets/images/agent/Ky_Thuat.png';
import receptionImage from '@/assets/images/agent/Le_tan.png';
import calculatorImage from '@/assets/images/agent/Tinh_toan.png';
import { Brand, BrandMark } from '@/components/layout/Brand';
import './landing-page.css';

interface Props {
	onGetStarted: () => void;
}

const agents = [
	{
		name: 'Agent Điều phối',
		role: 'Điều phối công việc',
		image: coordinatorImage,
		color: 'peach',
	},
	{
		name: 'Agent Kế hoạch',
		role: 'Lập kế hoạch thông minh',
		image: plannerImage,
		color: 'lilac',
	},
	{
		name: 'Agent Tính toán',
		role: 'Phân tích & tính toán',
		image: calculatorImage,
		color: 'yellow',
	},
	{ name: 'Agent Kỹ thuật', role: 'Giải quyết vấn đề', image: technicianImage, color: 'blue' },
	{ name: 'Agent Lễ tân', role: 'Chăm sóc & hỗ trợ', image: receptionImage, color: 'mint' },
] as const;

const faqs = [
	[
		'VAgents là gì?',
		'VAgents là nền tảng giúp bạn kết nối nhiều AI agent để cùng xử lý công việc, thay vì phải làm từng bước thủ công.',
	],
	[
		'Tôi có cần biết lập trình không?',
		'Không. Bạn có thể bắt đầu bằng cách chọn agent, mô tả mục tiêu và để workspace điều phối phần còn lại.',
	],
	[
		'Tôi có thể kết nối những công cụ nào?',
		'VAgents được thiết kế để kết nối với các công cụ và nguồn dữ liệu bạn đang sử dụng trong công việc hàng ngày.',
	],
	[
		'Dữ liệu của tôi có an toàn không?',
		'Mỗi workspace được tách biệt và bạn luôn kiểm soát quyền truy cập, credential và các thao tác mà agent được phép thực hiện.',
	],
] as const;

export function LandingPage({ onGetStarted }: Props) {
	const [mobileOpen, setMobileOpen] = useState(false);
	const [openFaq, setOpenFaq] = useState<number | null>(0);

	const scrollTo = (id: string) => {
		setMobileOpen(false);
		document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
	};

	return (
		<div className="landing-page">
			<header className="landing-nav">
				<a className="landing-brand" href="#top" aria-label="VAgents">
					<Brand />
				</a>
				<nav className={mobileOpen ? 'landing-links is-open' : 'landing-links'}>
					<button onClick={() => scrollTo('how-it-works')}>Cách hoạt động</button>
					<button onClick={() => scrollTo('agents')}>AI Agents</button>
					<button onClick={() => scrollTo('workspace')}>Workspace</button>
					<button onClick={() => scrollTo('pricing')}>Bảng giá</button>
					<button onClick={() => scrollTo('faq')}>FAQ</button>
					<button className="mobile-cta" onClick={onGetStarted}>
						Bắt đầu ngay <ArrowRight size={15} />
					</button>
				</nav>
				<div className="landing-nav-actions">
					<button className="landing-login" onClick={onGetStarted}>
						Đăng nhập
					</button>
					<button className="landing-button landing-button-small" onClick={onGetStarted}>
						Bắt đầu ngay <ArrowRight size={15} />
					</button>
				</div>
				<button
					className="landing-menu"
					aria-label="Mở menu"
					onClick={() => setMobileOpen((value) => !value)}
				>
					{mobileOpen ? <X /> : <Menu />}
				</button>
			</header>

			<main id="top">
				<section className="landing-hero landing-shell">
					<div className="hero-copy">
						<div className="eyebrow">
							<Sparkles size={14} /> WORK SMARTER WITH AI
						</div>
						<h1>
							Một vũ trụ.
							<br />
							<em>Cả đội ngũ AI</em>
							<br />
							cùng hành động.
						</h1>
						<p>
							Một nền tảng để các AI agent phối hợp, suy nghĩ và hoàn thành công việc
							cùng bạn.
						</p>
						<div className="hero-actions">
							<button className="landing-button" onClick={onGetStarted}>
								Khám phá VAgents <ArrowRight size={17} />
							</button>
							<button
								className="text-button"
								onClick={() => scrollTo('how-it-works')}
							>
								<CirclePlay size={17} /> Xem cách hoạt động
							</button>
						</div>
						<div className="hero-proof">
							<span>
								<BadgeCheck size={16} /> Không cần thẻ tín dụng
							</span>
							<span>
								<BadgeCheck size={16} /> Bắt đầu trong 2 phút
							</span>
						</div>
					</div>
					<div className="hero-visual">
						<div className="hero-grid" />
						<div className="hero-orbit orbit-one" />
						<div className="hero-orbit orbit-two" />
						<div className="hero-center">
							<BrandMark className="size-10" />
							<span>VAgents</span>
							<small>AI workforce platform</small>
						</div>
						<div className="hero-agent agent-one">
							<img src={coordinatorImage} alt="" />
							<strong>Điều phối</strong>
							<span>Đang làm việc</span>
						</div>
						<div className="hero-agent agent-two">
							<img src={plannerImage} alt="" />
							<strong>Kế hoạch</strong>
							<span>Đã sẵn sàng</span>
						</div>
						<div className="hero-agent agent-three">
							<img src={technicianImage} alt="" />
							<strong>Kỹ thuật</strong>
							<span>Đang suy nghĩ...</span>
						</div>
						<div className="hero-spark spark-one">✦</div>
						<div className="hero-spark spark-two">✦</div>
					</div>
				</section>

				<div className="trust-strip">
					<span>Được xây dựng cho những đội ngũ muốn đi xa hơn</span>
					<div>
						<span>✦</span> Tự động hóa
					</div>
					<div>
						<span>◌</span> Phối hợp
					</div>
					<div>
						<span>◈</span> Tăng trưởng
					</div>
					<div>
						<span>◎</span> Sáng tạo
					</div>
				</div>

				<section className="landing-section landing-shell" id="how-it-works">
					<div className="section-heading centered">
						<div className="eyebrow">TỪ Ý TƯỞNG ĐẾN KẾT QUẢ</div>
						<h2>
							Từ tưởng đến quy trình chạy thật
							<br />
							<em>chỉ trong 3 bước.</em>
						</h2>
						<p>
							VAgents biến những việc phức tạp thành một quy trình rõ ràng, có thể lặp
							lại và mở rộng.
						</p>
					</div>
					<div className="steps-grid">
						{[
							[
								'01',
								'Tạo Agent',
								'Chọn một agent phù hợp hoặc tạo đội ngũ của riêng bạn.',
								<Bot />,
							],
							[
								'02',
								'Kết nối công cụ',
								'Kết nối dữ liệu và các công cụ mà công việc của bạn cần.',
								<Link2 />,
							],
							[
								'03',
								'Vận hành quy trình',
								'Giao mục tiêu và để đội ngũ AI cùng bạn hoàn thành.',
								<Sparkles />,
							],
						].map(([number, title, description, icon]) => (
							<article className="step-card" key={String(number)}>
								<span className="step-number">{number}</span>
								<div className="step-icon">{icon}</div>
								<h3>{title}</h3>
								<p>{description}</p>
								<ArrowRight className="step-arrow" size={18} />
							</article>
						))}
					</div>
				</section>

				<section className="landing-band" id="agents">
					<div className="landing-shell">
						<div className="section-heading">
							<div className="eyebrow">NĂM AGENT, MỘT TINH THẦN ĐỒNG ĐỘI</div>
							<h2>
								Mỗi agent một thế mạnh.
								<br />
								<em>Cùng nhau tạo khác biệt.</em>
							</h2>
							<p>
								Từ lên kế hoạch đến thực thi, mỗi agent được sinh ra để làm tốt một
								việc — và làm việc cùng nhau.
							</p>
						</div>
						<div className="agent-grid">
							{agents.map((agent) => (
								<article className={`agent-card ${agent.color}`} key={agent.name}>
									<div className="agent-photo">
										<img src={agent.image} alt={agent.name} />
									</div>
									<div>
										<h3>{agent.name}</h3>
										<p>{agent.role}</p>
									</div>
									<ArrowRight size={17} />
								</article>
							))}
						</div>
					</div>
				</section>

				<section className="landing-section landing-shell workspace-section" id="workspace">
					<div className="section-heading centered">
						<div className="eyebrow">MỘT KHÔNG GIAN, MỌI KHẢ NĂNG</div>
						<h2>
							Bạn ra lệnh một câu.
							<br />
							<em>Cả đội ngũ xử lý.</em>
						</h2>
						<p>
							Từ một ý tưởng đơn giản đến kết quả hoàn chỉnh — mọi thứ diễn ra trong
							một workspace trực quan.
						</p>
					</div>
					<div className="workspace-preview">
						<div className="window-bar">
							<span />
							<span />
							<span />
							<b>VAgents workspace</b>
						</div>
						<div className="workspace-content">
							<aside>
								<BrandMark className="size-7" />
								<div className="preview-nav active">✦ Tổng quan</div>
								<div className="preview-nav">◈ Agent của tôi</div>
								<div className="preview-nav">⌁ Quy trình</div>
								<div className="preview-nav">⚙ Cài đặt</div>
							</aside>
							<div className="preview-main">
								<div className="preview-title">
									<span>
										<small>WORKSPACE / HÔM NAY</small>
										<strong>Chào buổi sáng, Minh 👋</strong>
									</span>
									<button className="landing-button landing-button-small">
										Tạo công việc <ArrowRight size={14} />
									</button>
								</div>
								<div className="preview-cards">
									<div className="preview-card highlight">
										<Sparkles size={18} />
										<strong>Đội ngũ đang hoạt động</strong>
										<span>5 agents đang phối hợp</span>
										<div className="avatar-stack">
											{agents.map((agent) => (
												<img key={agent.name} src={agent.image} alt="" />
											))}
										</div>
									</div>
									<div className="preview-card">
										<Layers3 size={18} />
										<strong>Quy trình hoàn thành</strong>
										<span>12 trong tuần này</span>
										<b className="metric">+24%</b>
									</div>
									<div className="preview-card">
										<Globe2 size={18} />
										<strong>Công cụ đã kết nối</strong>
										<span>8 integrations</span>
										<b className="metric">Sẵn sàng</b>
									</div>
								</div>
								<div className="preview-task">
									<div>
										<small>QUY TRÌNH MỚI NHẤT</small>
										<strong>Chuẩn bị báo cáo tuần</strong>
									</div>
									<span className="task-status">
										Đang chạy <i />
									</span>
								</div>
							</div>
						</div>
					</div>
				</section>

				<section className="landing-band tools-section">
					<div className="landing-shell tools-layout">
						<div className="tools-diagram">
							<div className="tools-ring ring-a" />
							<div className="tools-ring ring-b" />
							<div className="tools-core">
								<BrandMark className="size-9" />
							</div>
							{['✣', '◉', '⌁', '◈', '⚙', '✦'].map((icon, index) => (
								<span className={`tool-orb orb-${index}`} key={icon}>
									{icon}
								</span>
							))}
						</div>
						<div className="section-heading">
							<div className="eyebrow">KẾT NỐI MỌI CÔNG CỤ BẠN ĐANG DÙNG</div>
							<h2>
								Không cần thay đổi
								<br />
								<em>cách bạn làm việc.</em>
							</h2>
							<p>
								VAgents kết nối những công cụ quen thuộc vào cùng một hệ thống, để
								agent có thể hành động ngay khi bạn cần.
							</p>
							<ul className="feature-list">
								<li>
									<Check size={15} /> Quản lý dữ liệu tập trung
								</li>
								<li>
									<Check size={15} /> Phân quyền rõ ràng, an toàn
								</li>
								<li>
									<Check size={15} /> Theo dõi tiến độ theo thời gian thực
								</li>
							</ul>
						</div>
					</div>
				</section>

				<section className="landing-section landing-shell" id="pricing">
					<div className="section-heading centered">
						<div className="eyebrow">ĐƠN GIẢN, MINH BẠCH</div>
						<h2>
							Bắt đầu nhỏ.
							<br />
							<em>Mở rộng thoải mái.</em>
						</h2>
						<p>
							Chọn gói phù hợp với bạn hôm nay. Khi đội ngũ lớn lên, VAgents luôn sẵn
							sàng đồng hành.
						</p>
					</div>
					<div className="pricing-grid">
						{[
							[
								'Khởi đầu',
								'Dành cho cá nhân',
								'0đ',
								['5 agent cơ bản', '100 lượt chạy / tháng', 'Workspace cá nhân'],
							],
							[
								'Doanh nghiệp',
								'Dành cho đội ngũ',
								'Liên hệ',
								['Agent không giới hạn', 'Tích hợp tùy chỉnh', 'Hỗ trợ ưu tiên'],
							],
							[
								'Tập đoàn',
								'Dành cho tổ chức lớn',
								'Liên hệ',
								['Hạ tầng riêng biệt', 'Bảo mật nâng cao', 'Hỗ trợ 24/7'],
							],
						].map(([name, subtitle, price, features], index) => (
							<article
								className={`price-card ${index === 1 ? 'featured' : ''}`}
								key={index}
							>
								<span className="price-label">
									{index === 1 && 'PHỔ BIẾN NHẤT'}
								</span>
								<h3>{name}</h3>
								<p>{subtitle}</p>
								<strong>{price}</strong>
								<ul>
									{(features as string[]).map((feature) => (
										<li key={feature}>
											<Check size={15} /> {feature}
										</li>
									))}
								</ul>
								<button
									className={index === 1 ? 'landing-button' : 'outline-button'}
									onClick={onGetStarted}
								>
									{index === 0 ? 'Bắt đầu miễn phí' : 'Liên hệ chúng tôi'}
								</button>
							</article>
						))}
					</div>
				</section>

				<section className="landing-section faq-section" id="faq">
					<div className="landing-shell faq-layout">
						<div className="section-heading">
							<div className="eyebrow">CÓ THỂ BẠN ĐANG HỎI</div>
							<h2>
								Bạn hỏi,
								<br />
								<em>chúng tôi trả lời.</em>
							</h2>
							<p>Không tìm thấy câu trả lời? Hãy nói chuyện với chúng tôi.</p>
							<button className="text-button" onClick={onGetStarted}>
								Liên hệ đội ngũ <ArrowRight size={16} />
							</button>
						</div>
						<div className="faq-list">
							{faqs.map(([question, answer], index) => (
								<div
									className={`faq-item ${openFaq === index ? 'open' : ''}`}
									key={question}
								>
									<button
										onClick={() => setOpenFaq(openFaq === index ? null : index)}
									>
										<span>{question}</span>
										<ChevronDown size={18} />
									</button>
									{openFaq === index && <p>{answer}</p>}
								</div>
							))}
						</div>
					</div>
				</section>

				<section className="landing-cta landing-shell">
					<div className="cta-inner">
						<div className="eyebrow">SẴN SÀNG GIAO VIỆC CHO ĐỘI NGŨ AI CỦA BẠN?</div>
						<h2>
							Ý tưởng lớn bắt đầu
							<br />
							<em>từ một câu lệnh nhỏ.</em>
						</h2>
						<p>Tham gia cùng những đội ngũ đang xây dựng cách làm việc mới.</p>
						<button className="landing-button" onClick={onGetStarted}>
							Bắt đầu miễn phí <ArrowRight size={17} />
						</button>
						<div className="cta-agents">
							{agents.map((agent) => (
								<img key={agent.name} src={agent.image} alt="" />
							))}
						</div>
					</div>
				</section>
			</main>

			<footer className="landing-footer">
				<div className="landing-shell footer-grid">
					<div>
						<Brand />
						<p>Nền tảng AI workforce cho công việc hiện đại.</p>
						<div className="footer-socials">
							<span>in</span>
							<span>𝕏</span>
							<span>◎</span>
						</div>
					</div>
					<div>
						<strong>Sản phẩm</strong>
						<a href="#agents">AI Agents</a>
						<a href="#workspace">Workspace</a>
						<a href="#pricing">Bảng giá</a>
					</div>
					<div>
						<strong>Công ty</strong>
						<a href="#faq">Về chúng tôi</a>
						<a href="#faq">Liên hệ</a>
						<a href="#faq">Blog</a>
					</div>
					<div>
						<strong>Trợ giúp</strong>
						<a href="#faq">Trung tâm hỗ trợ</a>
						<a href="#faq">Điều khoản</a>
						<a href="#faq">Bảo mật</a>
					</div>
				</div>
				<div className="landing-shell footer-bottom">
					<span>© 2026 VAgents. All rights reserved.</span>
					<span>Made with purpose for better work.</span>
				</div>
			</footer>
		</div>
	);
}
