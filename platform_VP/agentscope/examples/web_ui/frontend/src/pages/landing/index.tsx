import {
	ArrowRight,
	Bot,
	Box,
	CalendarCheck,
	ChartNoAxesCombined,
	Check,
	CheckCheck,
	ChevronDown,
	Cloud,
	CreditCard,
	DatabaseZap,
	FileText,
	Headphones,
	Mail,
	Megaphone,
	Menu,
	MessageSquareText,
	Network,
	Pause,
	Play,
	PlugZap,
	RefreshCw,
	ShieldCheck,
	ShoppingCart,
	Sparkles,
	TableProperties,
	Terminal,
	Users,
	Waypoints,
	Workflow,
	X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

import agentSupport from '@/assets/images/landing-agent-cskh.webp';
import agentCoordinator from '@/assets/images/landing-agent-dieu-phoi.webp';
import agentIntegrations from '@/assets/images/landing-agent-du-lieu.webp';
import agentEngineer from '@/assets/images/landing-agent-ky-su.webp';
import agentAnalyst from '@/assets/images/landing-agent-phan-tich.webp';
import agentTeam from '@/assets/images/landing-hero-squad.webp';
import { BrandMark } from '@/components/layout/Brand';

import './landing.css';

interface IconCopy {
	icon: LucideIcon;
	label: string;
}

const capabilities: IconCopy[] = [
	{ icon: Headphones, label: 'Trả lời khách hàng' },
	{ icon: CalendarCheck, label: 'Điều phối lịch hẹn' },
	{ icon: Mail, label: 'Soạn và gửi email' },
	{ icon: ChartNoAxesCombined, label: 'Tổng hợp báo cáo' },
	{ icon: DatabaseZap, label: 'Đồng bộ dữ liệu' },
	{ icon: FileText, label: 'Xử lý tài liệu' },
	{ icon: Users, label: 'Phối hợp đa phòng ban' },
];

const processSteps: Array<IconCopy & { title: string; body: string }> = [
	{
		icon: Bot,
		label: 'Bước 1',
		title: 'Tạo Agent',
		body: 'Mô tả công việc bằng tiếng Việt. Nền tảng dựng vai trò, kỹ năng và giới hạn phù hợp.',
	},
	{
		icon: Network,
		label: 'Bước 2',
		title: 'Kết nối công cụ',
		body: 'Đưa agent vào email, dữ liệu, lịch làm việc và những hệ thống đội ngũ đang dùng.',
	},
	{
		icon: Waypoints,
		label: 'Bước 3',
		title: 'Vận hành quy trình',
		body: 'Các agent tự phối hợp, chuyển giao công việc và chỉ mời bạn duyệt ở bước quan trọng.',
	},
];

const agents = [
	{
		name: 'Agent CSKH',
		role: 'Chăm sóc khách hàng',
		body: 'Phản hồi trên mọi kênh theo đúng giọng thương hiệu và bối cảnh khách hàng.',
		image: agentSupport,
		tags: ['Chat', 'Email'],
	},
	{
		name: 'Agent Điều phối',
		role: 'Điều phối công việc',
		body: 'Nhận yêu cầu, chọn đúng thành viên và theo dõi tiến độ đến khi hoàn tất.',
		image: agentCoordinator,
		tags: ['Phân việc', 'Nhắc hạn'],
	},
	{
		name: 'Agent Kỹ sư',
		role: 'Xây dựng quy trình',
		body: 'Thiết kế workflow, kết nối dịch vụ và giữ cho mọi luồng vận hành ổn định.',
		image: agentEngineer,
		tags: ['Workflow', 'Tích hợp'],
		featured: true,
	},
	{
		name: 'Agent Phân tích',
		role: 'Phân tích',
		body: 'Đọc dữ liệu, nhận ra xu hướng và đề xuất hành động tiếp theo cho đội ngũ.',
		image: agentAnalyst,
		tags: ['Báo cáo', 'Dự báo'],
	},
	{
		name: 'Agent Dữ liệu',
		role: 'Dữ liệu',
		body: 'Thu thập, làm sạch và đồng bộ thông tin giữa các hệ thống doanh nghiệp.',
		image: agentIntegrations,
		tags: ['ETL', 'Đồng bộ'],
	},
];

const demoSteps = [
	'Nhận đơn hàng mới',
	'Kiểm tra tồn kho',
	'Xác nhận với khách',
	'Cập nhật báo cáo',
	'Lưu quy trình tự động',
];

const demoPrompt =
	'Mỗi khi có đơn hàng mới: kiểm tra tồn kho, xác nhận với khách và cập nhật báo cáo doanh thu.';

const demoMessages = [
	{
		agent: 'Agent Điều phối',
		body: 'Đã nhận yêu cầu, chia việc cho cả đội.',
		image: agentCoordinator,
	},
	{ agent: 'Agent Dữ liệu', body: 'Đã kiểm tra kho: mặt hàng còn đủ.', image: agentIntegrations },
	{ agent: 'Agent CSKH', body: 'Đã gửi tin xác nhận đơn cho khách.', image: agentSupport },
	{
		agent: 'Agent Phân tích',
		body: 'Đã cập nhật báo cáo doanh thu trong ngày.',
		image: agentAnalyst,
	},
];

const integrations: IconCopy[] = [
	{ icon: MessageSquareText, label: 'Chat' },
	{ icon: Mail, label: 'Email' },
	{ icon: TableProperties, label: 'Bảng tính' },
	{ icon: CreditCard, label: 'Thanh toán' },
	{ icon: DatabaseZap, label: 'Cơ sở dữ liệu' },
	{ icon: FileText, label: 'Tài liệu' },
	{ icon: CalendarCheck, label: 'Lịch' },
	{ icon: ChartNoAxesCombined, label: 'Báo cáo' },
	{ icon: ShoppingCart, label: 'Bán hàng' },
	{ icon: Cloud, label: 'Đám mây' },
	{ icon: Users, label: 'Đội ngũ' },
	{ icon: Megaphone, label: 'Marketing' },
];

const useCases = [
	{
		name: 'Chăm sóc khách hàng',
		title: 'Mọi hội thoại đều có ngữ cảnh.',
		body: 'Agent đọc lịch sử trao đổi, tra cứu dữ liệu cần thiết và phản hồi đúng chuẩn thương hiệu.',
		items: ['Tiếp nhận đa kênh', 'Phân loại yêu cầu', 'Chuyển người thật đúng lúc'],
		icon: Headphones,
	},
	{
		name: 'Vận hành',
		title: 'Quy trình tự chạy, đội ngũ vẫn kiểm soát.',
		body: 'Các bước lặp lại được tự động hóa. Những quyết định nhạy cảm luôn chờ người phụ trách duyệt.',
		items: ['Điều phối công việc', 'Theo dõi SLA', 'Báo cáo trạng thái'],
		icon: Waypoints,
	},
	{
		name: 'Dữ liệu',
		title: 'Dữ liệu sạch trước khi đến tay bạn.',
		body: 'Agent gom dữ liệu từ nhiều nguồn, chuẩn hóa cấu trúc và ghi lại đầy đủ nguồn gốc xử lý.',
		items: ['Kết nối nhiều nguồn', 'Kiểm tra chất lượng', 'Đồng bộ có kiểm soát'],
		icon: DatabaseZap,
	},
	{
		name: 'Nhân sự',
		title: 'Giảm việc hành chính, tăng thời gian cho con người.',
		body: 'Từ sàng lọc hồ sơ đến lịch phỏng vấn, agent hỗ trợ các bước tốn thời gian nhất.',
		items: ['Sàng lọc hồ sơ', 'Điều phối phỏng vấn', 'Chuẩn bị tài liệu'],
		icon: Users,
	},
];

const faqs = [
	{
		question: 'Tôi có cần biết lập trình để tạo agent không?',
		answer: 'Không. Bạn mô tả mục tiêu bằng ngôn ngữ tự nhiên, sau đó tinh chỉnh vai trò và quyền truy cập qua giao diện.',
	},
	{
		question: 'Agent có thể kết nối với công cụ nội bộ không?',
		answer: 'Có. VAgents hỗ trợ MCP, API và các kênh sự kiện để kết nối dịch vụ có sẵn trong doanh nghiệp.',
	},
	{
		question: 'Làm sao kiểm soát những hành động quan trọng?',
		answer: 'Bạn có thể đặt chính sách quyền, yêu cầu phê duyệt và theo dõi lịch sử thực thi cho từng workflow.',
	},
	{
		question: 'Tôi có thể bắt đầu với một agent trước không?',
		answer: 'Có. Bạn có thể bắt đầu từ một vai trò, kiểm chứng hiệu quả rồi mở rộng thành đội agent khi cần.',
	},
];

function WorkflowDemo() {
	const [typedLength, setTypedLength] = useState(0);
	const [completedSteps, setCompletedSteps] = useState(0);
	const [playing, setPlaying] = useState(true);

	useEffect(() => {
		if (!playing) return;
		if (typedLength < demoPrompt.length) {
			const timer = window.setTimeout(
				() => setTypedLength((current) => Math.min(current + 1, demoPrompt.length)),
				24,
			);
			return () => window.clearTimeout(timer);
		}
		if (completedSteps < demoSteps.length) {
			const timer = window.setTimeout(
				() => setCompletedSteps((current) => Math.min(current + 1, demoSteps.length)),
				820,
			);
			return () => window.clearTimeout(timer);
		}
		const timer = window.setTimeout(() => setPlaying(false), 200);
		return () => window.clearTimeout(timer);
	}, [completedSteps, playing, typedLength]);

	const replay = () => {
		setTypedLength(0);
		setCompletedSteps(0);
		setPlaying(true);
	};

	const togglePlayback = () => {
		if (completedSteps === demoSteps.length) {
			replay();
			return;
		}
		setPlaying((current) => !current);
	};

	const isTyping = typedLength < demoPrompt.length;
	const visibleMessages = Math.min(Math.max(completedSteps - 1, 0), demoMessages.length);
	const statusText = isTyping
		? 'Đang nhập yêu cầu…'
		: completedSteps < demoSteps.length
			? 'Đội agent đang xử lý…'
			: 'Quy trình đã hoàn tất';

	return (
		<div className="workflow-demo">
			<div className="workflow-command">
				<div className="workflow-window-bar">
					<div className="workflow-traffic-lights" aria-hidden="true">
						<span />
						<span />
						<span />
					</div>
					<p>vagents · không gian làm việc</p>
					<Terminal aria-hidden="true" />
				</div>
				<div className="workflow-command-body">
					<div className="workflow-prompt">
						<span className="workflow-prompt-arrow" aria-hidden="true">
							›
						</span>
						<p>
							<span className="sr-only">{demoPrompt}</span>
							<span aria-hidden="true">
								{demoPrompt.slice(0, typedLength)}
								{isTyping && <span className="workflow-typing-caret" />}
							</span>
						</p>
					</div>
					<div
						className="workflow-messages"
						role="log"
						aria-live="polite"
						aria-label="Kết quả mô phỏng từng Agent"
					>
						{demoMessages.slice(0, visibleMessages).map((message) => (
							<div className="workflow-message" key={message.agent}>
								<span className="workflow-message-avatar">
									<img src={message.image} alt="" />
								</span>
								<span>
									<strong>{message.agent}</strong>
									<small>{message.body}</small>
								</span>
								<Check className="workflow-message-check" aria-hidden="true" />
							</div>
						))}
					</div>
				</div>
				<div className="workflow-command-footer">
					<span className="workflow-status">
						<i className="workflow-live-dot" />
						{statusText}
					</span>
					<span>{completedSteps}/5 bước</span>
				</div>
			</div>

			<div className="workflow-flow">
				<div className="workflow-flow-title">
					<div>
						<CheckCheck />
						<strong>Luồng quy trình</strong>
					</div>
					<button
						type="button"
						className="workflow-pause-button"
						onClick={togglePlayback}
						aria-label={playing ? 'Tạm dừng demo' : 'Tiếp tục demo'}
					>
						{playing ? <Pause /> : <Play />}
					</button>
				</div>
				<ol>
					{demoSteps.map((step, index) => {
						const done = index < completedSteps;
						return (
							<li key={step} className={done ? 'is-done' : ''}>
								<span>{index + 1}</span>
								<p>{step}</p>
								{index < demoSteps.length - 1 && <i aria-hidden="true" />}
							</li>
						);
					})}
				</ol>
				<button type="button" className="workflow-replay-button" onClick={replay}>
					<RefreshCw />
					Chạy lại demo
				</button>
			</div>
		</div>
	);
}

export function LandingPage() {
	const [menuOpen, setMenuOpen] = useState(false);
	const [useCaseIndex, setUseCaseIndex] = useState(0);
	const [email, setEmail] = useState('');
	const [newsletterMessage, setNewsletterMessage] = useState('');
	const activeUseCase = useCases[useCaseIndex];
	const ActiveUseCaseIcon = activeUseCase.icon;

	useEffect(() => {
		document.title = 'VAgents | Đội ngũ AI cho mọi quy trình';
	}, []);

	const submitNewsletter = (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setNewsletterMessage('Cảm ơn bạn. Chúng tôi sẽ gửi cập nhật khi có tin mới.');
		setEmail('');
	};

	return (
		<div className="landing-page">
			<a className="landing-skip" href="#main-content">
				Đến nội dung chính
			</a>
			<header className="landing-header">
				<a className="landing-brand" href="/" aria-label="VAgents - Trang chủ">
					<BrandMark className="landing-brand-mark" />
					<span>VAgents</span>
				</a>

				<nav
					className={menuOpen ? 'landing-nav is-open' : 'landing-nav'}
					aria-label="Điều hướng chính"
				>
					<a href="#how" onClick={() => setMenuOpen(false)}>
						Cách hoạt động
					</a>
					<a href="#team" onClick={() => setMenuOpen(false)}>
						Đội ngũ Agent
					</a>
					<a href="#demo" onClick={() => setMenuOpen(false)}>
						Demo
					</a>
					<a href="#integrations" onClick={() => setMenuOpen(false)}>
						Tích hợp
					</a>
					<a href="#faq" onClick={() => setMenuOpen(false)}>
						FAQ
					</a>
				</nav>

				<div className="landing-header-actions">
					<a className="landing-login" href="/login">
						Đăng nhập
					</a>
					<a className="landing-button landing-button-small" href="/register">
						Đăng ký
					</a>
					<button
						type="button"
						className="landing-menu-button"
						aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'}
						aria-expanded={menuOpen}
						onClick={() => setMenuOpen((current) => !current)}
					>
						{menuOpen ? <X /> : <Menu />}
					</button>
				</div>
			</header>

			<main id="main-content">
				<section className="landing-hero">
					<div
						className="landing-hero-aurora landing-hero-aurora-orange"
						aria-hidden="true"
					/>
					<div
						className="landing-hero-aurora landing-hero-aurora-blue"
						aria-hidden="true"
					/>
					<div
						className="landing-hero-aurora landing-hero-aurora-cyan"
						aria-hidden="true"
					/>
					<div className="landing-hero-stars" aria-hidden="true" />
					<div className="landing-shell landing-hero-grid">
						<div className="landing-hero-copy">
							<div className="landing-badge">
								<span>Mới</span>
								Nền tảng AI Agent cho doanh nghiệp Việt
							</div>
							<h1>
								<span>Một ý tưởng.</span>
								<strong>Cả đội ngũ AI</strong>
								<span>cùng hành động.</span>
							</h1>
							<p>
								Giao một mục tiêu, VAgents tự lập đội agent chuyên trách, kết nối
								công cụ bạn đang dùng và vận hành quy trình từ đầu đến cuối.
							</p>
							<div className="landing-hero-pillars" aria-label="Năng lực chính">
								<span>
									<Box /> Tạo Agent
								</span>
								<span>
									<PlugZap /> Kết nối công cụ
								</span>
								<span>
									<Workflow /> Vận hành mọi quy trình
								</span>
							</div>
							<div className="landing-hero-actions">
								<a className="landing-button" href="/register">
									Tạo đội Agent đầu tiên <ArrowRight />
								</a>
								<a className="landing-button landing-button-secondary" href="#demo">
									<span className="landing-play-ring">
										<Play />
									</span>{' '}
									Xem demo
								</a>
							</div>
						</div>

						<div
							className="landing-hero-visual"
							aria-label="Ví dụ hoạt động của đội Agent"
							onPointerMove={(event) => {
								const bounds = event.currentTarget.getBoundingClientRect();
								const x = (event.clientX - bounds.left) / bounds.width - 0.5;
								const y = (event.clientY - bounds.top) / bounds.height - 0.5;
								event.currentTarget.style.setProperty(
									'--hero-tilt-x',
									`${-y * 4}deg`,
								);
								event.currentTarget.style.setProperty(
									'--hero-tilt-y',
									`${x * 4}deg`,
								);
							}}
							onPointerLeave={(event) => {
								event.currentTarget.style.setProperty('--hero-tilt-x', '0deg');
								event.currentTarget.style.setProperty('--hero-tilt-y', '0deg');
							}}
						>
							<div
								className="landing-hero-orbit landing-hero-orbit-cyan"
								aria-hidden="true"
							/>
							<div
								className="landing-hero-orbit landing-hero-orbit-orange"
								aria-hidden="true"
							/>
							<div className="landing-hero-frame">
								<img
									src={agentTeam}
									alt="Năm mascot VAgents cùng đứng trên nền tảng chữ V: chăm sóc khách hàng, điều phối, kỹ sư, phân tích và dữ liệu"
								/>
							</div>
							<div className="hero-note hero-note-left">
								<MessageSquareText />
								<span>
									<strong>Agent CSKH</strong>
									<small>Đang trả lời khách…</small>
								</span>
							</div>
							<div className="hero-note hero-note-top">
								<Check />
								<span>
									<strong>Đơn hàng đã xử lý</strong>
									<small>
										<i className="workflow-live-dot" /> Tự động · vừa xong
									</small>
								</span>
							</div>
							<div className="hero-note hero-note-right">
								<ChartNoAxesCombined />
								<span>
									<strong>Báo cáo ngày đã sẵn sàng</strong>
									<small>Agent Phân tích</small>
								</span>
							</div>
							<small className="landing-hero-caption">
								Minh họa hoạt động của đội Agent
							</small>
						</div>
					</div>
					<div className="landing-hero-grid-floor" aria-hidden="true" />
					<a className="landing-scroll-hint" href="#how" aria-label="Cuộn">
						<span>
							<i />
						</span>
					</a>
				</section>

				<div className="capability-strip" aria-label="Khả năng của đội agent">
					<div className="capability-track">
						{[...capabilities, ...capabilities].map(({ icon: Icon, label }, index) => (
							<span
								key={`${label}-${index}`}
								aria-hidden={index >= capabilities.length}
							>
								<Icon /> {label}
							</span>
						))}
					</div>
				</div>

				<section
					className="landing-section landing-how"
					id="how"
					aria-labelledby="how-title"
				>
					<div className="landing-shell">
						<div className="landing-section-heading">
							<span className="landing-eyebrow">Cách hoạt động</span>
							<h2 id="how-title">
								Từ mục tiêu đến quy trình thật <strong>chỉ trong 3 bước.</strong>
							</h2>
						</div>
						<div className="process-grid">
							{processSteps.map(({ icon: Icon, label, title, body }, index) => (
								<article className="process-step" key={title}>
									<div className="process-icon">
										<Icon />
										<span>0{index + 1}</span>
									</div>
									<small>{label}</small>
									<h3>{title}</h3>
									<p>{body}</p>
								</article>
							))}
						</div>
					</div>
				</section>

				<section
					className="landing-section landing-team"
					id="team"
					aria-labelledby="team-title"
				>
					<div className="landing-shell">
						<div className="landing-section-heading">
							<h2 id="team-title">
								Năm agent, <strong>một tinh thần đồng đội.</strong>
							</h2>
							<p>
								Mỗi agent có chuyên môn riêng và biết chính xác lúc nào cần chuyển
								việc cho đồng đội.
							</p>
						</div>
						<div className="agent-grid">
							{agents.map((agent) => (
								<article
									className={
										agent.featured ? 'agent-card is-featured' : 'agent-card'
									}
									key={agent.name}
								>
									<div className="agent-portrait">
										<img
											src={agent.image}
											alt={`${agent.name}, ${agent.role}`}
										/>
									</div>
									<small>{agent.role}</small>
									<h3>{agent.name}</h3>
									<p>{agent.body}</p>
									<div className="agent-tags">
										{agent.tags.map((tag) => (
											<span key={tag}>{tag}</span>
										))}
									</div>
								</article>
							))}
						</div>
					</div>
				</section>

				<section
					className="landing-section landing-demo"
					id="demo"
					aria-labelledby="demo-title"
				>
					<div className="landing-shell">
						<div className="landing-section-heading landing-section-heading-centered">
							<span className="landing-eyebrow">Xem đội agent làm việc</span>
							<h2 id="demo-title">
								Bạn ra lệnh một câu. <strong>Cả đội cùng xử lý.</strong>
							</h2>
							<p className="landing-demo-disclaimer">
								Mô phỏng minh họa. Không gửi yêu cầu hoặc thay đổi dữ liệu thật.
							</p>
						</div>
						<WorkflowDemo />
					</div>
				</section>

				<section
					className="landing-section landing-integrations"
					id="integrations"
					aria-labelledby="integrations-title"
				>
					<div className="landing-shell integrations-grid">
						<div
							className="integration-orbit"
							aria-label="Các công cụ kết nối quanh VAgents"
						>
							{[0, 1, 2].map((trackIndex) => (
								<div
									className={`orbit-track orbit-track-${trackIndex + 1}`}
									key={trackIndex}
								>
									{integrations
										.slice(trackIndex * 4, trackIndex * 4 + 4)
										.map(({ icon: Icon, label }, index) => (
											<span
												className={`orbit-node-position orbit-node-position-${index + 1}`}
												key={label}
											>
												<span className="orbit-node-counter">
													<span
														className="integration-node"
														aria-label={label}
													>
														<Icon />
														<span className="integration-tooltip">
															{label}
														</span>
													</span>
												</span>
											</span>
										))}
								</div>
							))}
							<div className="integration-core">
								<BrandMark />
							</div>
						</div>
						<div className="integration-copy">
							<h2 id="integrations-title">
								Kết nối mọi công cụ <strong>bạn đang dùng.</strong>
							</h2>
							<p>
								Agent đọc, ghi và thực thi trong hệ thống của bạn theo đúng chính
								sách quyền.
							</p>
							<div className="integration-list">
								<div>
									<MessageSquareText />
									<span>
										<strong>Kênh giao tiếp</strong>Email, chat nội bộ và kênh hỗ
										trợ khách hàng.
									</span>
								</div>
								<div>
									<DatabaseZap />
									<span>
										<strong>Dữ liệu và tài liệu</strong>Bảng tính, kho tài liệu,
										API và cơ sở dữ liệu.
									</span>
								</div>
								<div>
									<ShieldCheck />
									<span>
										<strong>Quản trị an toàn</strong>Phân quyền, phê duyệt và
										nhật ký thực thi.
									</span>
								</div>
							</div>
						</div>
					</div>
				</section>

				<section
					className="landing-section landing-use-cases"
					aria-labelledby="use-cases-title"
				>
					<div className="landing-shell">
						<div className="landing-section-heading">
							<h2 id="use-cases-title">
								Một nền tảng. <strong>Mọi phòng ban.</strong>
							</h2>
						</div>
						<div className="use-cases-layout">
							<div className="use-case-tabs" role="tablist" aria-label="Phòng ban">
								{useCases.map(({ name, icon: Icon }, index) => (
									<button
										type="button"
										role="tab"
										aria-selected={useCaseIndex === index}
										onClick={() => setUseCaseIndex(index)}
										key={name}
									>
										<Icon /> {name} <ArrowRight />
									</button>
								))}
							</div>
							<article className="use-case-panel" role="tabpanel">
								<div className="use-case-panel-icon">
									<ActiveUseCaseIcon />
								</div>
								<h3>{activeUseCase.title}</h3>
								<p>{activeUseCase.body}</p>
								<ul>
									{activeUseCase.items.map((item) => (
										<li key={item}>
											<Check /> {item}
										</li>
									))}
								</ul>
							</article>
						</div>
					</div>
				</section>

				<section className="landing-stats" aria-label="Thông tin nền tảng">
					<div className="landing-shell stats-grid">
						<div>
							<strong>24/7</strong>
							<span>Agent làm việc liên tục</span>
						</div>
						<div>
							<strong>5</strong>
							<span>Vai trò mẫu sẵn sàng</span>
						</div>
						<div>
							<strong>3</strong>
							<span>Bước để bắt đầu</span>
						</div>
						<div>
							<strong>API</strong>
							<span>Kết nối linh hoạt</span>
						</div>
					</div>
				</section>

				<section
					className="landing-section landing-faq"
					id="faq"
					aria-labelledby="faq-title"
				>
					<div className="landing-shell faq-grid">
						<div className="landing-section-heading">
							<h2 id="faq-title">Câu hỏi thường gặp</h2>
							<p>
								Những điều đội ngũ thường muốn biết trước khi đưa agent vào quy
								trình thật.
							</p>
						</div>
						<div className="faq-list">
							{faqs.map((faq) => (
								<details key={faq.question}>
									<summary>
										{faq.question}
										<ChevronDown />
									</summary>
									<p>{faq.answer}</p>
								</details>
							))}
						</div>
					</div>
				</section>

				<section className="landing-final-cta" aria-labelledby="cta-title">
					<div className="landing-shell final-cta-card">
						<div>
							<Sparkles />
							<h2 id="cta-title">
								Sẵn sàng giao việc cho <strong>đội ngũ AI của bạn?</strong>
							</h2>
							<p>
								Một mục tiêu là đủ để bắt đầu. Phần phối hợp, hãy để các agent lo.
							</p>
							<a className="landing-button" href="/register">
								Dùng thử miễn phí <ArrowRight />
							</a>
						</div>
						<div className="cta-mascots" aria-label="Năm agent AI sẵn sàng nhận việc">
							<img
								className="cta-mascot cta-mascot-1"
								src={agentSupport}
								alt="Agent chăm sóc khách hàng"
							/>
							<img
								className="cta-mascot cta-mascot-2"
								src={agentCoordinator}
								alt="Agent điều phối"
							/>
							<img
								className="cta-mascot cta-mascot-3"
								src={agentEngineer}
								alt="Agent kỹ sư"
							/>
							<img
								className="cta-mascot cta-mascot-4"
								src={agentAnalyst}
								alt="Agent phân tích"
							/>
							<img
								className="cta-mascot cta-mascot-5"
								src={agentIntegrations}
								alt="Agent dữ liệu"
							/>
						</div>
					</div>
				</section>
			</main>

			<footer className="landing-footer">
				<div className="landing-shell footer-grid">
					<div className="footer-brand-column">
						<a className="landing-brand" href="/">
							<BrandMark className="landing-brand-mark" />
							<span>VAgents</span>
						</a>
						<p>Tạo agent, kết nối công cụ và vận hành mọi quy trình.</p>
						<form onSubmit={submitNewsletter}>
							<label htmlFor="newsletter-email">Nhận tin mới từ VAgents</label>
							<div>
								<input
									id="newsletter-email"
									type="email"
									value={email}
									onChange={(event) => setEmail(event.target.value)}
									placeholder="ban@congty.vn"
									required
								/>
								<button type="submit">
									Đăng ký <ArrowRight />
								</button>
							</div>
							<p className="newsletter-message" aria-live="polite">
								{newsletterMessage}
							</p>
						</form>
					</div>
					<div>
						<h3>Sản phẩm</h3>
						<a href="#how">Cách hoạt động</a>
						<a href="#team">Đội ngũ Agent</a>
						<a href="#integrations">Tích hợp</a>
					</div>
					<div>
						<h3>Tài nguyên</h3>
						<a href="#faq">FAQ</a>
						<a href="#demo">Demo</a>
						<a href="/login">Đăng nhập</a>
					</div>
					<div>
						<h3>Bắt đầu</h3>
						<a href="/register">Tạo tài khoản</a>
						<a href="mailto:hello@vagents.ai">hello@vagents.ai</a>
					</div>
				</div>
				<div className="landing-shell footer-bottom">
					<span>© 2026 VAgents</span>
					<div>
						<a href="#">Điều khoản</a>
						<a href="#">Bảo mật</a>
					</div>
				</div>
			</footer>
		</div>
	);
}
