import { format, isToday } from 'date-fns';
import {
	Bot,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	Database,
	Ellipsis,
	Hammer,
	MessageSquare,
	MessageSquareDashed,
	Plus,
	Power,
	PowerOff,
	Send,
	Sparkles,
	Trash2,
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
	WorkforceAgent,
	KnowledgeBaseView,
} from '@/api';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Markdown } from '@/components/markdown';
import { LlmSelect } from '@/components/select/LlmSelect';
import { Badge } from '@/components/ui/badge';
import { Bubble, BubbleContent } from '@/components/ui/bubble';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Message, MessageContent } from '@/components/ui/message';
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
import { useKnowledgeBases } from '@/hooks/useKnowledgeBases';

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
					<div className="xl:col-span-2 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
						<CircleAlert className="mt-0.5 size-4 text-amber-600" />
						<span>
							Nghiệp vụ trùng với <strong>{proposal.reuse_agent_name}</strong>. Khi
							phát hành, platform sẽ tái sử dụng agent cũ thay vì tạo bản sao.
						</span>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

export function AgentBuilderPage() {
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
			<div className="grid size-full min-h-0 gap-2 p-2 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
				<aside className="flex min-h-0 flex-col overflow-hidden rounded-[22px] bg-card p-2 shadow-panel">
					<div className="flex items-center justify-between px-2 py-3">
						<div>
							<h2 className="text-sm font-medium">Hội thoại Builder</h2>
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
				<main className="flex min-h-0 flex-col overflow-hidden rounded-[22px] bg-card shadow-panel">
					<header className="flex flex-wrap items-center justify-between gap-4 border-b px-6 py-5">
						<div className="flex items-center gap-3">
							<div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
								<Hammer className="size-5" />
							</div>
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
						<div className="min-w-56">
							<p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
								Model cho Builder và agent
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
					</header>
					<div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
						<div className="mx-auto max-w-5xl space-y-5">
							<div className="rounded-xl border bg-background p-4">
								{conversation.length > 0 && (
									<div className="mb-5 max-h-80 space-y-5 overflow-y-auto border-b pb-5">
										{conversation.map((item, index) => (
											<Message
												key={`${item.role}:${index}`}
												align={item.role === 'user' ? 'end' : 'start'}
											>
												<MessageContent>
													<Bubble
														variant={
															item.role === 'user' ? 'muted' : 'ghost'
														}
													>
														<BubbleContent>
															<Markdown>{item.text}</Markdown>
														</BubbleContent>
													</Bubble>
												</MessageContent>
											</Message>
										))}
									</div>
								)}
								<div className="flex items-start gap-3">
									<Sparkles className="mt-1 size-4 text-primary" />
									<div className="flex-1">
										<p className="text-sm font-medium">
											Bạn cần agent làm nghiệp vụ gì?
										</p>
										<Textarea
											value={message}
											onChange={(event) => setMessage(event.target.value)}
											placeholder="Ví dụ: Tạo agent tìm khách sạn, kiểm tra phòng trống và đề xuất theo ngân sách..."
											className="mt-3 min-h-28 resize-y bg-background"
											disabled={working}
										/>
										<div className="mt-3 flex justify-end">
											<Button
												onClick={() => void prepare()}
												disabled={
													working || !message.trim() || !selectedModel
												}
											>
												{working ? <Spinner /> : <Send />}
												Gửi cho Builder
											</Button>
										</div>
										{!selectedModel && (
											<p className="mt-2 text-right text-xs text-amber-700">
												Hãy chọn model trước khi gửi yêu cầu cho Builder.
											</p>
										)}
									</div>
								</div>
							</div>

							{proposal && (
								<>
									<div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3">
										<div>
											<p className="text-sm font-medium">
												{proposal.assistant_message}
											</p>
											{proposal.clarification_question && (
												<p className="mt-1 text-sm text-amber-700">
													{proposal.clarification_question}
												</p>
											)}
											<p className="mt-1 text-xs text-muted-foreground">
												Model:{' '}
												<span className="font-mono">
													{proposal.chat_model_config.model}
												</span>
												{' · '}
												{proposal.fixed_config.runtime_note}
											</p>
										</div>
										{proposal.status === 'ready' && (
											<Button onClick={publish} disabled={working}>
												<CheckCircle2 /> Phát hành
											</Button>
										)}
										{proposal.status === 'needs_input' &&
											proposal.planned_agents.length > 0 && (
												<Button
													onClick={() => void confirmOutline()}
													disabled={working}
												>
													<CheckCircle2 /> Chốt định hướng và sinh cấu
													hình
												</Button>
											)}
										{proposal.status === 'published' && (
											<Badge>Đã phát hành</Badge>
										)}
										{proposal.status === 'blocked' && (
											<Badge variant="destructive">Bị chặn</Badge>
										)}
									</div>
									{proposal.planned_agents.length > 0 && (
										<div className="grid gap-3 md:grid-cols-2">
											{proposal.planned_agents.map((agent) => (
												<div
													key={agent.name}
													className="rounded-xl border bg-background p-4"
												>
													<div className="flex items-center gap-2">
														<Bot className="size-4 text-primary" />
														<p className="font-medium">{agent.name}</p>
													</div>
													<p className="mt-2 text-sm text-muted-foreground">
														{agent.objective}
													</p>
													<div className="mt-3 flex flex-wrap gap-1.5">
														{agent.suggested_tools.map((tool) => (
															<Badge
																key={tool.id}
																variant="secondary"
																className="font-mono text-[10px]"
															>
																{tool.tool_name}
															</Badge>
														))}
														{agent.suggested_knowledge_bases.map(
															(knowledge) => (
																<Badge
																	key={knowledge.id}
																	variant="outline"
																	className="text-[10px]"
																>
																	<Database className="size-3" />{' '}
																	{knowledge.name}
																</Badge>
															),
														)}
													</div>
												</div>
											))}
										</div>
									)}
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
								</>
							)}
						</div>
					</div>
				</main>

				<aside className="min-h-0 overflow-y-auto rounded-[22px] bg-card p-4 shadow-panel">
					<div className="mb-4 flex items-center justify-between">
						<div>
							<h2 className="font-medium">Agent trong platform</h2>
							<p className="text-xs text-muted-foreground">
								Leader chỉ thấy agent đang phát hành
							</p>
						</div>
						<Badge variant="secondary">{agents.length}</Badge>
					</div>
					<div className="space-y-2">
						{agents.map((agent) => (
							<div key={agent.agent_id} className="rounded-xl border p-3">
								<div className="flex items-start justify-between gap-2">
									<div className="min-w-0">
										<p className="truncate text-sm font-medium">{agent.name}</p>
										<p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
											{agent.objective}
										</p>
									</div>
									<Button
										size="icon-sm"
										variant="ghost"
										onClick={() => toggleLifecycle(agent)}
									>
										{agent.lifecycle_state === 'published' ? (
											<Power />
										) : (
											<PowerOff />
										)}
									</Button>
								</div>
								<div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
									<span>
										{agent.tool_count} tool · {agent.knowledge_base_count} KB
									</span>
									<span className="inline-flex items-center gap-1">
										<ChevronRight className="size-3" />
										{agent.lifecycle_state === 'published'
											? 'Đang phát hành'
											: 'Bản nháp'}
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
