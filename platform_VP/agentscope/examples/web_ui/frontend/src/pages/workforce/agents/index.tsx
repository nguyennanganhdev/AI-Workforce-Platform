import { useQueryClient } from '@tanstack/react-query';
import {
	Bot,
	Copy,
	FilePlus2,
	LayoutTemplate,
	List,
	Plus,
	Sparkles,
	Workflow,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ActivityDialog } from './activity';
import { AgentMapView, AgentTable } from './map-view';
import { studioApi } from '@/api';
import type { AgentSummary, AgentTemplate } from '@/api';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { refreshStudio, useStudioAgents } from '@/hooks/useStudioAgents';

export { AgentDetailPage } from './detail';

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
							placeholder="Ví dụ: Agent tìm chuyến bay theo ngày và số khách. So sánh giá, nói rõ điều kiện vé, chưa đặt vé khi khách chưa đồng ý…"
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

const VIEWS = [
	{ key: 'map', label: 'Sơ đồ 3D', icon: Workflow },
	{ key: 'list', label: 'Danh sách', icon: List },
] as const;

/**
 * Agent management: opens on the 3D map with the list beside it; the table
 * view adds versions, tests and rules. Both read one cache, so a change in
 * either shows in both. The view is in the URL (`?view=list`).
 */
export function AgentManagementPage() {
	const [params, setParams] = useSearchParams();
	const view = params.get('view') === 'list' ? 'list' : 'map';
	const client = useQueryClient();
	const { data: agents, isError } = useStudioAgents();
	const [creating, setCreating] = useState(false);
	const [removing, setRemoving] = useState<AgentSummary | null>(null);

	useEffect(() => {
		if (isError) toast.error('Không tải được danh sách agent.');
	}, [isError]);

	return (
		<div className="flex size-full">
			<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
				<div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-3">
					<div>
						<h1 className="text-[17px]/6 font-semibold">Quản lý agent</h1>
						<p className="mt-0.5 text-[13px]/[18px] text-muted-foreground">
							Sơ đồ và danh sách đồng bộ với nhau; mọi thay đổi agent được kiểm thử và lưu thành phiên bản.
						</p>
					</div>
					<div className="flex flex-wrap items-center gap-2">
						<Tabs value={view} onValueChange={(next) => setParams(next === 'list' ? { view: 'list' } : {}, { replace: true })}>
							<TabsList>
								{VIEWS.map(({ key, label, icon: Icon }) => (
									<TabsTrigger key={key} value={key} className="px-2.5">
										<Icon /> {label}
									</TabsTrigger>
								))}
							</TabsList>
						</Tabs>
						<ActivityDialog />
						<Button onClick={() => setCreating(true)}>
							<Plus /> Tạo agent
						</Button>
					</div>
				</div>
				<Separator />
				<div className="min-h-0 flex-1">
					{agents === undefined ? (
						<div className="flex flex-col gap-2 p-4" aria-busy="true">
							{[0, 1, 2, 3].map((row) => (
								<Skeleton key={row} className="h-14 w-full" />
							))}
						</div>
					) : agents.length === 0 ? (
						<Empty className="h-full border-none">
							<EmptyHeader>
								<EmptyMedia variant="icon">
									<Bot />
								</EmptyMedia>
								<EmptyTitle>Chưa có agent</EmptyTitle>
								<EmptyDescription>Tạo agent đầu tiên bằng mô tả, từ mẫu ngành hoặc agent trống.</EmptyDescription>
							</EmptyHeader>
						</Empty>
					) : view === 'map' ? (
						<AgentMapView agents={agents} onRemove={setRemoving} />
					) : (
						<AgentTable agents={agents} onRemove={setRemoving} />
					)}
				</div>
			</main>
			<CreateAgentDialog open={creating} onOpenChange={setCreating} agents={agents ?? []} />
			<DeleteDialog
				open={removing !== null}
				onOpenChange={(open) => !open && setRemoving(null)}
				title={`Gỡ agent "${removing?.name ?? ''}"?`}
				description="Agent bị gỡ khỏi platform, Leader không mời agent này nữa. Lịch sử phiếu đã xử lý vẫn giữ nguyên."
				confirmLabel="Gỡ agent"
				onConfirm={async () => {
					if (!removing) return;
					await studioApi.remove(removing.agent_id);
					toast.success(`Đã gỡ ${removing.name}.`);
					await refreshStudio(client);
				}}
			/>
		</div>
	);
}
