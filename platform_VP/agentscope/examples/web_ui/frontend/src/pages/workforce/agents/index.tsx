import { Bot, Copy, FilePlus2, LayoutTemplate, Plus, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { PartnerRoutesDialog } from './partner-routes';
import { studioApi } from '@/api';
import type { AgentSummary, AgentTemplate } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

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
						<Button
							disabled={busy || description.trim().length < 3}
							onClick={() =>
								go(async () => (await studioApi.compose(description.trim(), templateId)).agent)
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

export function AgentManagementPage() {
	const navigate = useNavigate();
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
		<div className="flex size-full min-h-0 p-2">
			<main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[22px] bg-card shadow-panel">
				<header className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
					<div>
						<h1 className="text-lg font-medium">Quản lý agent</h1>
						<p className="text-xs text-muted-foreground">
							Sửa agent bằng form hoặc nhờ Builder copilot; mọi thay đổi được kiểm thử và lưu thành phiên bản.
						</p>
					</div>
					<div className="flex gap-2">
						<PartnerRoutesDialog />
						<Button onClick={() => setCreating(true)}>
							<Plus /> Tạo agent
						</Button>
					</div>
				</header>
				<div className="min-h-0 flex-1 overflow-y-auto p-4">
					{agents === null ? (
						<div className="flex justify-center p-10">
							<Spinner />
						</div>
					) : agents.length === 0 ? (
						<Empty className="border-none">
							<EmptyHeader>
								<EmptyMedia variant="icon"><Bot /></EmptyMedia>
								<EmptyTitle>Chưa có agent</EmptyTitle>
								<EmptyDescription>Tạo agent đầu tiên bằng mô tả, từ mẫu ngành hoặc agent trống.</EmptyDescription>
							</EmptyHeader>
						</Empty>
					) : (
						<Table>
							<TableHeader>
								<TableRow>
									<TableHead>Agent</TableHead>
									<TableHead>Trạng thái</TableHead>
									<TableHead>Phiên bản</TableHead>
									<TableHead>Kiểm thử gần nhất</TableHead>
									<TableHead>Tool</TableHead>
									<TableHead>Luật (tự học)</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{agents.map((agent) => (
									<TableRow
										key={agent.agent_id}
										className="cursor-pointer"
										onClick={() => navigate(`/workforce/agents/${agent.agent_id}`)}
									>
										<TableCell>
											<p className="font-medium">{agent.name}</p>
											<p className="max-w-md truncate text-xs text-muted-foreground">{agent.description}</p>
										</TableCell>
										<TableCell>
											<Badge variant={STATUS[agent.lifecycle_state].variant}>{STATUS[agent.lifecycle_state].label}</Badge>
											{agent.has_draft && agent.published_version > 0 && (
												<Badge variant="outline" className="ml-1">Có nháp</Badge>
											)}
										</TableCell>
										<TableCell>{agent.published_version ? `v${agent.published_version}` : '—'}</TableCell>
										<TableCell>
											{agent.last_test ? `${agent.last_test.passed}/${agent.last_test.total}` : '—'}
										</TableCell>
										<TableCell>{agent.tool_count}</TableCell>
										<TableCell>
											{agent.rule_count}
											{agent.learned_rule_count > 0 && (
												<span className="text-primary"> (+{agent.learned_rule_count})</span>
											)}
										</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					)}
				</div>
			</main>
			<CreateAgentDialog open={creating} onOpenChange={setCreating} agents={agents ?? []} />
		</div>
	);
}
