import {
	ArrowLeft,
	ArrowRight,
	BookOpen,
	Bot,
	Check,
	CheckCheck,
	ChevronRight,
	CircleAlert,
	FlaskConical,
	Loader2,
	MessageSquare,
	Plus,
	Send,
	Settings2,
	Sparkles,
	Wrench,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { canCreate, knowledgeOptions, scenarios, toolOptions } from './model';
import type { DemoAgent, Scenario } from './model';
import { useBuilderDemo } from './useBuilderDemo';

import './builder-demo.css';

function AgentEditor({
	agent,
	disabled,
	onChange,
}: {
	agent: DemoAgent;
	disabled: boolean;
	onChange: (patch: Partial<DemoAgent>) => void;
}) {
	return (
		<fieldset className="bd-editor" disabled={disabled}>
			<label>
				Tên agent
				<input
					value={agent.name}
					maxLength={100}
					onChange={(e) => onChange({ name: e.target.value })}
				/>
			</label>
			<label>
				Nhiệm vụ
				<textarea
					rows={3}
					value={agent.objective}
					maxLength={1000}
					onChange={(e) => onChange({ objective: e.target.value })}
				/>
			</label>
			<label>
				Hướng dẫn hoạt động
				<textarea
					rows={5}
					value={agent.instructions}
					maxLength={4000}
					onChange={(e) => onChange({ instructions: e.target.value })}
				/>
			</label>
			<div>
				<h3>
					<Wrench size={15} /> Công cụ <span>Chọn ít nhất một</span>
				</h3>
				<div className="bd-choices">
					{toolOptions.map((tool) => (
						<label key={tool}>
							<input
								type="checkbox"
								checked={agent.tools.includes(tool)}
								onChange={(e) =>
									onChange({
										tools: e.target.checked
											? [...agent.tools, tool]
											: agent.tools.filter((t) => t !== tool),
									})
								}
							/>
							{tool}
						</label>
					))}
				</div>
			</div>
			<div>
				<h3>
					<BookOpen size={15} /> Nguồn kiến thức <span>Tùy chọn</span>
				</h3>
				<div className="bd-choices">
					{knowledgeOptions.map((kb) => (
						<label key={kb}>
							<input
								type="checkbox"
								checked={agent.knowledge.includes(kb)}
								onChange={(e) =>
									onChange({
										knowledge: e.target.checked
											? [...agent.knowledge, kb]
											: agent.knowledge.filter((k) => k !== kb),
									})
								}
							/>
							{kb}
						</label>
					))}
				</div>
			</div>
			{!canCreate([{ ...agent, blocker: undefined }]) && (
				<p className="bd-validation">
					Điền đủ tên, nhiệm vụ, hướng dẫn và chọn ít nhất một công cụ.
				</p>
			)}
		</fieldset>
	);
}

export function BuilderDemoPage() {
	const demo = useBuilderDemo();
	const { state, busy } = demo;
	const [draft, setDraft] = useState('');
	const [scenario, setScenario] = useState<Scenario>(state.scenario);
	const [selectedId, setSelectedId] = useState('');
	const [mobileTab, setMobileTab] = useState<'chat' | 'proposal'>('chat');
	const end = useRef<HTMLDivElement>(null);
	const agent = state.agents.find((a) => a.id === selectedId) ?? state.agents[0];
	const phase = { start: 0, clarify: 0, outline: 1, configure: 2, done: 3 }[state.stage];
	useEffect(() => {
		end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
	}, [state.messages.length, busy]);
	const reset = () => {
		demo.reset();
		setDraft('');
		setSelectedId('');
		setScenario('knowledge');
		setMobileTab('chat');
	};
	const send = async () => {
		const text = draft.trim();
		if (!text || busy) return;
		if (await demo.run({ type: 'message', text, scenario })) setDraft('');
	};
	return (
		<div className="builder-demo">
			<header className="bd-header">
				<div className="bd-brand">
					<a href="/agents" aria-label="Về quản lý agent" className="bd-back">
						<ArrowLeft size={18} />
					</a>
					<span className="bd-logo">
						<Sparkles size={20} />
					</span>
					<div>
						<strong>Agent Builder</strong>
						<small>Biến ý tưởng thành trợ lý của bạn</small>
					</div>
					<span className="bd-badge">DEMO</span>
				</div>
				<button className="bd-button bd-secondary" onClick={reset}>
					<Plus size={16} /> Bắt đầu lại
				</button>
			</header>
			<div className="bd-steps" aria-label="Tiến trình tạo agent">
				{['Mô tả nhu cầu', 'Duyệt phương án', 'Cấu hình agent', 'Hoàn tất'].map(
					(step, index) => (
						<div
							key={step}
							className={
								index === phase ? 'current' : index < phase ? 'complete' : ''
							}
							aria-current={index === phase ? 'step' : undefined}
						>
							<span>{index < phase ? <Check size={13} /> : index + 1}</span>
							{step}
							{index < 3 && <ChevronRight className="bd-step-arrow" size={14} />}
						</div>
					),
				)}
			</div>
			{demo.error && (
				<div className="bd-error bd-global-error" role="alert">
					<CircleAlert size={17} />
					<span>{demo.error}</span>
					<button
						disabled={busy}
						onClick={async () => {
							if (await demo.retry()) setDraft('');
						}}
					>
						Thử lại
					</button>
				</div>
			)}
			<div className="bd-mobile-tabs">
				<button aria-pressed={mobileTab === 'chat'} onClick={() => setMobileTab('chat')}>
					<MessageSquare size={16} /> Hội thoại
				</button>
				<button
					aria-pressed={mobileTab === 'proposal'}
					onClick={() => setMobileTab('proposal')}
				>
					<Settings2 size={16} /> Đề xuất{' '}
					{state.agents.length > 0 && `(${state.agents.length})`}
				</button>
			</div>
			<main className="bd-workspace">
				<section
					className={`bd-conversation ${mobileTab !== 'chat' ? 'bd-mobile-hidden' : ''}`}
					aria-label="Hội thoại với Builder"
				>
					<div className="bd-section-title">
						<span>
							<span className="bd-live-dot" /> Builder Assistant
						</span>
						<small>Kịch bản tương tác mẫu</small>
					</div>
					<div className="bd-chat-scroll">
						{state.stage === 'start' && (
							<div className="bd-welcome">
								<span className="bd-welcome-icon">
									<Sparkles size={28} />
								</span>
								<p className="bd-eyebrow">BẮT ĐẦU TỪ MỘT Ý TƯỞNG</p>
								<h1>
									Bạn muốn agent
									<br />
									giúp việc gì?
								</h1>
								<p>
									Mô tả công việc, chọn một kịch bản và cùng Builder thiết kế đội
									ngũ phù hợp.
								</p>
								<div className="bd-scenarios">
									{scenarios.map((item, i) => (
										<button
											key={item.id}
											aria-pressed={scenario === item.id}
											onClick={() => {
												setScenario(item.id);
												setDraft(item.prompt);
											}}
										>
											<span className="bd-scenario-number">0{i + 1}</span>
											<span>
												<strong>{item.title}</strong>
												<small>{item.description}</small>
											</span>
											<ArrowRight size={16} />
										</button>
									))}
								</div>
							</div>
						)}
						{state.messages.map((message) => (
							<div className={`bd-message ${message.role}`} key={message.id}>
								{message.role === 'builder' && (
									<span className="bd-message-avatar">
										<Sparkles size={16} />
									</span>
								)}
								<div>
									<small>{message.role === 'builder' ? 'Builder' : 'Bạn'}</small>
									<p>{message.text}</p>
								</div>
							</div>
						))}
						{state.stage === 'clarify' && !busy && (
							<button
								className="bd-suggestion"
								onClick={() =>
									setDraft(
										'Phục vụ khách hàng bằng tiếng Việt, trả lời ngắn gọn và xác nhận trước khi đặt dịch vụ.',
									)
								}
							>
								<Plus size={14} /> Dùng câu trả lời mẫu
							</button>
						)}
						{busy && (
							<p className="bd-thinking" role="status">
								<Loader2 size={16} className="animate-spin" />
								{state.stage === 'configure'
									? 'Đang mô phỏng tạo agent…'
									: 'Builder đang chuẩn bị phản hồi…'}
							</p>
						)}
						<div ref={end} />
					</div>
					<div className="bd-composer-area">
						{['start', 'clarify'].includes(state.stage) ? (
							<form
								className="bd-composer"
								onSubmit={(e) => {
									e.preventDefault();
									void send();
								}}
							>
								<label className="sr-only" htmlFor="builder-demo-message">
									Yêu cầu của bạn
								</label>
								<textarea
									id="builder-demo-message"
									placeholder={
										state.stage === 'start'
											? 'Ví dụ: Tôi cần một trợ lý hỗ trợ cư dân…'
											: 'Bổ sung đối tượng sử dụng và mong muốn của bạn…'
									}
									value={draft}
									maxLength={4000}
									disabled={busy}
									onChange={(e) => setDraft(e.target.value)}
									rows={3}
								/>
								<div>
									<small>
										{state.stage === 'start'
											? `Kịch bản: ${scenarios.find((s) => s.id === scenario)?.title}`
											: 'Nội dung chỉ dùng trong phiên demo'}{' '}
										· {draft.length}/4000
									</small>
									<button
										className="bd-send"
										type="submit"
										aria-label="Gửi yêu cầu"
										disabled={busy || !draft.trim()}
									>
										<Send size={17} />
									</button>
								</div>
							</form>
						) : (
							<div className="bd-chat-next">
								<CheckCheck size={18} />
								<span>
									{state.stage === 'done'
										? 'Phiên tạo agent đã hoàn tất.'
										: 'Tiếp tục với phương án ở phần Đề xuất.'}
								</span>
								<button onClick={() => setMobileTab('proposal')}>
									Xem đề xuất <ArrowRight size={14} />
								</button>
							</div>
						)}
						<details className="bd-demo-options">
							<summary>
								<FlaskConical size={13} /> Tùy chọn demo
							</summary>
							<label>
								<input
									type="checkbox"
									checked={demo.failNext}
									disabled={busy || state.stage === 'done'}
									onChange={(e) => demo.setFailNext(e.target.checked)}
								/>{' '}
								Giả lập lỗi ở thao tác tiếp theo
							</label>
							<p>Phản hồi theo kịch bản mẫu, không gọi AI hoặc API tạo agent.</p>
						</details>
						{demo.storageWarning && (
							<p role="status" className="bd-validation">
								Trình duyệt không cho lưu phiên. Tải lại trang sẽ mất tiến trình
								demo.
							</p>
						)}
					</div>
				</section>
				<section
					className={`bd-proposal ${mobileTab !== 'proposal' ? 'bd-mobile-hidden' : ''}`}
					aria-label="Đề xuất agent"
				>
					<div className="bd-section-title">
						<span>
							<Settings2 size={16} /> Đề xuất của bạn
						</span>
						<small>
							{state.agents.length ? `${state.agents.length} agent` : 'Chưa có agent'}
						</small>
					</div>
					{!state.agents.length ? (
						<div className="bd-empty">
							<div className="bd-empty-illustration">
								<span>
									<Bot size={33} />
								</span>
								<span>
									<Wrench size={19} />
								</span>
								<span>
									<BookOpen size={19} />
								</span>
							</div>
							<h2>Một đội ngũ đang chờ ý tưởng</h2>
							<p>
								Sau khi hiểu nhu cầu, Builder sẽ đề xuất vai trò, công cụ và nguồn
								kiến thức cho từng agent tại đây.
							</p>
							<div className="bd-empty-checks">
								<span>
									<Check size={14} /> Vai trò rõ ràng
								</span>
								<span>
									<Check size={14} /> Công cụ phù hợp
								</span>
								<span>
									<Check size={14} /> Bạn luôn kiểm soát
								</span>
							</div>
						</div>
					) : (
						<>
							<div className="bd-proposal-scroll">
								{state.stage === 'done' && (
									<div className="bd-success" role="status">
										<span>
											<CheckCheck size={24} />
										</span>
										<h2>Đội ngũ của bạn đã sẵn sàng!</h2>
										<p>
											Đã hoàn tất mô phỏng. Các agent bên dưới chưa được tạo
											trên hệ thống thật.
										</p>
									</div>
								)}
								<div className="bd-agent-list">
									{state.agents.map((item, index) => (
										<button
											className={`bd-agent-card ${agent?.id === item.id ? 'selected' : ''}`}
											key={item.id}
											onClick={() => setSelectedId(item.id)}
											aria-pressed={agent?.id === item.id}
										>
											<span className={`bd-agent-icon color-${index % 2}`}>
												<Bot size={22} />
											</span>
											<span>
												<small>
													AGENT 0{index + 1}{' '}
													<i>
														{item.blocker
															? 'Cần bổ sung'
															: state.stage === 'done'
																? 'Demo hoàn tất'
																: 'Bản nháp'}
													</i>
												</small>
												<strong>{item.name || 'Agent chưa đặt tên'}</strong>
												<p>{item.objective}</p>
												<span className="bd-agent-meta">
													{item.tools.length} công cụ ·{' '}
													{item.knowledge.length} nguồn kiến thức
												</span>
											</span>
											<ChevronRight size={16} />
										</button>
									))}
								</div>
								{agent?.blocker && (
									<div className="bd-blocker" role="alert">
										<CircleAlert size={18} />
										<div>
											<strong>Cần bổ sung công cụ</strong>
											<p>{agent.blocker}</p>
											<button onClick={reset}>
												Chọn kịch bản khác <ArrowRight size={13} />
											</button>
										</div>
									</div>
								)}
								{agent && state.stage !== 'outline' && (
									<>
										<div className="bd-editor-heading">
											<h2>
												{state.stage === 'done'
													? 'Cấu hình đã tạo thử'
													: 'Tinh chỉnh agent'}
											</h2>
											<p>
												{state.stage === 'done'
													? 'Bạn có thể chọn từng agent để xem lại cấu hình.'
													: 'Điều chỉnh để agent làm việc theo cách bạn muốn.'}
											</p>
										</div>
										<AgentEditor
											agent={agent}
											disabled={busy || state.stage !== 'configure'}
											onChange={(patch) => demo.edit(agent.id, patch)}
										/>
									</>
								)}
								{state.stage === 'outline' && (
									<div className="bd-outline-note">
										<Sparkles size={18} />
										<p>
											Mỗi agent đảm nhận một nhiệm vụ riêng. Duyệt phương án
											để chọn công cụ và chỉnh hướng dẫn chi tiết.
										</p>
									</div>
								)}
							</div>
							<footer className="bd-proposal-footer">
								<p>
									{state.stage === 'done'
										? 'Chỉ lưu trong phiên trình duyệt này'
										: state.stage === 'outline'
											? 'Bạn có thể chỉnh cấu hình ở bước tiếp theo'
											: 'Thông tin bắt buộc: tên, nhiệm vụ, hướng dẫn và công cụ'}
								</p>
								<button
									className="bd-button bd-primary"
									disabled={
										busy ||
										(state.stage === 'configure' && !canCreate(state.agents))
									}
									onClick={() =>
										state.stage === 'done'
											? reset()
											: void demo.run({
													type:
														state.stage === 'outline'
															? 'approve'
															: 'publish',
												})
									}
								>
									{busy ? (
										<Loader2 size={16} className="animate-spin" />
									) : state.stage === 'done' ? (
										<Plus size={16} />
									) : (
										<Sparkles size={16} />
									)}
									{state.stage === 'done'
										? 'Tạo một đội ngũ mới'
										: state.stage === 'outline'
											? 'Duyệt phương án'
											: `Tạo thử ${state.agents.length} agent`}
									<ArrowRight size={16} />
								</button>
							</footer>
						</>
					)}
				</section>
			</main>
		</div>
	);
}
