import {
	Bot,
	Copy,
	Ellipsis,
	FilePlus2,
	LayoutTemplate,
	List,
	MessageSquare,
	Pencil,
	Plus,
	Sparkles,
	Workflow,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ActivityDialog } from './activity';
import { PartnerRoutesDialog } from './partner-routes';
import { studioApi } from '@/api';
import type { AgentSummary, AgentTemplate, AgentView } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAgents } from '@/hooks/useAgents';
import { useSettled } from '@/hooks/useSettled';
import { AgentGraph } from '@/pages/agents/AgentGraph';

export { AgentDetailPage } from './detail';

const STATUS = {
	draft: { label: 'Bản nháp', variant: 'secondary' },
	published: { label: 'Đang phát hành', variant: 'default' },
	withdrawn: { label: 'Đã ngừng', variant: 'outline' },
} as const;

function CreateAgentDialog({
	open,
	onOpenChange,
	agents,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agents: AgentSummary[];
}) {
	const navigate = useNavigate();
	const [templates, setTemplates] = useState<AgentTemplate[]>([]);
	const [description, setDescription] = useState('');
	const [templateId, setTemplateId] = useState<string | undefined>();
	const [allowTeam, setAllowTeam] = useState(true);
	const [runTests, setRunTests] = useState(false);
	const [busy, setBusy] = useState(false);

	useEffect(() => {
		if (open) studioApi.templates().then(setTemplates).catch(() => setTemplates([]));
	}, [open]);

	const go = async (task: () => Promise<{ agent_id: string }>) => {
		setBusy(true);
		try {
			const agent = await task();
			onOpenChange(false);
			navigate(`/workforce/agents/${agent.agent_id}`);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : String(error));
		} finally {
			setBusy(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Tạo agent</DialogTitle>
					<DialogDescription>
						Agent mới luôn là bản nháp. Bạn xem lại trên form, chạy kiểm thử rồi mới phát hành.
					</DialogDescription>
				</DialogHeader>
				<Tabs defaultValue="describe">
					<TabsList>
						<TabsTrigger value="describe"><Sparkles /> Mô tả bằng lời</TabsTrigger>
						<TabsTrigger value="template"><LayoutTemplate /> Từ mẫu ngành</TabsTrigger>
						<TabsTrigger value="clone"><Copy /> Nhân bản</TabsTrigger>
					</TabsList>
					<TabsContent value="describe" className="space-y-3 pt-2">
						<Textarea
							value={description}
							rows={6}
							placeholder="Ví dụ: Agent tiếp nhận sự cố điện nước của cư dân. Luôn hướng dẫn an toàn trước, không báo giá khi chưa có ảnh, sự cố khẩn cấp thì báo bảo vệ…"
							onChange={(event) => setDescription(event.target.value)}
						/>
						<div className="flex flex-wrap items-center gap-1.5 text-xs">
							<span className="text-muted-foreground">Dựa trên mẫu (tuỳ chọn):</span>
							{templates.map((template) => (
								<Button
									key={template.id}
									size="xs"
									variant={templateId === template.id ? 'default' : 'outline'}
									onClick={() => setTemplateId(templateId === template.id ? undefined : template.id)}
								>
									{template.title}
								</Button>
							))}
						</div>
						<div className="flex flex-wrap gap-4 text-xs">
							<label className="flex items-center gap-2">
								<Checkbox checked={allowTeam} onCheckedChange={(value) => setAllowTeam(value === true)} />
								Cho Builder chia thành nhóm agent nếu việc gồm nhiều chuyên môn
							</label>
							<label className="flex items-center gap-2">
								<Checkbox checked={runTests} onCheckedChange={(value) => setRunTests(value === true)} />
								Chạy kiểm thử ngay (gọi model thật)
							</label>
						</div>
						<Button
							disabled={busy || description.trim().length < 3}
							onClick={() =>
								go(async () => {
									const result = await studioApi.compose(description.trim(), templateId, { allowTeam, runTests });
									if (result.agents.length > 1) {
										toast.success(result.reply.assistant_message);
									}
									const failed = Object.values(result.test_reports).find((report) => report.errors);
									if (failed) toast.error(`Chưa kiểm thử được: ${failed.model_error}`);
									return result.agent;
								})
							}
						>
							{busy ? <Spinner /> : <Sparkles />} Để Builder soạn bản nháp
						</Button>
					</TabsContent>
					<TabsContent value="template" className="grid gap-2 pt-2 md:grid-cols-2">
						{templates.map((template) => (
							<button
								key={template.id}
								type="button"
								disabled={busy}
								onClick={() => go(() => studioApi.create({ template_id: template.id }))}
								className="space-y-1 rounded-xl border border-border/70 p-3 text-left transition-colors hover:bg-muted"
							>
								<Badge variant="outline">{template.domain}</Badge>
								<p className="text-sm font-medium">{template.title}</p>
								<p className="text-xs text-muted-foreground">{template.spec.description}</p>
								<p className="text-xs text-muted-foreground">
									{template.spec.rules.length} luật · {template.spec.tests.length} kịch bản kiểm thử
								</p>
							</button>
						))}
						<button
							type="button"
							disabled={busy}
							onClick={() => go(() => studioApi.create({}))}
							className="flex items-center gap-2 rounded-xl border border-dashed p-3 text-left text-sm hover:bg-muted"
						>
							<FilePlus2 className="size-4" /> Agent trống
						</button>
					</TabsContent>
					<TabsContent value="clone" className="space-y-2 pt-2">
						{agents.map((agent) => (
							<button
								key={agent.agent_id}
								type="button"
								disabled={busy}
								onClick={() => go(() => studioApi.create({ clone_from: agent.agent_id }))}
								className="flex w-full items-center gap-2 rounded-xl border border-border/70 p-3 text-left text-sm hover:bg-muted"
							>
								<Bot className="size-4" /> {agent.name}
							</button>
						))}
						{agents.length === 0 && <p className="text-xs text-muted-foreground">Chưa có agent để nhân bản.</p>}
					</TabsContent>
				</Tabs>
			</DialogContent>
		</Dialog>
	);
}

/** The Leader and its agents as a map; a click on an agent opens its page. */
function AgentMap() {
	const navigate = useNavigate();
	const isMobile = useIsMobile();
	const { agents, loading } = useAgents();
	const settled = useSettled(loading);

	if (!settled) return <Skeleton className="m-4 h-[calc(100%-2rem)]" />;
	// A node canvas has no usable form on a phone; the list carries the same agents.
	if (isMobile) {
		return <p className="p-4 text-sm text-muted-foreground">Sơ đồ cần màn hình rộng. Xem các agent ở tab Danh sách.</p>;
	}
	return (
		<AgentGraph
			agents={agents}
			onChat={(agent: AgentView) => navigate(`/chat/${agent.id}`)}
			onEdit={(agent: AgentView) => navigate(`/workforce/agents/${agent.id}`)}
		/>
	);
}

function AgentTable({ agents }: { agents: AgentSummary[] }) {
	const navigate = useNavigate();
	return (
		<div className="h-full overflow-y-auto px-4 pb-4">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Agent</TableHead>
						<TableHead>Trạng thái</TableHead>
						<TableHead>Phiên bản</TableHead>
						<TableHead>Kiểm thử gần nhất</TableHead>
						<TableHead>Tool</TableHead>
						<TableHead>Luật (tự học)</TableHead>
						<TableHead className="w-10">
							<span className="sr-only">Thao tác</span>
						</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{agents.map((agent) => (
						<TableRow
							key={agent.agent_id}
							className="h-14 cursor-pointer"
							onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}
						>
							<TableCell className="whitespace-normal">
								<div className="flex items-center gap-3">
									<ClayAvatar id={agent.agent_id} label={agent.name} size={36} />
									<div className="min-w-0">
										<p className="truncate text-[14px]/[20px] font-medium">{agent.name}</p>
										<p className="line-clamp-1 max-w-xl text-[12px]/[16px] text-muted-foreground">
											{agent.description || 'Chưa có mô tả'}
										</p>
									</div>
								</div>
							</TableCell>
							<TableCell>
								<Badge variant={STATUS[agent.lifecycle_state].variant}>{STATUS[agent.lifecycle_state].label}</Badge>
								{agent.has_draft && agent.published_version > 0 && (
									<Badge variant="outline" className="ml-1">Có nháp</Badge>
								)}
							</TableCell>
							<TableCell>{agent.published_version ? `v${agent.published_version}` : '-'}</TableCell>
							<TableCell>
								{agent.last_test
									? agent.last_test.errors
										? 'lỗi model'
										: `${agent.last_test.passed}/${agent.last_test.total}`
									: '-'}
							</TableCell>
							<TableCell>{agent.tool_count}</TableCell>
							<TableCell>
								{agent.rule_count}
								{agent.learned_rule_count > 0 && (
									<span className="text-primary"> (+{agent.learned_rule_count})</span>
								)}
							</TableCell>
							<TableCell onClick={(event) => event.stopPropagation()}>
								<DropdownMenu>
									<DropdownMenuTrigger asChild>
										<Button variant="ghost" size="icon" aria-label={`Thao tác với ${agent.name}`}>
											<Ellipsis />
										</Button>
									</DropdownMenuTrigger>
									<DropdownMenuContent align="end" className="w-auto">
										<DropdownMenuItem onClick={() => navigate(`/chat/${agent.agent_id}`)}>
											<MessageSquare /> Trò chuyện
										</DropdownMenuItem>
										<DropdownMenuItem onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}>
											<Pencil /> Sửa và kiểm thử
										</DropdownMenuItem>
									</DropdownMenuContent>
								</DropdownMenu>
							</TableCell>
						</TableRow>
					))}
				</TableBody>
			</Table>
		</div>
	);
}

const VIEWS = [
	{ key: 'list', label: 'Danh sách', icon: List },
	{ key: 'graph', label: 'Sơ đồ', icon: Workflow },
] as const;

/**
 * Agent management: the agents as a table (versions, tests, rules) or as a
 * map around the Leader. The view is in the URL (`?view=graph`).
 */
export function AgentManagementPage() {
	const [params, setParams] = useSearchParams();
	const view = params.get('view') === 'graph' ? 'graph' : 'list';
	const [agents, setAgents] = useState<AgentSummary[] | null>(null);
	const [creating, setCreating] = useState(false);

	useEffect(() => {
		studioApi
			.listAgents()
			.then(setAgents)
			.catch((error) => {
				toast.error(error instanceof Error ? error.message : String(error));
				setAgents([]);
			});
	}, []);

	return (
		<div className="flex size-full">
			<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-3">
					<div>
						<h1 className="text-[17px]/6 font-semibold">Quản lý agent</h1>
						<p className="mt-0.5 text-[13px]/[18px] text-muted-foreground">
							Sửa agent bằng form hoặc nhờ Builder copilot; mọi thay đổi được kiểm thử và lưu thành phiên bản.
						</p>
					</div>
					<div className="flex flex-wrap items-center gap-2">
						<Tabs
							value={view}
							onValueChange={(next) => setParams(next === 'graph' ? { view: 'graph' } : {}, { replace: true })}
						>
							<TabsList>
								{VIEWS.map(({ key, label, icon: Icon }) => (
									<TabsTrigger key={key} value={key} className="px-2.5">
										<Icon /> {label}
									</TabsTrigger>
								))}
							</TabsList>
						</Tabs>
						<ActivityDialog />
						<PartnerRoutesDialog />
						<Button onClick={() => setCreating(true)}>
							<Plus /> Tạo agent
						</Button>
					</div>
				</div>
				<Separator />
				<div className="min-h-0 flex-1">
					{view === 'graph' ? (
						<AgentMap />
					) : agents === null ? (
						<div className="flex flex-col gap-2 p-4" aria-busy="true">
							{[0, 1, 2, 3].map((row) => (
								<Skeleton key={row} className="h-14 w-full" />
							))}
						</div>
					) : agents.length === 0 ? (
						<Empty className="h-full border-none">
							<EmptyHeader>
								<EmptyMedia variant="icon"><Bot /></EmptyMedia>
								<EmptyTitle>Chưa có agent</EmptyTitle>
								<EmptyDescription>Tạo agent đầu tiên bằng mô tả, từ mẫu ngành hoặc agent trống.</EmptyDescription>
							</EmptyHeader>
						</Empty>
					) : (
						<AgentTable agents={agents} />
					)}
				</div>
			</main>
			<CreateAgentDialog open={creating} onOpenChange={setCreating} agents={agents ?? []} />
		</div>
	);
}
