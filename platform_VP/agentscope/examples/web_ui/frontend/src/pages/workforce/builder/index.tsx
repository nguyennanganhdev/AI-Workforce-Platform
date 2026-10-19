import { format, isToday } from 'date-fns';
import {
	Bot,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	Database,
	Ellipsis,
	PanelLeft,
	UsersRound,
	MessageSquare,
	MessageSquareDashed,
	Plus,
	Power,
	PowerOff,
	Send,
	Settings2,
	Trash2,
	Wrench,
	X,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { workforceApi } from '@/api';
import type {
	BuilderConversationSummary,
	BuilderMessage,
	BuilderProgress,
	BuilderProposal,
	ChatModelConfig,
	WorkforceAgent,
	KnowledgeBaseView,
} from '@/api';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditAgentDialog } from '@/components/dialog/EditAgentDialog';
import { Markdown } from '@/components/markdown';
import { LlmSelect } from '@/components/select/LlmSelect';
import { Badge } from '@/components/ui/badge';
import { Bubble, BubbleContent } from '@/components/ui/bubble';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Message, MessageAvatar, MessageContent } from '@/components/ui/message';
import { Progress } from '@/components/ui/progress';
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuAction,
	SidebarMenuBadge,
	SidebarMenuButton,
	SidebarMenuItem,
} from '@/components/ui/sidebar';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';
import { useAgents } from '@/hooks/useAgents';
import { useKnowledgeBases } from '@/hooks/useKnowledgeBases';

function prefersVietnamese(text: string) {
	const normalized = text.toLocaleLowerCase('vi-VN');
	return (
		/[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/i.test(normalized) ||
		['tôi', 'bạn', 'hãy', 'muốn', 'không'].filter((word) => normalized.includes(word)).length >=
			2
	);
}

function PlannedAgentCard({ agent }: { agent: BuilderProposal['planned_agents'][number] }) {
	return (
		<Card className="border-border/70 shadow-none">
			<CardHeader className="pb-3">
				<div className="flex items-start justify-between gap-3">
					<div className="min-w-0">
						<CardTitle className="flex flex-wrap items-center gap-2 text-base">
							<Bot className="size-4 shrink-0 text-primary" />
							{agent.name}
						</CardTitle>
						<p className="mt-2 text-sm leading-5 text-muted-foreground">
							{agent.objective}
						</p>
					</div>
					{agent.reuse_agent_name && (
						<Badge variant="destructive" className="shrink-0">
							Có thể tái sử dụng
						</Badge>
					)}
				</div>
			</CardHeader>
			<CardContent className="grid gap-4 pt-0 sm:grid-cols-2">
				<section>
					<div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<Wrench className="size-3.5" /> Tool đề xuất
					</div>
					{agent.suggested_tools.length > 0 ? (
						<div className="space-y-1.5">
							{agent.suggested_tools.map((tool) => (
								<div
									key={tool.id}
									className="w-fit max-w-full break-all rounded-md bg-secondary px-2 py-1 font-mono text-[10px] font-medium text-secondary-foreground"
									title={tool.description || tool.tool_name}
								>
									{tool.mcp_name} / {tool.tool_name}
								</div>
							))}
						</div>
					) : (
						<p className="text-xs text-muted-foreground">Không cần tool riêng.</p>
					)}
				</section>
				<section>
					<div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<Database className="size-3.5" /> Knowledge Base đề xuất
					</div>
					{agent.suggested_knowledge_bases.length > 0 ? (
						<div className="space-y-1.5">
							{agent.suggested_knowledge_bases.map((knowledge) => (
								<div
									key={knowledge.id}
									className="w-fit max-w-full break-words rounded-md border px-2 py-1 text-[10px] font-medium"
									title={knowledge.description || knowledge.name}
								>
									{knowledge.name}
								</div>
							))}
						</div>
					) : (
						<p className="text-xs text-muted-foreground">
							Không đề xuất Knowledge Base.
						</p>
					)}
				</section>
				{agent.reuse_agent_name && (
					<div className="flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-xs text-red-700 sm:col-span-2 dark:text-red-400">
						<CircleAlert className="mt-0.5 size-4 shrink-0" />
						<span>
							Có thể tái sử dụng agent đã phát hành{' '}
							<strong>{agent.reuse_agent_name}</strong>. Builder sẽ không tạo lại
							agent này khi sinh cấu hình.
						</span>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

function AgentProposalCard({
	proposal,
	knowledgeBases,
	knowledgeBasesLoading,
	onKnowledgeBaseIdsChange,
}: {
	proposal: BuilderProposal['agents'][number];
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
		<Card className="overflow-hidden border-border/70 shadow-none">
			<CardHeader className="border-b bg-muted/25 pb-4">
				<div className="flex flex-wrap items-start justify-between gap-3">
					<div>
						<CardTitle className="text-base">{proposal.name}</CardTitle>
						<p className="mt-1 max-w-2xl text-sm text-muted-foreground">
							{proposal.objective}
						</p>
					</div>
					<div className="flex flex-wrap gap-2">
						<Badge variant="secondary">
							{proposal.execution_mode === 'context_only'
								? 'Ngữ cảnh / KB'
								: 'Có MCP'}
						</Badge>
						<Badge variant={passed ? 'default' : 'destructive'}>
							{passed ? 'Eval đạt' : 'Eval chưa đạt'}
						</Badge>
					</div>
				</div>
				<Progress value={(proposal.evaluation.score ?? 0) * 100} className="mt-3 h-1.5" />
			</CardHeader>
			<CardContent className="grid gap-5 p-5 xl:grid-cols-2">
				<section className="xl:col-span-2">
					<div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
						<Bot className="size-3.5" /> System prompt do Builder sinh
					</div>
					<pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border bg-background p-3 text-xs leading-5">
						{proposal.system_prompt}
					</pre>
				</section>
				<section>
					<div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
						<Database className="size-3.5" /> Knowledge Base
					</div>
					{knowledgeBasesLoading ? (
						<div className="flex items-center gap-2 rounded-lg border p-3 text-xs text-muted-foreground">
							<Spinner /> Đang tải Knowledge Base…
						</div>
					) : knowledgeBases.length ? (
						<div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border p-2">
							{knowledgeBases.map((knowledge) => (
								<label
									key={knowledge.id}
									className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-muted/50"
								>
									<Checkbox
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
										<span className="block text-xs font-medium">
											{knowledge.name}
										</span>
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
						<p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
							Chưa có Knowledge Base. Hãy tạo KB và mô tả rõ phạm vi sử dụng trước khi
							publish.
						</p>
					)}
				</section>
				<section>
					<div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
						<Wrench className="size-3.5" /> Tool đã chọn
					</div>
					<div className="space-y-2">
						{proposal.selected_tools.map((tool) => (
							<div
								key={tool.id}
								className="rounded-lg border bg-background px-3 py-2"
							>
								<div className="font-mono text-xs font-medium">
									{tool.mcp_name} / {tool.tool_name}
								</div>
								{tool.description && (
									<p className="mt-1 text-xs text-muted-foreground">
										{tool.description}
									</p>
								)}
							</div>
						))}
						{proposal.selected_tools.length === 0 && (
							<p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
								{proposal.execution_mode === 'context_only'
									? 'Agent dùng input, Knowledge Base hoặc kết quả từ agent khác; không cần MCP riêng.'
									: 'Chưa có tool phù hợp trong MCP đã đăng ký.'}
							</p>
						)}
					</div>
				</section>
				<details className="xl:col-span-2 rounded-lg border bg-background p-3">
					<summary className="cursor-pointer text-sm font-medium">
						Skill: {proposal.skill_name}
					</summary>
					<pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-muted-foreground">
						{proposal.skill_markdown}
					</pre>
				</details>
				{reused && (
					<div className="xl:col-span-2 flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-400">
						<CircleAlert className="mt-0.5 size-4 shrink-0" />
						<span>
							Đã tái sử dụng <strong>{proposal.reuse_agent_name}</strong>; Builder
							không sinh lại cấu hình cho agent này.
						</span>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

export function AgentBuilderPage() {
	const { knowledgeBases, loading: knowledgeBasesLoading } = useKnowledgeBases();
	const { agents: agentViews, refetch: refetchAgentViews, remove: removeAgent } = useAgents();
	const [searchParams, setSearchParams] = useSearchParams();
	const [message, setMessage] = useState('');
	const [historyOpen, setHistoryOpen] = useState(false);
	const [rosterOpen, setRosterOpen] = useState(false);
	const [conversationId, setConversationId] = useState<string | null>(() =>
		searchParams.get('conversation_id'),
	);
	const [conversation, setConversation] = useState<BuilderMessage[]>([]);
	const [conversations, setConversations] = useState<BuilderConversationSummary[]>([]);
	const [proposal, setProposal] = useState<BuilderProposal | null>(null);
	const [agents, setAgents] = useState<WorkforceAgent[]>([]);
	const [working, setWorking] = useState(false);
	const [selectedModel, setSelectedModel] = useState<ChatModelConfig | null>(null);
	const [selectedBuilderModel, setSelectedBuilderModel] = useState<ChatModelConfig | null>(null);
	const [buildProgress, setBuildProgress] = useState<BuilderProgress | null>(null);
	const [credentialOpen, setCredentialOpen] = useState(false);
	const [credentialRefetchTrigger, setCredentialRefetchTrigger] = useState(0);
	const [deleteConversationOpen, setDeleteConversationOpen] = useState(false);
	const [conversationToDelete, setConversationToDelete] =
		useState<BuilderConversationSummary | null>(null);
	const [agentToEditId, setAgentToEditId] = useState<string | null>(null);
	const [agentToDelete, setAgentToDelete] = useState<WorkforceAgent | null>(null);
	const [deleteAgentOpen, setDeleteAgentOpen] = useState(false);
	const conversationEndRef = useRef<HTMLDivElement | null>(null);
	const agentToEdit = agentViews.find((agent) => agent.id === agentToEditId) ?? null;

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
			setBuildProgress(stored.progress);
			if (stored.proposal) {
				setSelectedModel(stored.proposal.chat_model_config);
				setSelectedBuilderModel(stored.proposal.builder_chat_model_config);
			}
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

	useEffect(() => {
		conversationEndRef.current?.scrollIntoView({ block: 'end' });
	}, [conversation, working]);

	const newConversation = () => {
		setConversationId(null);
		setConversation([]);
		setProposal(null);
		setBuildProgress(null);
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
				selectedBuilderModel,
				conversationId,
				confirmOutline,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			setWorking(false);
		}
	};

	const confirmOutline = async () => {
		if (!selectedModel || !proposal?.planned_agents.length || !conversationId) return;
		const lastUserMessage =
			[...conversation].reverse().find((item) => item.role === 'user')?.text ?? '';
		const generatedAgentCount = proposal.planned_agents.filter(
			(agent) => !agent.reuse_agent_id,
		).length;
		setWorking(true);
		setBuildProgress(
			generatedAgentCount > 0
				? { stage: 'generating', completed: 0, total: generatedAgentCount }
				: null,
		);
		const pollProgress = async () => {
			try {
				const stored = await workforceApi.getBuilderConversation(conversationId, true);
				if (stored.progress) setBuildProgress(stored.progress);
			} catch {
				// The main prepare request owns error reporting.
			}
		};
		const progressTimer = window.setInterval(() => void pollProgress(), 750);
		try {
			const nextProposal = await workforceApi.prepare(
				prefersVietnamese(lastUserMessage)
					? 'Tôi xác nhận hướng trên. Hãy tạo và đánh giá cấu hình agent.'
					: 'I confirm this direction. Please generate and evaluate the agent configuration.',
				selectedModel,
				selectedBuilderModel,
				conversationId,
				true,
			);
			await refreshConversation(nextProposal.conversation_id);
		} finally {
			window.clearInterval(progressTimer);
			setBuildProgress(null);
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
			await Promise.all([loadAgents(), refetchAgentViews()]);
			toast.success(`Đã sẵn sàng ${result.agents.length} agent trong platform.`);
		} finally {
			setWorking(false);
		}
	};

	const toggleLifecycle = async (agent: WorkforceAgent) => {
		const next = agent.lifecycle_state === 'published' ? 'draft' : 'published';
		await workforceApi.setLifecycle(agent.agent_id, next);
		await loadAgents();
		toast.success(
			next === 'published'
				? `Đã phát hành lại ${agent.name}.`
				: `Đã ngừng phát hành ${agent.name}.`,
		);
	};

	const deleteAgent = async (agent: WorkforceAgent) => {
		await removeAgent(agent.agent_id);
		await loadAgents();
		if (agentToEditId === agent.agent_id) setAgentToEditId(null);
		toast.success(`Đã xóa ${agent.name}.`);
	};

	const conversationGroups = [
		{
			label: 'Hôm nay',
			items: conversations.filter((item) => isToday(new Date(item.updated_at))),
		},
		{
			label: 'Trước đó',
			items: conversations.filter((item) => !isToday(new Date(item.updated_at))),
		},
	];

	return (
		<>
			<div className="builder-layout">
				<aside
					id="builder-history"
					data-open={historyOpen}
					className="builder-history flex flex-col overflow-hidden p-2"
				>
					<div className="flex items-center justify-between px-2 py-3">
						<div>
							<h2 className="text-sm font-medium">Hội thoại Builder</h2>
							<Button
								className="builder-panel-close"
								variant="ghost"
								size="icon"
								aria-label="Đóng lịch sử Builder"
								onClick={() => setHistoryOpen(false)}
							>
								<X />
							</Button>
							<p className="text-xs text-muted-foreground">
								Lịch sử làm việc với Agent Builder
							</p>
						</div>
						<Badge variant="secondary">{conversations.length}</Badge>
					</div>
					<Button className="mx-2 mb-3" onClick={newConversation} disabled={working}>
						<Plus /> Hội thoại mới
					</Button>
					<div className="no-scrollbar min-h-0 flex-1 overflow-y-auto">
						{conversations.length === 0 ? (
							<div className="flex min-h-48 flex-col items-center justify-center gap-2 px-4 text-center text-sm text-muted-foreground">
								<MessageSquareDashed className="size-7" />
								<span>Chưa có hội thoại Builder.</span>
							</div>
						) : (
							conversationGroups.map(
								(group) =>
									group.items.length > 0 && (
										<SidebarGroup key={group.label} className="px-2 py-2">
											<SidebarGroupLabel>{group.label}</SidebarGroupLabel>
											<SidebarGroupContent>
												<SidebarMenu>
													{group.items.map((item) => (
														<SidebarMenuItem key={item.conversation_id}>
															<SidebarMenuButton
																isActive={
																	item.conversation_id ===
																	conversationId
																}
																className="text-muted-foreground hover:text-foreground group-has-data-[sidebar=menu-action]/menu-item:pr-16"
																onClick={() =>
																	void openConversation(
																		item.conversation_id,
																	)
																}
																disabled={working}
															>
																<MessageSquare />
																<span className="truncate">
																	{item.title}
																</span>
															</SidebarMenuButton>
															<SidebarMenuBadge className="group-hover/menu-item:hidden group-has-data-[state=open]/menu-item:hidden font-mono text-text-tertiary!">
																{format(
																	new Date(item.updated_at),
																	isToday(
																		new Date(item.updated_at),
																	)
																		? 'HH:mm'
																		: 'dd/MM',
																)}
															</SidebarMenuBadge>
															<DropdownMenu>
																<DropdownMenuTrigger asChild>
																	<SidebarMenuAction className="md:opacity-0 group-hover/menu-item:opacity-100 aria-expanded:opacity-100">
																		<Ellipsis />
																	</SidebarMenuAction>
																</DropdownMenuTrigger>
																<DropdownMenuContent
																	side="right"
																	align="start"
																	className="w-auto"
																>
																	<DropdownMenuItem
																		variant="destructive"
																		onClick={() => {
																			setConversationToDelete(
																				item,
																			);
																			setDeleteConversationOpen(
																				true,
																			);
																		}}
																	>
																		<Trash2 /> Xóa hội thoại
																	</DropdownMenuItem>
																</DropdownMenuContent>
															</DropdownMenu>
														</SidebarMenuItem>
													))}
												</SidebarMenu>
											</SidebarGroupContent>
										</SidebarGroup>
									),
							)
						)}
					</div>
				</aside>
				<main className="builder-main flex min-h-0 flex-col overflow-hidden bg-card">
					<header className="builder-header flex flex-wrap items-center justify-between border-b">
						<div className="flex items-center gap-3">
							<Button
								className="builder-history-toggle"
								variant="ghost"
								size="icon"
								aria-label="Hội thoại Builder"
								aria-controls="builder-history"
								aria-expanded={historyOpen}
								onClick={() => {
									setHistoryOpen(!historyOpen);
									setRosterOpen(false);
								}}
							>
								<PanelLeft />
							</Button>
							<ClayAvatar
								id="builder"
								label="Agent Builder"
								size={36}
								working={working}
							/>
							<div>
								<h1 className="text-xl font-medium tracking-tight">
									Agent Builder
								</h1>
								<p className="text-sm text-muted-foreground">
									Mô tả một agent hoặc nhiều agent. Builder tự viết prompt, skill
									và chọn tool.
								</p>
							</div>
						</div>
						<Button
							className="builder-roster-toggle"
							variant="ghost"
							size="icon"
							aria-label="Agent trong platform"
							aria-controls="builder-roster"
							aria-expanded={rosterOpen}
							onClick={() => {
								setRosterOpen(!rosterOpen);
								setHistoryOpen(false);
							}}
						>
							<UsersRound />
						</Button>
						<div className="builder-models grid gap-3 sm:grid-cols-2">
							<div>
								<p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
									Model runtime
								</p>
								<LlmSelect
									value={selectedModel}
									onChange={setSelectedModel}
									onAddCredential={() => setCredentialOpen(true)}
									refetchTrigger={credentialRefetchTrigger}
									placeholder="Chọn model"
									className="w-full justify-between font-mono"
									disabled={working}
								/>
							</div>
							<div>
								<p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
									Model Builder
								</p>
								<LlmSelect
									value={selectedBuilderModel}
									onChange={setSelectedBuilderModel}
									onAddCredential={() => setCredentialOpen(true)}
									refetchTrigger={credentialRefetchTrigger}
									placeholder="Giống runtime"
									allowClear
									clearLabel="Dùng model runtime"
									className="w-full justify-between font-mono"
									disabled={working}
								/>
							</div>
						</div>
					</header>
					<div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
						<div className="mx-auto max-w-4xl space-y-6">
							{conversation.length === 0 ? (
								<div className="builder-empty flex flex-col items-center justify-center text-center">
									<div
										className="mb-5 flex items-end -space-x-3"
										aria-hidden="true"
									>
										<ClayAvatar
											id="planner"
											label="Planner"
											size={56}
											className="border-4 border-white"
										/>
										<ClayAvatar
											id="builder"
											label="Agent Builder"
											size={72}
											className="border-4 border-white"
										/>
										<ClayAvatar
											id="leader"
											label="Leader"
											size={56}
											className="border-4 border-white"
										/>
									</div>
									<p className="text-xl font-semibold tracking-tight">
										Bạn cần đội agent làm gì?
									</p>
									<p className="mt-1 max-w-md text-sm text-muted-foreground">
										Mô tả công việc, dữ liệu cần dùng và kết quả bạn muốn agent
										tạo ra.
									</p>
								</div>
							) : (
								conversation.map((item, index) => (
									<Message
										key={`${item.role}:${index}`}
										align={item.role === 'user' ? 'end' : 'start'}
									>
										{item.role === 'builder' && (
											<MessageAvatar className="self-start bg-transparent">
												<ClayAvatar
													id="builder"
													label="Agent Builder"
													size={32}
													working={working}
												/>
											</MessageAvatar>
										)}
										<MessageContent>
											{item.role === 'builder' && (
												<p className="px-1 text-xs font-medium text-muted-foreground">
													Agent Builder
												</p>
											)}
											<Bubble variant="secondary">
												<BubbleContent className="px-4 py-3">
													<Markdown>{item.text}</Markdown>
												</BubbleContent>
											</Bubble>
										</MessageContent>
									</Message>
								))
							)}
							<div ref={conversationEndRef} />

							{proposal && proposal.planned_agents.length > 0 && (
								<section className="space-y-4 border-t pt-6">
									<div>
										<div className="flex items-center justify-between gap-3">
											<h2 className="font-medium">Đề xuất phân công</h2>
											<Badge variant="secondary">
												{proposal.planned_agents.length} agent
											</Badge>
										</div>
										<p className="mt-1 text-sm text-muted-foreground">
											Kiểm tra agent, tool, Knowledge Base và khả năng tái sử
											dụng trước khi sinh cấu hình.
										</p>
									</div>
									<div className="grid gap-3 md:grid-cols-2">
										{proposal.planned_agents.map((agent) => (
											<PlannedAgentCard key={agent.name} agent={agent} />
										))}
									</div>
								</section>
							)}

							{proposal?.status === 'needs_input' &&
								proposal.planned_agents.length > 0 && (
									<div className="flex justify-center py-2">
										<Button
											onClick={() => void confirmOutline()}
											disabled={working}
										>
											{working ? <Spinner /> : <CheckCircle2 />}
											{working && buildProgress
												? `${buildProgress.stage} ${buildProgress.completed}/${buildProgress.total}`
												: 'Chốt định hướng và sinh cấu hình'}
										</Button>
									</div>
								)}
							{proposal?.status === 'ready' && (
								<div className="flex justify-center py-2">
									<Button onClick={publish} disabled={working}>
										{working ? <Spinner /> : <CheckCircle2 />} Phát hành
									</Button>
								</div>
							)}

							{proposal && proposal.agents.length > 0 && (
								<section className="space-y-4 border-t pt-6">
									<div>
										<h2 className="font-medium">Cấu hình đã sinh</h2>
										<p className="mt-1 text-sm text-muted-foreground">
											Xem prompt, skill, tool và Knowledge Base trước khi phát
											hành.
										</p>
									</div>
									{proposal.agents.map((agent, agentIndex) => (
										<AgentProposalCard
											key={`${agent.name}:${agent.skill_name}`}
											proposal={agent}
											knowledgeBases={knowledgeBases}
											knowledgeBasesLoading={knowledgeBasesLoading}
											onKnowledgeBaseIdsChange={(ids) =>
												setProposal((current) => {
													if (!current) return current;
													const selected = knowledgeBases
														.filter((knowledge) =>
															ids.includes(knowledge.id),
														)
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
																		selected_knowledge_bases:
																			selected,
																	}
																: item,
														),
													};
												})
											}
										/>
									))}
								</section>
							)}
						</div>
					</div>
					<div className="builder-composer bg-card">
						<div className="mx-auto max-w-4xl">
							<div className="flex items-end gap-2 rounded-2xl border bg-background p-2 shadow-sm focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/20">
								<Textarea
									value={message}
									onChange={(event) => setMessage(event.target.value)}
									onKeyDown={(event) => {
										if (
											event.key === 'Enter' &&
											!event.shiftKey &&
											!event.nativeEvent.isComposing &&
											!working &&
											message.trim() &&
											selectedModel
										) {
											event.preventDefault();
											void prepare();
										}
									}}
									placeholder="Nhắn cho Agent Builder..."
									className="max-h-40 min-h-12 resize-none border-0 bg-transparent px-3 py-3 shadow-none focus-visible:ring-0 dark:bg-transparent"
									disabled={working}
									rows={1}
								/>
								<Button
									size="icon"
									className="size-10 shrink-0 rounded-full"
									onClick={() => void prepare()}
									disabled={working || !message.trim() || !selectedModel}
									aria-label="Gửi cho Agent Builder"
									title="Gửi"
								>
									{working ? <Spinner /> : <Send />}
								</Button>
							</div>
							{!selectedModel && (
								<p className="mt-2 px-2 text-xs text-amber-700">
									Hãy chọn model trước khi gửi yêu cầu cho Builder.
								</p>
							)}
						</div>
					</div>
				</main>

				<aside
					id="builder-roster"
					data-open={rosterOpen}
					className="builder-roster overflow-y-auto p-4"
				>
					<div className="mb-4 flex items-center justify-between">
						<div>
							<div className="flex items-center justify-between gap-2">
								<h2 className="font-medium">Agent trong platform</h2>
								<Button
									className="builder-panel-close"
									variant="ghost"
									size="icon"
									aria-label="Đóng danh sách agent"
									onClick={() => setRosterOpen(false)}
								>
									<X />
								</Button>
							</div>
							<p className="text-xs text-muted-foreground">
								Chỉ agent đang phát hành xuất hiện trong Chat
							</p>
						</div>
						<Badge variant="secondary">{agents.length}</Badge>
					</div>
					<div className="space-y-2">
						{agents.map((agent) => (
							<div key={agent.agent_id} className="builder-roster-item border p-3">
								<div className="flex items-start justify-between gap-2">
									<div className="min-w-0">
										<div className="flex min-w-0 items-center gap-2">
											<ClayAvatar
												id={agent.agent_id}
												label={agent.name}
												size={32}
											/>
											<p className="truncate text-sm font-medium">
												{agent.name}
											</p>
										</div>
										<p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
											{agent.objective}
										</p>
									</div>
									<div className="flex shrink-0 items-center">
										<Button
											size="icon-sm"
											variant="ghost"
											onClick={() => setAgentToEditId(agent.agent_id)}
											disabled={
												!agentViews.find(
													(item) => item.id === agent.agent_id,
												)?.editable
											}
											aria-label={`Cài đặt ${agent.name}`}
											title="Cài đặt"
										>
											<Settings2 />
										</Button>
										<Button
											size="icon-sm"
											variant="ghost"
											onClick={() => void toggleLifecycle(agent)}
											aria-label={
												agent.lifecycle_state === 'published'
													? `Ngừng phát hành ${agent.name}`
													: `Phát hành lại ${agent.name}`
											}
											title={
												agent.lifecycle_state === 'published'
													? 'Ngừng phát hành'
													: 'Phát hành lại'
											}
										>
											{agent.lifecycle_state === 'published' ? (
												<Power />
											) : (
												<PowerOff />
											)}
										</Button>
										<Button
											size="icon-sm"
											variant="ghost"
											className="text-destructive hover:text-destructive"
											onClick={() => {
												setAgentToDelete(agent);
												setDeleteAgentOpen(true);
											}}
											aria-label={`Xóa ${agent.name}`}
											title="Xóa"
										>
											<Trash2 />
										</Button>
									</div>
								</div>
								<div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
									<span>
										{agent.tool_count} tool · {agent.knowledge_base_count} KB
									</span>
									<span className="inline-flex items-center gap-1">
										<ChevronRight className="size-3" />
										{agent.lifecycle_state === 'published'
											? 'Đang phát hành'
											: 'Đã ngừng phát hành'}
									</span>
								</div>
							</div>
						))}
						{agents.length === 0 && (
							<p className="rounded-xl border border-dashed p-4 text-center text-sm text-muted-foreground">
								Chưa có business agent nào.
							</p>
						)}
					</div>
				</aside>
			</div>
			{agentToEdit && (
				<EditAgentDialog
					open
					onOpenChange={(open) => {
						if (!open) setAgentToEditId(null);
					}}
					agent={agentToEdit}
					onUpdated={() => {
						void loadAgents();
						void refetchAgentViews();
					}}
				/>
			)}
			<DeleteDialog
				open={deleteAgentOpen}
				onOpenChange={setDeleteAgentOpen}
				title={`Xóa agent “${agentToDelete?.name ?? ''}”?`}
				description="Agent và toàn bộ session liên quan sẽ bị xóa vĩnh viễn."
				confirmLabel="Xóa agent"
				onConfirm={async () => {
					if (agentToDelete) await deleteAgent(agentToDelete);
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
