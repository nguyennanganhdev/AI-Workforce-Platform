import {
	ArrowUp,
	Bot,
	Check,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	Database,
	Plus,
	Recycle,
	Rocket,
	Sparkles,
	Trash2,
	Wrench,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { agentApi, workforceApi } from '@/api';
import type {
	BuilderConversationSummary,
	BuilderMessage,
	BuilderProposal,
	ChatModelConfig,
	WorkforceAgent,
	KnowledgeBaseView,
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
import { Checkbox } from '@/components/ui/checkbox';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { ClayPortrait, type PortraitKey } from '@/components/ui/clay-portrait';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Progress } from '@/components/ui/progress';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { TaskProgress } from '@/components/ui/task-progress';
import { Textarea } from '@/components/ui/textarea';
import { useKnowledgeBases } from '@/hooks/useKnowledgeBases';
import { cn } from '@/lib/utils';

function prefersVietnamese(text: string) {
	const normalized = text.toLocaleLowerCase('vi-VN');
	return (
		/[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/i.test(normalized) ||
		['tôi', 'bạn', 'hãy', 'muốn', 'không'].filter((word) => normalized.includes(word)).length >=
			2
	);
}

function AgentProposalCard({
	proposal,
	resourcesLocked,
	knowledgeBases,
	knowledgeBasesLoading,
	onKnowledgeBaseIdsChange,
}: {
	proposal: BuilderProposal['agents'][number];
	resourcesLocked: boolean;
	knowledgeBases: KnowledgeBaseView[];
	knowledgeBasesLoading: boolean;
	onKnowledgeBaseIdsChange: (ids: string[]) => void;
}) {
	const passed = proposal.evaluation.passed === true;
	const reused = proposal.reuse_agent_id !== null;
	const selectedKnowledgeIds = new Set(
		proposal.selected_knowledge_bases.map((knowledge) => knowledge.id),
	);

	return (
		<article className="rounded-2xl border border-border/70 bg-background p-4">
			<header className="flex items-start gap-3">
				<ClayAvatar id={proposal.reuse_agent_id ?? proposal.name} label={proposal.name} size={40} />
				<div className="min-w-0 flex-1">
					<div className="flex flex-wrap items-center gap-2">
						<h3 className="text-[15px]/5 font-semibold">{proposal.name}</h3>
						<Badge variant="secondary">
							{proposal.execution_mode === 'context_only' ? 'Ngữ cảnh / KB' : 'Có MCP'}
						</Badge>
						<Badge variant={passed ? 'secondary' : 'destructive'}>
							{passed ? <CheckCircle2 /> : <CircleAlert />}
							{passed ? 'Cấu hình đạt' : 'Cấu hình chưa đạt'}
						</Badge>
					</div>
					<p className="mt-1 text-sm text-muted-foreground">{proposal.objective}</p>
				</div>
			</header>
			<Progress value={(proposal.evaluation.score ?? 0) * 100} className="mt-3 h-1.5" />

			<div className="mt-3 flex flex-wrap gap-1.5 text-xs">
				{proposal.selected_tools.map((tool) => (
					<span
						key={tool.id}
						title={tool.description ?? undefined}
						className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 font-mono"
					>
						<Wrench className="size-3" /> {tool.mcp_name} / {tool.tool_name}
					</span>
				))}
				{proposal.selected_tools.length === 0 && (
					<span className="text-muted-foreground">
						{proposal.execution_mode === 'context_only'
							? 'Agent dùng input, Knowledge Base hoặc kết quả từ agent khác; không cần MCP riêng.'
							: 'Chưa có tool phù hợp trong MCP đã đăng ký.'}
					</span>
				)}
			</div>

			{reused && (
				<p className="mt-3 flex items-start gap-2 rounded-xl bg-sky-50 p-2.5 text-sm text-sky-800 dark:bg-sky-950/30 dark:text-sky-300">
					<Recycle className="mt-0.5 size-4 shrink-0" />
					<span>
						Nghiệp vụ trùng với <strong>{proposal.reuse_agent_name}</strong>. Khi phát hành,
						platform sẽ tái sử dụng agent cũ thay vì tạo bản sao.
					</span>
				</p>
			)}

			<section className="mt-4">
				<p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
					<Database className="size-3.5" /> Knowledge Base
				</p>
				{resourcesLocked && (
					<p className="mb-2 text-xs text-muted-foreground">
						KB đã chốt theo plan. Muốn thay đổi, hãy nhắn yêu cầu để lập và duyệt lại plan.
					</p>
				)}
				{knowledgeBasesLoading ? (
					<div className="flex items-center gap-2 rounded-xl bg-muted/50 p-3 text-xs text-muted-foreground">
						<Spinner /> Đang tải Knowledge Base…
					</div>
				) : knowledgeBases.length ? (
					<div className="max-h-56 space-y-0.5 overflow-y-auto rounded-xl bg-muted/40 p-1.5">
						{knowledgeBases.map((knowledge) => (
							<label
								key={knowledge.id}
								className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 hover:bg-[var(--cue-bg-hover,var(--accent))]"
							>
								<Checkbox
									disabled={resourcesLocked}
									checked={selectedKnowledgeIds.has(knowledge.id)}
									onCheckedChange={(checked) => {
										const next = new Set(selectedKnowledgeIds);
										if (checked === true) next.add(knowledge.id);
										else next.delete(knowledge.id);
										onKnowledgeBaseIdsChange([...next]);
									}}
									className="mt-0.5"
								/>
								<span className="min-w-0">
									<span className="block text-xs font-medium">{knowledge.name}</span>
									{knowledge.description && (
										<span className="mt-0.5 block text-xs text-muted-foreground">
											{knowledge.description}
										</span>
									)}
								</span>
							</label>
						))}
					</div>
				) : (
					<p className="rounded-xl bg-muted/40 p-3 text-xs text-muted-foreground">
						Chưa có Knowledge Base. Hãy tạo KB và mô tả rõ phạm vi sử dụng trước khi publish.
					</p>
				)}
			</section>

			<Collapsible className="mt-3">
				<CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
					{reused ? 'System prompt của agent có sẵn' : 'System prompt do Builder sinh'} và skill{' '}
					{proposal.skill_name}
					<ChevronRight className="size-3 transition-transform group-data-[state=open]:rotate-90" />
				</CollapsibleTrigger>
				<CollapsibleContent className="mt-2 space-y-2">
					<pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-xs leading-5">
						{proposal.system_prompt}
					</pre>
					<pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">
						{proposal.skill_markdown}
					</pre>
				</CollapsibleContent>
			</Collapsible>
		</article>
	);
}

export function AgentBuilderPage() {
	const navigate = useNavigate();
	const { knowledgeBases, loading: knowledgeBasesLoading } = useKnowledgeBases();
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
	const [selectedModel, setSelectedModel] = useState<ChatModelConfig | null>(null);
	const [credentialOpen, setCredentialOpen] = useState(false);
	const [credentialRefetchTrigger, setCredentialRefetchTrigger] = useState(0);
	const [deleteConversationOpen, setDeleteConversationOpen] = useState(false);
	const [conversationToDelete, setConversationToDelete] =
		useState<BuilderConversationSummary | null>(null);
	const [agentToDelete, setAgentToDelete] = useState<WorkforceAgent | null>(null);
	const [agentsOpen, setAgentsOpen] = useState(false);
	// Display only: when the current Builder call started, for the elapsed-time line.
	const [workStartedAt, setWorkStartedAt] = useState(0);
	useEffect(() => {
		setWorkStartedAt(working ? Date.now() : 0);
	}, [working]);

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
			const model = stored.chat_model_config ?? stored.proposal?.chat_model_config;
			if (model) setSelectedModel(model);
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
		setSearchParams({}, { replace: true });
	};

	const deleteConversation = async (item: BuilderConversationSummary) => {
		await workforceApi.deleteBuilderConversation(item.conversation_id);
		const remaining = await loadConversations();
		if (item.conversation_id !== conversationId) return;
		if (remaining.length > 0) await openConversation(remaining[0].conversation_id);
		else newConversation();
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
		try {
			const nextProposal = await workforceApi.prepare(
				userText,
				selectedModel,
				conversationId,
				confirmOutline,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			setWorking(false);
		}
	};

	const confirmOutline = async () => {
		if (!selectedModel || !proposal?.planned_agents.length) return;
		const lastUserMessage =
			[...conversation].reverse().find((item) => item.role === 'user')?.text ?? '';
		setWorking(true);
		try {
			const nextProposal = await workforceApi.prepare(
				prefersVietnamese(lastUserMessage)
					? 'Tôi xác nhận hướng trên. Hãy tạo và đánh giá cấu hình agent.'
					: 'I confirm this direction. Please generate and evaluate the agent configuration.',
				selectedModel,
				conversationId,
				true,
				proposal.revision,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			setWorking(false);
		}
	};

	const publish = async () => {
		if (!proposal?.proposal_id) return;
		setWorking(true);
		try {
			const result = await workforceApi.publish(
				proposal.conversation_id,
				proposal.proposal_id,
				proposal.revision,
				proposal.agents.map((agent) =>
					agent.selected_knowledge_bases.map((knowledge) => knowledge.id),
				),
			);
			setProposal({ ...proposal, status: 'published' });
			await refreshConversation(proposal.conversation_id);
			await loadAgents();
			toast.success(`Đã sẵn sàng ${result.agents.length} agent trong platform.`);
		} finally {
			setWorking(false);
		}
	};

	const toggleLifecycle = async (agent: WorkforceAgent) => {
		const next = agent.lifecycle_state === 'published' ? 'draft' : 'published';
		await workforceApi.setLifecycle(agent.agent_id, next);
		await loadAgents();
	};

	const current = conversations.find((item) => item.conversation_id === conversationId);
	// Built inline (no hooks inside) so the delete buttons stay part of this page's tree.
	const roster = agentRoster({
		agents,
		onOpenManagement: () => navigate('/workforce/agents'),
		onToggle: (agent) => void toggleLifecycle(agent),
		onDelete: setAgentToDelete,
	});

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
								Chưa có hội thoại
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
									compact
									status={working && item.conversation_id === conversationId ? 'running' : 'idle'}
									active={item.conversation_id === conversationId}
									disabled={working}
									onSelect={() => void openConversation(item.conversation_id)}
									actions={
										<Button
											variant="ghost"
											size="icon-sm"
											aria-label={`Xóa hội thoại ${item.title}`}
											title="Xóa hội thoại"
											className="text-muted-foreground"
											onClick={() => {
												setConversationToDelete(item);
												setDeleteConversationOpen(true);
											}}
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
						<h2 className="min-w-0 flex-1 truncate text-[15px]/5 font-semibold max-md:hidden">
							{current?.title ?? 'Hội thoại mới'}
						</h2>
						{/* The conversation list is hidden on small screens; pick one here instead. */}
						<select
							aria-label="Hội thoại Builder"
							className="min-w-0 flex-1 truncate rounded-lg border bg-background p-1.5 text-sm md:hidden"
							value={conversationId ?? ''}
							disabled={working}
							onChange={(event) =>
								event.target.value
									? void openConversation(event.target.value)
									: newConversation()
							}
						>
							<option value="">Hội thoại mới</option>
							{conversations.map((item) => (
								<option key={item.conversation_id} value={item.conversation_id}>
									{item.title}
								</option>
							))}
						</select>
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
							<Badge variant="secondary" className="ml-0.5">
								{agents.length}
							</Badge>
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
											<p className="mb-0.5 text-[13px]/[18px] font-medium text-muted-foreground">
												Agent Builder
											</p>
											<Markdown className="text-[15px]/6">{item.text}</Markdown>
										</div>
									</div>
								),
							)}
							{working && workStartedAt > 0 && (
								<TaskProgress key={workStartedAt} label="Builder đang xử lý…" startedAt={workStartedAt} />
							)}

							{proposal && (
								<section className="flex flex-col gap-4 rounded-3xl border border-border/70 bg-[var(--cue-bg-subtle,var(--muted))]/40 p-4 motion-safe:animate-in motion-safe:fade-in">
									<ProposalSteps status={proposal.status} />
									<div className="flex flex-wrap items-start justify-between gap-3">
										<div className="min-w-0 flex-1">
											<p className="text-[15px]/6 font-medium">{proposal.assistant_message}</p>
											{proposal.clarification_question && (
												<p className="mt-1 text-sm text-amber-700 dark:text-amber-400">
													{proposal.clarification_question}
												</p>
											)}
											<p className="mt-1 text-xs text-muted-foreground">
												Model <span className="font-mono">{proposal.chat_model_config.model}</span>
												{' · '}
												{proposal.fixed_config.runtime_note}
											</p>
											{proposal.resource_selection && (
												<p className="mt-1 text-xs text-muted-foreground">
													Chọn tool/KB:{' '}
													{proposal.resource_selection === 'jev'
														? 'Jev'
														: proposal.resource_selection === 'hybrid'
															? 'Jev + LLM'
															: 'LLM (fallback)'}
												</p>
											)}
										</div>
										{proposal.status === 'ready' && (
											<Button onClick={publish} disabled={working}>
												<Rocket /> Phát hành
											</Button>
										)}
										{proposal.status === 'needs_input' && proposal.planned_agents.length > 0 && (
											<Button
												onClick={() => void confirmOutline()}
												disabled={working}
											>
												<CheckCircle2 />{' '}
												{proposal.planned_agents.every((agent) => agent.reuse_agent_id)
													? 'Chốt định hướng và dùng agent có sẵn'
													: 'Chốt định hướng và sinh cấu hình'}
											</Button>
										)}
										{proposal.status === 'published' && <Badge>Đã phát hành</Badge>}
										{proposal.status === 'blocked' && <Badge variant="destructive">Bị chặn</Badge>}
									</div>
									{proposal.planned_agents.length > 0 && (
										<div className="grid gap-3 md:grid-cols-2">
											{proposal.planned_agents.map((agent, index) => (
												<PlannedAgentCard key={agent.name} agent={agent} index={index} />
											))}
										</div>
									)}
									{proposal.agents.map((agent, agentIndex) => (
										<div
											key={`${agent.name}:${agent.skill_name}`}
											className="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:fill-mode-both"
											style={{ animationDelay: `${agentIndex * 60}ms` }}
										>
											<AgentProposalCard
												proposal={agent}
												resourcesLocked={proposal.resources_locked === true}
												knowledgeBases={knowledgeBases}
												knowledgeBasesLoading={knowledgeBasesLoading}
												onKnowledgeBaseIdsChange={(ids) =>
													setProposal((current) => {
														if (!current) return current;
														const selected = knowledgeBases
															.filter((knowledge) => ids.includes(knowledge.id))
															.map(({ id, name, description }) => ({
																id,
																name,
																description,
															}));
														return {
															...current,
															agents: current.agents.map((item, index) =>
																index === agentIndex
																	? {
																			...item,
																			selected_knowledge_bases: selected,
																		}
																	: item,
															),
														};
													})
												}
											/>
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
								placeholder="Nhắn cho Builder hoặc mô tả agent cần tạo…"
								className="min-h-12 resize-none border-none bg-transparent px-3 text-[15px] shadow-none focus-visible:ring-0"
								disabled={working}
							/>
							<div className="flex items-center justify-between gap-2 pr-1 pl-3">
								<p className="text-xs text-amber-700 dark:text-amber-400">
									{!selectedModel && 'Chọn model để bắt đầu'}
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
						<SheetTitle>Agent</SheetTitle>
						<SheetDescription>Phát hành để Leader sử dụng.</SheetDescription>
					</SheetHeader>
					{roster}
				</SheetContent>
			</Sheet>
			<DeleteDialog
				open={agentToDelete !== null}
				onOpenChange={(open) => {
					if (!open) setAgentToDelete(null);
				}}
				title={`Xóa agent “${agentToDelete?.name ?? ''}”?`}
				description="Agent cùng toàn bộ phiên chat, lịch sử và lịch chạy của agent sẽ bị xóa vĩnh viễn. Thao tác này không thể hoàn tác."
				confirmLabel="Xóa agent"
				onConfirm={async () => {
					if (!agentToDelete) return;
					await agentApi.delete(agentToDelete.agent_id);
					setAgents((current) =>
						current.filter((agent) => agent.agent_id !== agentToDelete.agent_id),
					);
					toast.success(`Đã xóa agent “${agentToDelete.name}”.`);
				}}
			/>
			<DeleteDialog
				open={deleteConversationOpen}
				onOpenChange={setDeleteConversationOpen}
				title={`Xóa hội thoại “${conversationToDelete?.title ?? ''}”?`}
				description="Toàn bộ lịch sử và proposal trong hội thoại này sẽ bị xóa."
				confirmLabel="Xóa hội thoại"
				onConfirm={async () => {
					if (conversationToDelete) await deleteConversation(conversationToDelete);
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

/** One agent of the outline: what it does, what it reuses, needs and gets from teammates. */
function PlannedAgentCard({
	agent,
	index,
}: {
	agent: BuilderProposal['planned_agents'][number];
	index: number;
}) {
	const missingKnowledge = agent.missing_resources?.filter((missing) =>
		missing.trim().toLowerCase().startsWith('knowledge:'),
	) ?? [];

	return (
		<article
			className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-background p-3.5 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:fill-mode-both"
			style={{ animationDelay: `${index * 60}ms` }}
		>
			<div className="flex gap-3">
				<ClayAvatar id={agent.reuse_agent_id ?? agent.name} label={agent.name} size={40} />
				<div className="min-w-0 flex-1">
					<div className="flex flex-wrap items-center gap-2">
						<p className="text-sm font-semibold">{agent.name}</p>
						<Badge variant={agent.reuse_agent_id ? 'default' : 'secondary'}>
							{agent.reuse_agent_id ? `Dùng lại: ${agent.reuse_agent_name}` : 'Tạo mới'}
						</Badge>
					</div>
					<p className="mt-1 text-[13px]/[18px] text-muted-foreground">{agent.objective}</p>
				</div>
			</div>
			{!!agent.peer_dependencies?.length && (
				<div className="rounded-xl bg-muted/50 p-2.5 text-[13px]/[18px] text-muted-foreground">
					<p className="font-medium text-foreground">Kết quả đã xác minh từ:</p>
					<ul className="mt-1 list-disc pl-4">
						{agent.peer_dependencies.map((dependency) => (
							<li key={dependency}>{dependency}</li>
						))}
					</ul>
				</div>
			)}
			{!!missingKnowledge.length && (
				<div className="rounded-xl bg-destructive/5 p-2.5 text-[13px]/[18px] text-destructive">
					<p className="flex items-center gap-1.5 font-medium">
						<CircleAlert className="size-3.5 shrink-0" /> Thiếu Knowledge Base:
					</p>
					<ul className="mt-1 list-disc pl-4">
						{missingKnowledge.map((missing) => (
							<li key={missing}>{missing}</li>
						))}
					</ul>
					<p className="mt-1 text-xs text-muted-foreground">Có thể thêm KB sau.</p>
				</div>
			)}
			{(agent.suggested_tools.length > 0 || agent.suggested_knowledge_bases.length > 0) && (
				<div className="flex flex-wrap gap-1">
					{agent.suggested_tools.map((tool) => (
						<span key={tool.id} className="rounded-full bg-muted px-2 py-0.5 font-mono text-[11px]">
							{tool.tool_name}
						</span>
					))}
					{agent.suggested_knowledge_bases.map((knowledge) => (
						<span
							key={knowledge.id}
							className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px]"
						>
							<Database className="size-3" /> {knowledge.name}
						</span>
					))}
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
	'Lên kế hoạch du lịch theo ngân sách: vé, khách sạn, ăn uống, tham quan.',
	'Tìm khách sạn còn phòng theo ngân sách.',
	'Trả lời khách hàng từ kho tri thức.',
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
			<h3 className="mt-5 text-xl font-semibold tracking-tight">Bạn muốn tạo agent gì?</h3>
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

/** Where the proposal stands: outline, configured and checked, published. */
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
							{blocked ? 'Bị chặn' : step.label}
						</span>
					</li>
				);
			})}
		</ol>
	);
}

/** The platform's business agents as portrait cards; the switch publishes one. */
function agentRoster({
	agents,
	onOpenManagement,
	onToggle,
	onDelete,
}: {
	agents: WorkforceAgent[];
	onOpenManagement: () => void;
	onToggle: (agent: WorkforceAgent) => void;
	onDelete: (agent: WorkforceAgent) => void;
}) {
	const published = agents.filter((agent) => agent.lifecycle_state === 'published').length;
	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<header className="shrink-0 px-4 pt-3 pb-2">
				<div className="flex items-center justify-between">
					<button type="button" className="text-[15px]/5 font-semibold hover:underline" onClick={onOpenManagement}>
						Agent
					</button>
					<span className="text-xs tabular-nums text-muted-foreground">
						{published}/{agents.length} phát hành
					</span>
				</div>
			</header>
			<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-3">
				{agents.length === 0 ? (
					<div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
						<img src={robotStill} alt="" className="size-14 opacity-80" />
						<p className="text-sm text-muted-foreground">Chưa có agent</p>
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
									<ClayAvatar
										id={agent.agent_id}
										label={agent.name}
										size={40}
										className={live ? undefined : 'opacity-60 grayscale'}
									/>
									<div className="min-w-0 flex-1">
										<p className="truncate text-sm font-medium">{agent.name}</p>
										<p className="truncate text-xs text-muted-foreground" title={agent.objective}>
											{agent.tool_count} tool · {agent.knowledge_base_count} KB ·{' '}
											{live ? 'Đang phát hành' : 'Bản nháp'}
										</p>
									</div>
									<Switch
										checked={live}
										onCheckedChange={() => onToggle(agent)}
										aria-label={live ? `Ngừng phát hành ${agent.name}` : `Phát hành ${agent.name}`}
									/>
									<Button
										size="icon-sm"
										variant="ghost"
										className="text-muted-foreground hover:text-destructive"
										aria-label={`Xóa agent ${agent.name}`}
										title="Xóa agent"
										onClick={() => onDelete(agent)}
									>
										<Trash2 />
									</Button>
								</li>
							);
						})}
					</ul>
				)}
			</div>
		</div>
	);
}
