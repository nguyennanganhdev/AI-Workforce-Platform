import {
	ArrowUp,
	BookText,
	Bot,
	Check,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	GitBranchPlus,
	LibraryBig,
	Plus,
	Recycle,
	Rocket,
	Sparkles,
	Trash2,
	Wand2,
	Wrench,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { workforceApi } from '@/api';
import type {
	BuilderConversationSummary,
	BuilderMessage,
	BuilderProposal,
	ChatModelConfig,
	DuplicateDecision,
	PlannedAgent,
	WorkforceAgent,
} from '@/api';
import robotStill from '@/assets/images/stickers/robot-still.webp';
import { sessionTime } from '@/components/chat/session-row-utils';
import { ChatRow } from '@/components/chat/SessionRow';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Markdown } from '@/components/markdown';
import { LlmSelect } from '@/components/select/LlmSelect';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { ClayPortrait, type PortraitKey } from '@/components/ui/clay-portrait';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { TaskProgress } from '@/components/ui/task-progress';
import { Textarea } from '@/components/ui/textarea';
import { EvaluationProgress } from '@/components/workforce/EvaluationProgress';
import { EvaluationReport } from '@/components/workforce/EvaluationReport';
import { useEvaluationProgress } from '@/hooks/useEvaluationProgress';
import { cn } from '@/lib/utils';

function prefersVietnamese(text: string) {
	const normalized = text.toLocaleLowerCase('vi-VN');
	return (
		/[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/i.test(
			normalized,
		) ||
		['tôi', 'bạn', 'hãy', 'muốn', 'không'].filter((word) =>
			normalized.includes(word),
		).length >= 2
	);
}

/** What each Builder evaluation check means, for the checks that failed. */
const CHECK_LABEL: Record<string, string> = {
	system_prompt: 'prompt quá ngắn',
	registered_tools: 'chọn tool không có trong MCP',
	exclusive_tool_assignment: 'tool trùng với agent khác trong đội',
	capability_has_tools: 'chưa có tool cho việc của mình',
	registered_library: 'kho tri thức hoặc skill không có thật',
	skill: 'chưa có skill',
};

function AgentProposalCard({ proposal }: { proposal: BuilderProposal['agents'][number] }) {
	const passed = proposal.evaluation.passed === true;
	const reused = proposal.reuse_agent_id !== null;
	const failed = Object.entries((proposal.evaluation.checks ?? {}) as Record<string, boolean>)
		.filter(([, ok]) => !ok)
		.map(([check]) => CHECK_LABEL[check] ?? check);

	return (
		<article className="rounded-2xl border border-border/70 bg-background p-4">
			<header className="flex items-start gap-3">
				<ClayAvatar id={proposal.reuse_agent_id ?? proposal.name} label={proposal.name} size={40} />
				<div className="min-w-0 flex-1">
					<div className="flex flex-wrap items-center gap-2">
						<h3 className="text-[15px]/5 font-semibold">{proposal.name}</h3>
						<Badge variant={passed ? 'secondary' : 'destructive'}>
							{passed ? <CheckCircle2 /> : <CircleAlert />}
							{passed ? 'Kiểm thử đạt' : 'Chưa đủ điều kiện phát hành'}
						</Badge>
					</div>
					<p className="mt-1 text-sm text-muted-foreground">{proposal.objective}</p>
					{failed.length > 0 && <p className="mt-1 text-xs text-destructive">Chưa đạt: {failed.join('; ')}.</p>}
					{proposal.evaluation.publish_blocker && <p className="mt-1 text-xs text-destructive">{proposal.evaluation.publish_blocker}</p>}
				</div>
			</header>

			<div className="mt-3 flex flex-wrap gap-1.5 text-xs">
				{proposal.selected_tools.map((tool) => (
					<span
						key={tool.id}
						title={tool.description ?? undefined}
						className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 font-mono"
					>
						<Wrench className="size-3" /> {tool.tool_name}
					</span>
				))}
				{proposal.knowledge?.map((kb) => (
					<span key={kb.kb_id} className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5">
						<LibraryBig className="size-3" /> {kb.name}
					</span>
				))}
				{proposal.library_skills?.map((skill) => (
					<span key={skill.skill_id} className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5">
						<BookText className="size-3" /> {skill.name}
					</span>
				))}
				{proposal.selected_tools.length === 0 && (
					<span className="text-muted-foreground">
						{proposal.evaluation.checks?.capability_has_tools
							? 'Điều phối đồng đội, không cần tool riêng.'
							: 'Chưa có tool phù hợp trong MCP đã đăng ký.'}
					</span>
				)}
			</div>

			{reused && (
				<p className="mt-3 flex items-start gap-2 rounded-xl bg-sky-50 p-2.5 text-sm text-sky-800 dark:bg-sky-950/30 dark:text-sky-300">
					<Recycle className="mt-0.5 size-4 shrink-0" />
					<span>
						Dùng lại nguyên vẹn <strong>{proposal.reuse_agent_name}</strong> đang phát hành; không sinh bản sao và
						không đổi agent đó.
					</span>
				</p>
			)}
			{proposal.update_agent_id && (
				<p className="mt-3 flex items-start gap-2 rounded-xl bg-violet-50 p-2.5 text-sm text-violet-800 dark:bg-violet-950/30 dark:text-violet-300">
					<GitBranchPlus className="mt-0.5 size-4 shrink-0" />
					<span>
						Phiên bản mới của <strong>{proposal.update_agent_name}</strong>; khi phát hành, agent đó lên phiên bản mới
						(có thể quay lại bản cũ ở trang quản lý agent).
					</span>
				</p>
			)}
			{proposal.evaluation.repair && (
				<p className="mt-3 flex items-start gap-2 rounded-xl bg-muted/60 p-2.5 text-sm">
					<Wand2 className="mt-0.5 size-4 shrink-0 text-primary" />
					<span>
						<strong>Builder đã sửa (vòng {proposal.evaluation.repair.round}):</strong> {proposal.evaluation.repair.explanation}{' '}
						<span className="text-muted-foreground">
							Trước khi sửa đạt {Math.round(proposal.evaluation.repair.previous_pass_rate * 100)}%.
						</span>
					</span>
				</p>
			)}

			<Collapsible className="mt-3">
				<CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
					Prompt{proposal.skill_markdown ? ' và skill' : ''} do Builder viết
					<ChevronRight className="size-3 transition-transform group-data-[state=open]:rotate-90" />
				</CollapsibleTrigger>
				<CollapsibleContent className="mt-2 space-y-2">
					<pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-xs leading-5">
						{proposal.system_prompt}
					</pre>
					{proposal.skill_markdown && (
						<pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">
							{proposal.skill_markdown}
						</pre>
					)}
				</CollapsibleContent>
			</Collapsible>
			{proposal.evaluation.model_report && <div className="mt-4 border-t pt-4"><EvaluationReport report={proposal.evaluation.model_report} configurationBlocker={failed.length ? `Cấu hình chưa đủ: ${failed.join('; ')}.` : undefined} /></div>}
			{!proposal.evaluation.model_report && proposal.tests && proposal.tests.length > 0 && (
				<details className="mt-3 text-sm">
					<summary className="cursor-pointer py-2 font-medium">{proposal.tests.length} ca kiểm thử</summary>
					<p className="mb-2 text-xs text-muted-foreground">{proposal.evaluation.model_report ? 'Đã chạy model và bộ chấm. Chỉ được phát hành khi kết quả khớp cấu hình này và mọi ca an toàn đạt.' : 'Kịch bản chưa được chạy bằng model; chưa được phát hành. Tạo lại cấu hình để kiểm thử.'}</p>
					<ol className="space-y-2">
						{proposal.tests.map((test, index) => (
							<li key={index} className="rounded-lg bg-muted/50 p-3">
								<p className="font-medium">Ca {index + 1}: {String(test.scenario ?? '')}</p>
								<p className="mt-1 text-muted-foreground">Mong đợi: {String(test.expected ?? '')}</p>
							</li>
						))}
					</ol>
				</details>
			)}
		</article>
	);
}

export function AgentBuilderPage() {
	const [searchParams, setSearchParams] = useSearchParams();
	const [message, setMessage] = useState('');
	const [conversationId, setConversationId] = useState<string | null>(() =>
		searchParams.get('conversation_id'),
	);
	const [conversation, setConversation] = useState<BuilderMessage[]>([]);
	const [conversations, setConversations] = useState<BuilderConversationSummary[]>([]);
	const [proposal, setProposal] = useState<BuilderProposal | null>(null);
	const [agents, setAgents] = useState<WorkforceAgent[]>([]);
	const [working, setWorking] = useState(false);
	const [task, setTask] = useState({ label: '', startedAt: 0 });
	const [lastLatency, setLastLatency] = useState<number | null>(null);
	const [contextInfo, setContextInfo] = useState({ messages: 0, summarized: false });
	const [selectedModel, setSelectedModel] = useState<ChatModelConfig | null>(null);
	const [credentialOpen, setCredentialOpen] = useState(false);
	const [credentialRefetchTrigger, setCredentialRefetchTrigger] = useState(0);
	const [agentsOpen, setAgentsOpen] = useState(false);
	const [deleting, setDeleting] = useState<BuilderConversationSummary | null>(null);
	const [decisions, setDecisions] = useState<Record<string, DuplicateDecision>>({});
	const loadProgress = useCallback(() => workforceApi.builderProgress(conversationId!), [conversationId]);
	const { progress, progressError } = useEvaluationProgress(conversationId, loadProgress, working);

	const loadAgents = useCallback(async () => {
		setAgents(await workforceApi.listAgents());
	}, []);
	const loadConversations = useCallback(async () => {
		const items = await workforceApi.listBuilderConversations();
		setConversations(items);
		return items;
	}, []);
	const openConversation = useCallback(
		async (nextId: string) => {
			const stored = await workforceApi.getBuilderConversation(nextId);
			setConversationId(nextId);
			setConversation(stored.messages);
			setProposal(stored.proposal);
			setDecisions({});
			setContextInfo({ messages: stored.context_messages ?? stored.messages.length, summarized: stored.context_summarized ?? false });
			if (stored.proposal) setSelectedModel(stored.proposal.chat_model_config);
			setSearchParams({ conversation_id: nextId }, { replace: true });
		},
		[setSearchParams],
	);

	useEffect(() => {
		void loadAgents();
	}, [loadAgents]);

	useEffect(() => {
		void loadConversations().then((items) => {
			const requested = searchParams.get('conversation_id');
			const initial = requested ?? items[0]?.conversation_id;
			if (initial) void openConversation(initial);
		});
		// The first load owns restoration; later navigation uses openConversation.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const newConversation = () => {
		setConversationId(null);
		setConversation([]);
		setProposal(null);
		setMessage('');
		setLastLatency(null);
		setContextInfo({ messages: 0, summarized: false });
		setSearchParams({}, { replace: true });
	};

	const refreshConversation = async (nextId: string) => {
		await openConversation(nextId);
		await loadConversations();
	};

	const prepare = async (confirmOutline = false) => {
		if (!message.trim() || !selectedModel) return;
		const userText = message.trim();
		setConversation((current) => [...current, { role: 'user', text: userText }]);
		setMessage('');
		setWorking(true);
		const startedAt = Date.now();
		setTask({ label: 'Builder đang xử lý yêu cầu…', startedAt });
		try {
			const nextProposal = await workforceApi.prepare(
				userText,
				selectedModel,
				conversationId,
				confirmOutline,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			setLastLatency(Date.now() - startedAt);
			setWorking(false);
		}
	};

	const confirmOutline = async () => {
		if (!selectedModel || !proposal?.planned_agents.length) return;
		const lastUserMessage = [...conversation]
			.reverse()
			.find((item) => item.role === 'user')?.text ?? '';
		setWorking(true);
		const startedAt = Date.now();
		setTask({ label: 'Đang sinh prompt, công cụ và ca kiểm thử…', startedAt });
		try {
			const nextProposal = await workforceApi.prepare(
				prefersVietnamese(lastUserMessage)
					? 'Tôi xác nhận hướng trên. Hãy tạo và đánh giá cấu hình agent.'
					: 'I confirm this direction. Please generate and evaluate the agent configuration.',
				selectedModel,
				conversationId,
				true,
				decisions,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			setLastLatency(Date.now() - startedAt);
			setWorking(false);
		}
	};
	const undecided = (proposal?.planned_agents ?? []).filter((agent) => agent.similar && !decisions[agent.name]);

	const publish = async () => {
		if (!proposal?.proposal_id) return;
		setWorking(true);
		const startedAt = Date.now();
		setTask({ label: 'Đang lưu và phát hành agent…', startedAt });
		try {
			const result = await workforceApi.publish(
				proposal.conversation_id,
				proposal.proposal_id,
				proposal.revision,
			);
			setProposal({ ...proposal, status: 'published' });
			await refreshConversation(proposal.conversation_id);
			await loadAgents();
			const updated = result.agents.filter((agent) => agent.updated).length;
			const reused = result.agents.filter((agent) => agent.reused).length;
			const created = result.agents.length - updated - reused;
			toast.success(
				[created && `tạo mới ${created}`, updated && `cập nhật ${updated}`, reused && `dùng lại ${reused}`]
					.filter(Boolean)
					.join(', ')
					.replace(/^./, (first) => first.toUpperCase()) + ' agent.',
			);
		} finally {
			setLastLatency(Date.now() - startedAt);
			setWorking(false);
		}
	};
	const evaluate = async () => {
		if (!proposal?.proposal_id || working) return;
		setWorking(true);
		const startedAt = Date.now();
		setTask({ label: 'Đang chạy lại eval trên cấu hình hiện tại…', startedAt });
		try {
			await workforceApi.evaluate(proposal.conversation_id, proposal.proposal_id, proposal.revision);
			await refreshConversation(proposal.conversation_id);
		} catch { toast.error('Chưa chạy lại được eval. Kiểm tra kết nối và tải lại đề xuất.'); }
		finally { setLastLatency(Date.now() - startedAt); setWorking(false); }
	};
	const repair = async () => {
		if (!proposal?.proposal_id || working) return;
		setWorking(true);
		const startedAt = Date.now();
		setTask({ label: 'Builder đang đọc ca trượt, sửa prompt hoặc test rồi chạy lại eval…', startedAt });
		try {
			await workforceApi.repair(proposal.conversation_id, proposal.proposal_id, proposal.revision);
			await refreshConversation(proposal.conversation_id);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Chưa sửa được theo kết quả eval.');
		} finally {
			setLastLatency(Date.now() - startedAt);
			setWorking(false);
		}
	};
	const repairRounds = Math.max(0, ...(proposal?.agents ?? []).map((agent) => agent.evaluation.repair?.round ?? 0));
	const canRepair =
		proposal?.status === 'blocked' &&
		repairRounds < 2 &&
		(proposal.agents ?? []).some((agent) => !agent.reuse_agent_id && agent.evaluation.model_report && !agent.evaluation.passed);

	const toggleLifecycle = async (agent: WorkforceAgent) => {
		const next = agent.lifecycle_state === 'published' ? 'draft' : 'published';
		await workforceApi.setLifecycle(agent.agent_id, next);
		await loadAgents();
	};

	const current = conversations.find((item) => item.conversation_id === conversationId);
	const roster = <AgentRoster agents={agents} onToggle={(agent) => void toggleLifecycle(agent)} />;

	return (
		<>
		<div className="flex size-full min-h-0">
			<aside className="cue-column flex w-80 shrink-0 flex-col border-r border-sidebar-border bg-sidebar max-md:hidden">
				<header className="flex h-12 shrink-0 items-center justify-between gap-2 pr-2 pl-4">
					<h1 className="truncate text-[15px]/5 font-semibold">Agent Builder</h1>
					<Button
						variant="ghost"
						size="icon"
						aria-label="Hội thoại mới"
						title="Hội thoại mới"
						onClick={newConversation}
						disabled={working}
					>
						<Plus className="size-5" />
					</Button>
				</header>
				<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
					{conversations.length === 0 ? (
						<p className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							Chưa có hội thoại. Mô tả agent bạn cần ở khung bên phải.
						</p>
					) : (
						conversations.map((item, index) => (
							<ChatRow
								key={item.conversation_id}
								className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-1 motion-safe:fill-mode-both"
								style={{ animationDelay: `${Math.min(index, 10) * 30}ms` }}
								avatarId={BUILDER_ID}
								avatarLabel="Agent Builder"
								title={item.title}
								time={sessionTime(item.updated_at)}
								preview="Agent Builder"
								status={working && item.conversation_id === conversationId ? 'running' : 'idle'}
								active={item.conversation_id === conversationId}
								disabled={working}
								onSelect={() => void openConversation(item.conversation_id)}
								actions={
									<Button
										variant="ghost"
										size="icon-sm"
										aria-label={`Xoá hội thoại ${item.title}`}
										title="Xoá hội thoại"
										className="text-muted-foreground"
										onClick={() => setDeleting(item)}
									>
										<Trash2 />
									</Button>
								}
							/>
						))
					)}
				</div>
			</aside>

			<main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<header className="flex h-12 shrink-0 items-center gap-2 px-4">
					<Button
						variant="ghost"
						size="icon-sm"
						className="md:hidden"
						aria-label="Hội thoại mới"
						onClick={newConversation}
						disabled={working}
					>
						<Plus />
					</Button>
					<ClayAvatar id={BUILDER_ID} label="Agent Builder" size={28} working={working} />
					<h2 className="min-w-0 flex-1 truncate text-[15px]/5 font-semibold">
						{current?.title ?? 'Hội thoại mới'}
					</h2>
					<LlmSelect
						value={selectedModel}
						onChange={setSelectedModel}
						onAddCredential={() => setCredentialOpen(true)}
						refetchTrigger={credentialRefetchTrigger}
						placeholder="Chọn model"
						variant="ghost"
						className="w-44 font-mono text-[13px] text-muted-foreground hover:text-foreground"
						disabled={working}
					/>
					<Button variant="ghost" size="sm" className="xl:hidden" onClick={() => setAgentsOpen(true)}>
						<Bot /> Agent
						<Badge variant="secondary" className="ml-0.5">{agents.length}</Badge>
					</Button>
				</header>

				<div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-6">
					<div className="mx-auto flex max-w-3xl flex-col gap-5">
						{conversation.length === 0 && !proposal && (
							<BuilderWelcome onPick={(text) => setMessage(text)} />
						)}
						{conversation.map((item, index) =>
							item.role === 'user' ? (
								<div
									key={`user:${index}`}
									className="ml-auto w-fit max-w-[84%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-[var(--cue-bg-subtle,var(--muted))] px-3.5 py-2 text-[15px]/6 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1"
								>
									{item.text}
								</div>
							) : (
								<div
									key={`builder:${index}`}
									className="flex gap-3 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1"
								>
									<ClayAvatar id={BUILDER_ID} label="Agent Builder" size={32} />
									<div className="min-w-0 flex-1">
										<p className="mb-0.5 text-[13px]/[18px] font-medium text-muted-foreground">Agent Builder</p>
										<Markdown className="text-[15px]/6">{item.text}</Markdown>
									</div>
								</div>
							),
						)}
						{working && (
							<TaskProgress key={task.startedAt} {...task} />
						)}
						{progress && <EvaluationProgress progress={progress} />}
						{progressError && <p role="status" className="text-xs text-muted-foreground">Chưa tải được tiến độ. Kết quả vẫn được lưu trên server; không tự chạy lại model.</p>}
						{conversation.length > 0 && (
							<p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" data-testid="builder-metrics">
								<span>Ngữ cảnh: {contextInfo.messages} tin nhắn{contextInfo.summarized ? ' · đã tóm tắt lịch sử dài' : ''}</span>
								{lastLatency !== null && <span>Thời gian phản hồi: {(lastLatency / 1000).toFixed(1)} giây</span>}
							</p>
						)}

						{proposal && (
							<section className="flex flex-col gap-4 rounded-3xl border border-border/70 bg-[var(--cue-bg-subtle,var(--muted))]/40 p-4 motion-safe:animate-in motion-safe:fade-in">
								<ProposalSteps status={proposal.status} />
								<div className="flex flex-wrap items-start justify-between gap-3">
									<div className="min-w-0 flex-1">
										<h2 className="text-[15px]/6 font-medium">{proposal.agents.length ? 'Cấu hình chờ duyệt' : 'Dàn ý hiện tại'} · {proposal.agents.length || proposal.planned_agents.length} agent</h2>
										<p className="mt-1 text-xs text-muted-foreground">
											Model <span className="font-mono">{proposal.chat_model_config.model}</span>
										</p>
									</div>
									{proposal.status === 'ready' && (
										<Button onClick={publish} disabled={working}>
											<Rocket /> Phát hành
										</Button>
									)}
									{proposal.status === 'needs_input' && proposal.planned_agents.length > 0 && (
										<Button
											onClick={() => void confirmOutline()}
											disabled={working || undecided.length > 0}
											title={undecided.length ? 'Chọn cách xử lý agent trùng nghiệp vụ trước' : undefined}
										>
											<CheckCircle2 /> Chốt và sinh cấu hình
										</Button>
									)}
									{canRepair && (
										<Button onClick={() => void repair()} disabled={working}>
											<Wand2 /> Để Builder sửa theo kết quả eval
										</Button>
									)}
									{proposal.agents.length > 0 && proposal.status !== 'published' && <Button variant="outline" onClick={() => void evaluate()} disabled={working}>Chạy lại eval · giữ cấu hình</Button>}
								</div>
								{proposal.planned_agents.length > 0 && proposal.agents.length === 0 && (
									<div className="grid gap-3 md:grid-cols-2">
										{proposal.planned_agents.map((agent, index) => (
											<PlannedAgentCard
												key={agent.name}
												agent={agent}
												index={index}
												decision={decisions[agent.name]}
												disabled={working || proposal.status !== 'needs_input'}
												onDecide={(choice) => setDecisions((current) => ({ ...current, [agent.name]: choice }))}
											/>
										))}
									</div>
								)}
								{undecided.length > 0 && proposal.status === 'needs_input' && (
									<p role="status" className="text-xs text-amber-700 dark:text-amber-400">
										{undecided.length} agent trùng nghiệp vụ với agent đang có. Chọn cập nhật, dùng lại hoặc vẫn tạo mới để tiếp tục.
									</p>
								)}
								{proposal.agents.map((agent, index) => (
									<div
										key={`${agent.name}:${agent.skill_name}`}
										className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:fill-mode-both"
										style={{ animationDelay: `${index * 60}ms` }}
									>
										<AgentProposalCard proposal={agent} />
									</div>
								))}
							</section>
						)}
					</div>
				</div>

				<div className="shrink-0 px-4 pb-4">
					<div className="mx-auto max-w-3xl rounded-[24px] border border-[var(--cue-border,var(--border))] bg-background p-1.5 shadow-[var(--cue-shadow-composer,none)] focus-within:border-ring/60">
						<Textarea
							value={message}
							onChange={(event) => setMessage(event.target.value)}
							onKeyDown={(event) => {
								if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
									event.preventDefault();
									void prepare();
								}
							}}
							placeholder="Mô tả agent hoặc đội agent bạn cần…"
							className="min-h-12 resize-none border-none bg-transparent px-3 text-[15px] shadow-none focus-visible:ring-0"
							disabled={working}
						/>
						<div className="flex items-center justify-between gap-2 pr-1 pl-3">
							<p className="text-xs text-amber-700 dark:text-amber-400">
								{!selectedModel && 'Hãy chọn model trước khi gửi.'}
							</p>
							<Button
								size="icon"
								aria-label="Gửi cho Builder"
								title="Gửi cho Builder"
								className="rounded-full"
								onClick={() => void prepare()}
								disabled={working || !message.trim() || !selectedModel}
							>
								{working ? <Spinner /> : <ArrowUp />}
							</Button>
						</div>
					</div>
				</div>
			</main>

			<aside className="hidden w-80 shrink-0 flex-col border-l border-sidebar-border bg-sidebar xl:flex">
				{roster}
			</aside>
		</div>

		<Sheet open={agentsOpen} onOpenChange={setAgentsOpen}>
			<SheetContent className="w-[340px] gap-0 p-0 sm:max-w-[340px]">
				<SheetHeader className="sr-only">
					<SheetTitle>Agent trong platform</SheetTitle>
					<SheetDescription>Leader chỉ mời agent đang phát hành.</SheetDescription>
				</SheetHeader>
				{roster}
			</SheetContent>
		</Sheet>
		<DeleteDialog
			open={deleting !== null}
			onOpenChange={(open) => !open && setDeleting(null)}
			title={`Xoá hội thoại "${deleting?.title ?? ''}"?`}
			description="Hội thoại và đề xuất của nó bị xoá. Agent đã phát hành từ hội thoại này vẫn giữ nguyên."
			confirmLabel="Xoá hội thoại"
			onConfirm={async () => {
				if (!deleting) return;
				await workforceApi.deleteBuilderConversation(deleting.conversation_id);
				if (deleting.conversation_id === conversationId) newConversation();
				await loadConversations();
			}}
		/>
		<CreateCredentialDialog
			open={credentialOpen}
			onOpenChange={setCredentialOpen}
			onCreated={() => setCredentialRefetchTrigger((value) => value + 1)}
		/>
		</>
	);
}

const DECISIONS: { value: DuplicateDecision; label: string; hint: string }[] = [
	{ value: 'update', label: 'Cập nhật agent đó', hint: 'Builder viết phiên bản mới cho agent đang có' },
	{ value: 'reuse', label: 'Dùng lại nguyên vẹn', hint: 'Không sinh agent mới, giữ agent đang có' },
	{ value: 'create', label: 'Vẫn tạo mới', hint: 'Tạo agent riêng bên cạnh agent đang có' },
];

/** One agent of the outline; when it duplicates an existing agent, the manager says what to do. */
function PlannedAgentCard({
	agent,
	index,
	decision,
	disabled,
	onDecide,
}: {
	agent: PlannedAgent;
	index: number;
	decision?: DuplicateDecision;
	disabled: boolean;
	onDecide: (decision: DuplicateDecision) => void;
}) {
	return (
		<article
			className={cn(
				'flex flex-col gap-3 rounded-2xl border bg-background p-3.5 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:fill-mode-both',
				agent.similar && !decision ? 'border-amber-400/70' : 'border-border/70',
			)}
			style={{ animationDelay: `${index * 60}ms` }}
		>
			<div className="flex gap-3">
				<ClayAvatar id={agent.name} label={agent.name} size={40} />
				<div className="min-w-0 flex-1">
					<p className="text-sm font-semibold">{agent.name}</p>
					<p className="mt-1 line-clamp-3 text-[13px]/[18px] text-muted-foreground">{agent.objective}</p>
					{agent.suggested_tools.length > 0 && (
						<div className="mt-2 flex flex-wrap gap-1">
							{agent.suggested_tools.map((tool) => (
								<span key={tool.id} className="rounded-full bg-muted px-2 py-0.5 font-mono text-[11px]">
									{tool.tool_name}
								</span>
							))}
						</div>
					)}
				</div>
			</div>
			{agent.similar && (
				<div className="rounded-xl bg-amber-50 p-2.5 text-[13px]/[18px] dark:bg-amber-950/30">
					<p className="flex items-start gap-1.5 text-amber-800 dark:text-amber-300">
						<CircleAlert className="mt-0.5 size-3.5 shrink-0" />
						<span>
							Giống <strong>{agent.similar.name}</strong> ({Math.round(agent.similar.score * 100)}%,{' '}
							{agent.similar.published ? 'đang phát hành' : 'bản nháp'}).
						</span>
					</p>
					<div role="radiogroup" aria-label={`Xử lý ${agent.name}`} className="mt-2 grid gap-1.5">
						{DECISIONS.filter((option) => option.value !== 'reuse' || agent.similar?.published).map((option) => (
							<button
								key={option.value}
								type="button"
								role="radio"
								aria-checked={decision === option.value}
								disabled={disabled}
								onClick={() => onDecide(option.value)}
								className={cn(
									'flex items-start gap-2 rounded-lg border px-2.5 py-1.5 text-left transition-colors',
									decision === option.value
										? 'border-foreground bg-foreground text-background'
										: 'border-border/70 bg-background hover:bg-muted',
								)}
							>
								<span className="font-medium">{option.label}</span>
								<span className={cn('text-xs', decision === option.value ? 'text-background/80' : 'text-muted-foreground')}>
									{option.hint}
								</span>
							</button>
						))}
					</div>
				</div>
			)}
		</article>
	);
}

/** The Builder's own mark, so its portrait is the same on every screen. */
const BUILDER_ID = 'agent-builder';

/** Roles the Builder can staff, shown as the team it is about to build. */
const WELCOME_TEAM: { which: PortraitKey; label: string }[] = [
	{ which: 'reception', label: 'Lễ tân' },
	{ which: 'leader', label: 'Điều phối' },
	{ which: 'technician', label: 'Kỹ thuật' },
	{ which: 'planner', label: 'Kế hoạch' },
	{ which: 'calculator', label: 'Tính toán' },
];

const WELCOME_PROMPTS = [
	'Tạo đội agent xử lý ticket sự cố kỹ thuật của cư dân: đánh giá, giao thợ, báo cư dân.',
	'Tạo agent tư vấn cư dân về nội quy và bàn giao căn hộ, trả lời từ kho tri thức của BQL.',
	'Tạo agent báo cáo tình trạng ticket hằng ngày cho Ban quản lý.',
];

/** An empty conversation: the team to build, and a few ways to start. */
function BuilderWelcome({ onPick }: { onPick: (text: string) => void }) {
	return (
		<div className="flex flex-col items-center pt-8 pb-2 text-center">
			<div className="flex items-end -space-x-3">
				{WELCOME_TEAM.map((member, index) => (
					<div
						key={member.which}
						className="flex flex-col items-center gap-1.5 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3 motion-safe:fill-mode-both"
						style={{ animationDelay: `${index * 80}ms`, zIndex: index === 2 ? 1 : 0 }}
					>
						<ClayPortrait
							which={member.which}
							size={index === 2 ? 84 : 68}
							className="rounded-full border-4 border-background shadow-[0_8px_24px_rgba(0,0,0,0.08)]"
						/>
						<span className="text-[11px] text-muted-foreground">{member.label}</span>
					</div>
				))}
			</div>
			<h3 className="mt-5 text-xl font-semibold tracking-tight">Bạn cần đội agent làm gì?</h3>
			<p className="mt-1.5 max-w-md text-sm text-muted-foreground">
				Builder viết prompt, chọn tool từ MCP, gắn kho tri thức, dùng lại skill có sẵn và chấm eval trước khi bạn
				phát hành.
			</p>
			<div className="mt-5 flex w-full max-w-xl flex-col gap-2">
				{WELCOME_PROMPTS.map((prompt, index) => (
					<button
						key={prompt}
						type="button"
						onClick={() => onPick(prompt)}
						className="group flex items-center gap-3 rounded-2xl border border-border/70 bg-background px-3.5 py-2.5 text-left text-sm transition-[background-color,transform] hover:-translate-y-px hover:bg-[var(--cue-bg-hover,var(--accent))] active:translate-y-0 motion-safe:animate-in motion-safe:fade-in motion-safe:fill-mode-both"
						style={{ animationDelay: `${300 + index * 60}ms` }}
					>
						<Sparkles className="size-4 shrink-0 text-muted-foreground group-hover:text-foreground" />
						<span className="min-w-0 flex-1">{prompt}</span>
					</button>
				))}
			</div>
		</div>
	);
}

const STEPS = [
	{ key: 'outline', label: 'Định hướng' },
	{ key: 'config', label: 'Kiểm tra cấu hình' },
	{ key: 'publish', label: 'Phát hành' },
] as const;

/** Where the proposal stands: outline, configured and evaluated, published. */
function ProposalSteps({ status }: { status: BuilderProposal['status'] }) {
	const reached = status === 'published' ? 3 : status === 'ready' || status === 'blocked' ? 2 : 1;
	return (
		<ol className="flex items-center gap-2 text-xs">
			{STEPS.map((step, index) => {
				const done = index < reached;
				const blocked = status === 'blocked' && index === 1;
				return (
					<li key={step.key} className="flex items-center gap-2">
						{index > 0 && <span className={cn('h-px w-6', done ? 'bg-foreground/40' : 'bg-border')} />}
						<span
							className={cn(
								'flex items-center gap-1.5 rounded-full px-2.5 py-1',
								blocked
									? 'bg-destructive/10 text-destructive'
									: done
										? 'bg-foreground text-background'
										: 'bg-muted text-muted-foreground',
							)}
						>
							{blocked ? <CircleAlert className="size-3" /> : done ? <Check className="size-3" /> : null}
							{blocked ? 'Eval chưa đạt' : step.label}
						</span>
					</li>
				);
			})}
		</ol>
	);
}

/** The platform's business agents as portrait cards; the switch publishes one. */
function AgentRoster({ agents, onToggle }: { agents: WorkforceAgent[]; onToggle: (agent: WorkforceAgent) => void }) {
	const published = agents.filter((agent) => agent.lifecycle_state === 'published').length;
	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<header className="shrink-0 px-4 pt-3 pb-2">
				<div className="flex items-center justify-between">
					<h2 className="text-[15px]/5 font-semibold">Agent trong platform</h2>
					<span className="text-xs tabular-nums text-muted-foreground">
						{published}/{agents.length} phát hành
					</span>
				</div>
				<p className="mt-0.5 text-xs text-muted-foreground">Leader chỉ mời agent đang phát hành.</p>
			</header>
			<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-3">
				{agents.length === 0 ? (
					<div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
						<img src={robotStill} alt="" className="size-14 opacity-80" />
						<p className="text-sm text-muted-foreground">Chưa có agent nào. Agent Builder phát hành sẽ hiện ở đây.</p>
					</div>
				) : (
					<ul className="flex flex-col gap-1">
						{agents.map((agent, index) => {
							const live = agent.lifecycle_state === 'published';
							return (
								<li
									key={agent.agent_id}
									className="group flex items-center gap-3 rounded-2xl px-2 py-2 transition-colors hover:bg-[var(--cue-bg-hover,var(--accent))] motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-right-1 motion-safe:fill-mode-both"
									style={{ animationDelay: `${Math.min(index, 12) * 35}ms` }}
								>
									<ClayAvatar id={agent.agent_id} label={agent.name} size={40} className={cn(!live && 'opacity-60 grayscale')} />
									<div className="min-w-0 flex-1">
										<p className="truncate text-sm font-medium">{agent.name}</p>
										<p className="truncate text-xs text-muted-foreground">
											{agent.tool_count} tool · {live ? 'đang phát hành' : 'bản nháp'}
										</p>
									</div>
									<Switch
										checked={live}
										onCheckedChange={() => onToggle(agent)}
										aria-label={live ? `Ngừng phát hành ${agent.name}` : `Phát hành ${agent.name}`}
									/>
								</li>
							);
						})}
					</ul>
				)}
			</div>
		</div>
	);
}
