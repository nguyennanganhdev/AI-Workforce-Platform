import {
	BookText,
	Bot,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	Hammer,
	LibraryBig,
	Plus,
	Power,
	PowerOff,
	Send,
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
} from '@/api';
import { ListRow } from '@/components/chat/ListRow';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Markdown } from '@/components/markdown';
import { LlmSelect } from '@/components/select/LlmSelect';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';

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
							{passed ? 'Eval đạt' : 'Eval chưa đạt'}
						</Badge>
					</div>
					<p className="mt-1 text-sm text-muted-foreground">{proposal.objective}</p>
					{failed.length > 0 && <p className="mt-1 text-xs text-destructive">Chưa đạt: {failed.join('; ')}.</p>}
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
				<p className="mt-3 flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400">
					<CircleAlert className="mt-0.5 size-4 shrink-0" />
					<span>
						Trùng nghiệp vụ với <strong>{proposal.reuse_agent_name}</strong>; khi phát hành, platform dùng lại
						agent đó thay vì tạo bản sao.
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
	const [selectedModel, setSelectedModel] = useState<ChatModelConfig | null>(null);
	const [credentialOpen, setCredentialOpen] = useState(false);
	const [credentialRefetchTrigger, setCredentialRefetchTrigger] = useState(0);
	const [agentsOpen, setAgentsOpen] = useState(false);
	const [deleting, setDeleting] = useState<BuilderConversationSummary | null>(null);

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
		const lastUserMessage = [...conversation]
			.reverse()
			.find((item) => item.role === 'user')?.text ?? '';
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
				<ul className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pt-1 pb-2">
					{conversations.length === 0 ? (
						<li className="px-3 py-6 text-center text-[13px]/[18px] text-muted-foreground">
							Chưa có hội thoại. Mô tả agent bạn cần ở khung bên phải.
						</li>
					) : (
						conversations.map((item) => (
							<ListRow
								key={item.conversation_id}
								title={item.title}
								active={item.conversation_id === conversationId}
								disabled={working}
								onSelect={() => void openConversation(item.conversation_id)}
								onDelete={() => setDeleting(item)}
							/>
						))
					)}
				</ul>
			</aside>

			<main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
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
					<h2 className="min-w-0 flex-1 truncate text-[15px]/5 font-semibold">
						{current?.title ?? 'Hội thoại mới'}
					</h2>
					<LlmSelect
						value={selectedModel}
						onChange={setSelectedModel}
						onAddCredential={() => setCredentialOpen(true)}
						refetchTrigger={credentialRefetchTrigger}
						placeholder="Chọn model"
						className="w-48 font-mono"
						disabled={working}
					/>
					<Button variant="outline" size="sm" onClick={() => setAgentsOpen(true)}>
						<Bot /> Agent
						<Badge variant="secondary" className="ml-0.5">{agents.length}</Badge>
					</Button>
				</header>

				<div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
					<div className="mx-auto max-w-4xl space-y-5">
						{conversation.length === 0 && !proposal && (
							<div className="pt-10 text-center">
								<Hammer className="mx-auto size-6 text-muted-foreground" />
								<p className="mt-3 text-[15px]/5 font-semibold">Bạn cần agent làm nghiệp vụ gì?</p>
								<p className="mx-auto mt-1 max-w-md text-[13px]/[18px] text-muted-foreground">
									Mô tả một agent hoặc cả một đội. Builder viết prompt, chọn tool, gắn kho tri thức,
									dùng lại skill đã có rồi chấm eval trước khi bạn phát hành.
								</p>
							</div>
						)}
						{conversation.map((item, index) =>
							item.role === 'user' ? (
								<div
									key={`user:${index}`}
									className="ml-auto w-fit max-w-[84%] whitespace-pre-wrap rounded-2xl bg-[var(--cue-bg-subtle,var(--muted))] px-3.5 py-2 text-[15px]/6"
								>
									{item.text}
								</div>
							) : (
								<div key={`builder:${index}`} className="flex gap-3">
									<span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
										<Hammer className="size-3.5 text-muted-foreground" />
									</span>
									<Markdown className="min-w-0 flex-1 text-[15px]/6">{item.text}</Markdown>
								</div>
							),
						)}
						{working && (
							<p className="flex items-center gap-2 text-[13px]/[18px] text-muted-foreground">
								<Spinner /> Builder đang soạn, có thể mất vài phút với một đội nhiều agent.
							</p>
						)}

						{proposal && (
							<>
								<div className="flex flex-wrap items-center justify-between gap-3 border-y py-3">
									<div className="min-w-0">
										<p className="text-sm font-medium">{proposal.assistant_message}</p>
										{proposal.clarification_question && (
											<p className="mt-1 text-sm text-amber-700">
												{proposal.clarification_question}
											</p>
										)}
										<p className="mt-1 text-xs text-muted-foreground">
											Model: <span className="font-mono">{proposal.chat_model_config.model}</span>
											{' · '}{proposal.fixed_config.runtime_note}
										</p>
									</div>
									{proposal.status === 'ready' && (
										<Button onClick={publish} disabled={working}>
											<CheckCircle2 /> Phát hành
										</Button>
									)}
									{proposal.status === 'needs_input' && proposal.planned_agents.length > 0 && (
										<Button onClick={() => void confirmOutline()} disabled={working}>
											<CheckCircle2 /> Chốt định hướng và sinh cấu hình
										</Button>
									)}
									{proposal.status === 'published' && <Badge>Đã phát hành</Badge>}
									{proposal.status === 'blocked' && <Badge variant="destructive">Bị chặn</Badge>}
								</div>
								{proposal.planned_agents.length > 0 && (
									<div className="grid gap-3 md:grid-cols-2">
										{proposal.planned_agents.map((agent) => (
											<div key={agent.name} className="rounded-xl border bg-background p-4">
												<div className="flex items-center gap-2">
													<Bot className="size-4 text-primary" />
													<p className="font-medium">{agent.name}</p>
												</div>
												<p className="mt-2 text-sm text-muted-foreground">{agent.objective}</p>
												<div className="mt-3 flex flex-wrap gap-1.5">
													{agent.suggested_tools.map((tool) => (
														<Badge key={tool.id} variant="secondary" className="font-mono text-[10px]">
															{tool.tool_name}
														</Badge>
													))}
												</div>
											</div>
										))}
									</div>
								)}
								{proposal.agents.map((agent) => (
									<AgentProposalCard key={`${agent.name}:${agent.skill_name}`} proposal={agent} />
								))}
							</>
						)}
					</div>
				</div>

				<div className="shrink-0 px-4 pb-4">
					<div className="mx-auto max-w-4xl rounded-2xl border bg-background p-2 focus-within:ring-1 focus-within:ring-ring">
						<Textarea
							value={message}
							onChange={(event) => setMessage(event.target.value)}
							onKeyDown={(event) => {
								if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
									event.preventDefault();
									void prepare();
								}
							}}
							placeholder="Ví dụ: Tạo agent tìm khách sạn, kiểm tra phòng trống và đề xuất theo ngân sách..."
							className="min-h-16 resize-none border-none shadow-none focus-visible:ring-0"
							disabled={working}
						/>
						<div className="flex items-center justify-between gap-2 px-1">
							<p className="text-xs text-amber-700">
								{!selectedModel && 'Hãy chọn model trước khi gửi yêu cầu cho Builder.'}
							</p>
							<Button
								size="sm"
								onClick={() => void prepare()}
								disabled={working || !message.trim() || !selectedModel}
							>
								{working ? <Spinner /> : <Send />}
								Gửi cho Builder
							</Button>
						</div>
					</div>
				</div>
			</main>
		</div>

		<Sheet open={agentsOpen} onOpenChange={setAgentsOpen}>
			<SheetContent className="w-[360px] sm:max-w-[360px]">
				<SheetHeader>
					<SheetTitle>Agent trong platform</SheetTitle>
					<SheetDescription>Leader chỉ mời agent đang phát hành. Bấm nút nguồn để bật hoặc tắt.</SheetDescription>
				</SheetHeader>
				<div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-4">
					{agents.map((agent) => (
						<div key={agent.agent_id} className="flex items-start gap-3 rounded-xl px-2 py-2.5 hover:bg-muted/60">
							<ClayAvatar id={agent.agent_id} label={agent.name} size={32} />
							<div className="min-w-0 flex-1">
								<p className="truncate text-sm font-medium">{agent.name}</p>
								<p className="line-clamp-2 text-xs text-muted-foreground">{agent.objective}</p>
								<p className="mt-1 text-[11px] text-muted-foreground">
									{agent.tool_count} tool ·{' '}
									{agent.lifecycle_state === 'published' ? 'Đang phát hành' : 'Bản nháp'}
								</p>
							</div>
							<Button
								size="icon-sm"
								variant="ghost"
								aria-label={agent.lifecycle_state === 'published' ? 'Ngừng phát hành' : 'Phát hành'}
								title={agent.lifecycle_state === 'published' ? 'Ngừng phát hành' : 'Phát hành'}
								onClick={() => toggleLifecycle(agent)}
							>
								{agent.lifecycle_state === 'published' ? <Power /> : <PowerOff />}
							</Button>
						</div>
					))}
					{agents.length === 0 && (
						<p className="px-2 py-6 text-center text-sm text-muted-foreground">Chưa có business agent nào.</p>
					)}
				</div>
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
