import { ArrowLeft, FlaskConical, History, Rocket, RotateCcw, Save, Sparkles, Trash2, Undo2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import {
	CollaboratorsEditor,
	EscalationEditor,
	ExamplesEditor,
	KnowledgeEditor,
	RulesEditor,
	Section,
	StringListEditor,
	TestsEditor,
	TextField,
	ToolsEditor,
} from './editors';
import { ChangeList, CopilotPanel, TestReportView } from './panels';
import type { CopilotTurn } from './panels';
import { knowledgeBaseApi, studioApi } from '@/api';
import type {
	AgentDetail,
	AgentMemory,
	AgentSpec,
	CatalogTool,
	KnowledgeBaseView,
	TestReport,
} from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';


const STATUS_LABEL = {
	draft: 'Bản nháp',
	published: 'Đang phát hành',
	withdrawn: 'Đã ngừng',
} as const;

const AUTHOR_LABEL: Record<string, string> = {
	manager: 'BQL',
	builder: 'Builder copilot',
	agent: 'Agent tự cải tiến',
	legacy: 'Có sẵn',
	template: 'Mẫu',
};

function errorText(error: unknown) {
	return error instanceof Error ? error.message : String(error);
}

export function AgentDetailPage() {
	const { agentId = '' } = useParams();
	const navigate = useNavigate();
	const [detail, setDetail] = useState<AgentDetail | null>(null);
	const [spec, setSpec] = useState<AgentSpec | null>(null);
	const [dirty, setDirty] = useState(false);
	const [busy, setBusy] = useState<string | null>(null);
	const [confirmRemove, setConfirmRemove] = useState(false);
	const [catalog, setCatalog] = useState<CatalogTool[]>([]);
	const [bases, setBases] = useState<KnowledgeBaseView[]>([]);
	const [memories, setMemories] = useState<AgentMemory[]>([]);
	const [turns, setTurns] = useState<CopilotTurn[]>([]);
	const [report, setReport] = useState<TestReport | null>(null);
	const [publishNote, setPublishNote] = useState('');

	const apply = useCallback((value: AgentDetail) => {
		setDetail(value);
		setSpec(value.draft);
		setReport(value.last_test);
		setDirty(false);
	}, []);

	const loadMemories = useCallback(() => {
		studioApi
			.memories(agentId)
			.then(setMemories)
			.catch(() => setMemories([]));
	}, [agentId]);

	useEffect(() => {
		studioApi.getAgent(agentId).then(apply).catch((error) => toast.error(errorText(error)));
		studioApi.tools().then(setCatalog).catch(() => setCatalog([]));
		knowledgeBaseApi
			.listAll()
			.then(setBases)
			.catch(() => setBases([]));
		loadMemories();
	}, [agentId, apply, loadMemories]);

	const update = useCallback(<K extends keyof AgentSpec>(key: K, value: AgentSpec[K]) => {
		setSpec((current) => (current ? { ...current, [key]: value } : current));
		setDirty(true);
	}, []);

	const run = async <T,>(label: string, task: () => Promise<T>) => {
		setBusy(label);
		try {
			return await task();
		} catch (error) {
			toast.error(errorText(error));
			return undefined;
		} finally {
			setBusy(null);
		}
	};

	const saveDraft = async () => {
		if (!spec) return undefined;
		const value = await run('save', () => studioApi.saveDraft(agentId, spec, 'Sửa trên form'));
		if (value) {
			apply(value);
			toast.success('Đã lưu bản nháp.');
		}
		return value;
	};

	const sendCopilot = async (message: string) => {
		if (dirty && !(await saveDraft())) return;
		setTurns((items) => [...items, { user: message }]);
		const result = await run('copilot', () => studioApi.copilot(agentId, message));
		setTurns((items) => {
			const next = [...items];
			next[next.length - 1] = result
				? {
						user: message,
						reply: result.reply.assistant_message,
						questions: result.reply.questions,
						changes: result.changes,
					}
				: { user: message, error: 'Copilot chưa xử lý được yêu cầu này.' };
			return next;
		});
		if (result) apply(result.agent);
	};

	const runTests = async () => {
		if (dirty && !(await saveDraft())) return;
		const value = await run('tests', () => studioApi.runTests(agentId));
		if (value) {
			setReport(value);
			const refreshed = await studioApi.getAgent(agentId);
			apply(refreshed);
			toast[value.publishable ? 'success' : 'warning'](
				`Kiểm thử: ${value.passed}/${value.total} kịch bản đạt.`,
			);
		}
	};

	const publish = async () => {
		const value = await run('publish', () => studioApi.publish(agentId, publishNote));
		if (value) {
			apply(value);
			setPublishNote('');
			toast.success(`Đã phát hành phiên bản ${value.published_version}.`);
		}
	};

	const rollback = async (version: number) => {
		const value = await run('rollback', () => studioApi.rollback(agentId, version));
		if (value) {
			apply(value);
			toast.success(`Đã quay về nội dung phiên bản ${version}.`);
		}
	};

	const discard = async () => {
		const value = await run('discard', () => studioApi.discardDraft(agentId));
		if (value) apply(value);
	};

	const withdraw = async () => {
		const value = await run('withdraw', () => studioApi.withdraw(agentId));
		if (value) apply(value);
	};

	const remove = async () => {
		const done = await run('remove', async () => {
			await studioApi.remove(agentId);
			return true;
		});
		setConfirmRemove(false);
		if (done) {
			toast.success('Đã gỡ agent.');
			navigate('/workforce/agents');
		}
	};

	const retireMemory = async (memoryId: string) => {
		await run('memory', () => studioApi.retireMemory(agentId, memoryId));
		loadMemories();
	};

	const learnedRules = useMemo(() => spec?.rules.filter((rule) => rule.source === 'agent') ?? [], [spec]);

	if (!detail || !spec) {
		return (
			<div className="flex size-full items-center justify-center">
				<Spinner />
			</div>
		);
	}

	return (
		<div className="flex size-full min-h-0 gap-2 p-2">
			<main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[22px] bg-card shadow-panel">
				<header className="space-y-3 border-b p-5">
					<div className="flex flex-wrap items-center gap-3">
						<Button variant="ghost" size="icon-sm" onClick={() => navigate('/workforce/agents')} aria-label="Quay lại">
							<ArrowLeft />
						</Button>
						<h1 className="text-lg font-medium">{spec.name}</h1>
						<Badge variant={detail.lifecycle_state === 'published' ? 'default' : 'secondary'}>
							{STATUS_LABEL[detail.lifecycle_state]}
						</Badge>
						{detail.published_version > 0 && <Badge variant="outline">v{detail.published_version}</Badge>}
						{detail.changes.length > 0 && <Badge variant="outline">Có thay đổi chưa phát hành</Badge>}
						{dirty && <Badge variant="destructive">Chưa lưu</Badge>}
					</div>
					<div className="flex flex-wrap items-center gap-2">
						<Button size="sm" variant="outline" onClick={saveDraft} disabled={!dirty || busy !== null}>
							{busy === 'save' ? <Spinner /> : <Save />} Lưu nháp
						</Button>
						<Button size="sm" variant="outline" onClick={runTests} disabled={busy !== null || spec.tests.length === 0}>
							{busy === 'tests' ? <Spinner /> : <FlaskConical />} Chạy kiểm thử
						</Button>
						<Button size="sm" onClick={publish} disabled={busy !== null || dirty || !detail.can_publish}>
							{busy === 'publish' ? <Spinner /> : <Rocket />} Phát hành
						</Button>
						{detail.changes.length > 0 && detail.published_version > 0 && (
							<Button size="sm" variant="ghost" onClick={discard} disabled={busy !== null}>
								<Undo2 /> Huỷ thay đổi
							</Button>
						)}
						{detail.lifecycle_state === 'published' && (
							<Button size="sm" variant="ghost" onClick={withdraw} disabled={busy !== null}>
								Ngừng phát hành
							</Button>
						)}
						<Button
							size="sm"
							variant="ghost"
							className="text-destructive"
							onClick={() => setConfirmRemove(true)}
							disabled={busy !== null}
						>
							<Trash2 /> Gỡ agent
						</Button>
						{!detail.can_publish && detail.publish_blocker && (
							<span className="text-xs text-muted-foreground">{detail.publish_blocker}</span>
						)}
					</div>
					{detail.can_publish && (
						<Textarea
							value={publishNote}
							rows={1}
							placeholder="Ghi chú phiên bản (tuỳ chọn): thay đổi gì, vì sao"
							onChange={(event) => setPublishNote(event.target.value)}
						/>
					)}
				</header>

				<Tabs defaultValue="overview" className="min-h-0 flex-1 overflow-hidden p-4">
					<TabsList className="flex-wrap">
						<TabsTrigger value="overview">Tổng quan</TabsTrigger>
						<TabsTrigger value="rules">Hướng dẫn</TabsTrigger>
						<TabsTrigger value="tools">Công cụ</TabsTrigger>
						<TabsTrigger value="knowledge">Kiến thức</TabsTrigger>
						<TabsTrigger value="team">Phối hợp</TabsTrigger>
						<TabsTrigger value="tests">Kiểm thử</TabsTrigger>
						<TabsTrigger value="prompt">Prompt</TabsTrigger>
						<TabsTrigger value="versions">Phiên bản</TabsTrigger>
						<TabsTrigger value="memory">Bộ nhớ</TabsTrigger>
					</TabsList>
					<div className="min-h-0 flex-1 overflow-y-auto pr-1">
						<TabsContent value="overview" className="space-y-4">
							<Section title="Danh tính" hint="Leader đọc mô tả này để quyết định có mời agent vào ticket hay không.">
								<div className="grid gap-3 md:grid-cols-2">
									<TextField label="Tên agent" value={spec.name} onChange={(value) => update('name', value)} />
									<TextField label="Đối tượng phục vụ" value={spec.audience} onChange={(value) => update('audience', value)} placeholder="cư dân, khách du lịch..." />
									<TextField label="Giọng điệu" value={spec.tone} onChange={(value) => update('tone', value)} placeholder="thân thiện, ngắn gọn..." />
									<div className="space-y-1.5">
										<p className="text-xs text-muted-foreground">Ngôn ngữ trả lời</p>
										<div className="flex gap-1.5">
											{(['auto', 'vi', 'en'] as const).map((language) => (
												<Button
													key={language}
													size="xs"
													variant={spec.language === language ? 'default' : 'outline'}
													onClick={() => update('language', language)}
												>
													{{ auto: 'Theo khách', vi: 'Tiếng Việt', en: 'English' }[language]}
												</Button>
											))}
										</div>
									</div>
								</div>
								<TextField label="Mô tả ngắn" value={spec.description} onChange={(value) => update('description', value)} multiline rows={2} />
								<TextField label="Mục tiêu" value={spec.goal} onChange={(value) => update('goal', value)} multiline />
							</Section>
							<Section title="Phạm vi">
								<p className="text-xs text-muted-foreground">Agent xử lý</p>
								<StringListEditor items={spec.scope_in} onChange={(items) => update('scope_in', items)} placeholder="Việc agent làm" addLabel="Thêm việc" />
								<p className="text-xs text-muted-foreground">Ngoài phạm vi (agent từ chối lịch sự và chỉ đúng kênh)</p>
								<StringListEditor items={spec.scope_out} onChange={(items) => update('scope_out', items)} placeholder="Việc agent không làm" addLabel="Thêm mục" />
							</Section>
							<Section title="Vận hành">
								<div className="flex flex-wrap gap-6 text-sm">
									<label className="flex items-center gap-2">
										<Switch checked={spec.model_tier === 'strong'} onCheckedChange={(checked) => update('model_tier', checked ? 'strong' : 'standard')} />
										Dùng model mạnh (đắt hơn)
									</label>
									<label className="flex items-center gap-2">
										<Switch checked={spec.memory_enabled} onCheckedChange={(checked) => update('memory_enabled', checked)} />
										Ghi nhớ kinh nghiệm giữa các ticket
									</label>
									<label className="flex items-center gap-2">
										<Switch checked={spec.self_improve} onCheckedChange={(checked) => update('self_improve', checked)} />
										Cho agent tự cải tiến luật sau ca xử lý tốt
									</label>
								</div>
							</Section>
						</TabsContent>

						<TabsContent value="rules" className="space-y-4">
							<Section title="Luật" hint="Bắt buộc = agent phải tuân thủ; Nên làm = ưu tiên. Luật khoá thì agent không tự sửa được.">
								<RulesEditor rules={spec.rules} onChange={(rules) => update('rules', rules)} />
							</Section>
							<Section title="Khi nào chuyển người">
								<EscalationEditor items={spec.escalation} onChange={(items) => update('escalation', items)} />
							</Section>
							<Section title="Hướng dẫn thêm" hint="Văn bản tự do đặt sau các mục có cấu trúc.">
								<Textarea value={spec.extra_instructions} rows={4} onChange={(event) => update('extra_instructions', event.target.value)} />
							</Section>
						</TabsContent>

						<TabsContent value="tools" className="space-y-4">
							<Section title="Công cụ" hint="Tool chỉ đọc được chạy thật khi kiểm thử; tool ghi dữ liệu chỉ mô phỏng và cần khách xác nhận khi chạy thật.">
								<ToolsEditor tools={spec.tools} catalog={catalog} onChange={(tools) => update('tools', tools)} />
							</Section>
						</TabsContent>

						<TabsContent value="knowledge" className="space-y-4">
							<Section title="Kho kiến thức" hint="Agent tra cứu tài liệu ở đây thay vì nhồi vào prompt.">
								<KnowledgeEditor items={spec.knowledge} bases={bases} onChange={(items) => update('knowledge', items)} />
							</Section>
							<Section title="Skill" hint="Skill trong thư viện của bạn; được cài vào agent khi phát hành. Nhờ copilot thêm, ví dụ: dùng skill đọc ảnh khi cư dân gửi ảnh.">
								<div className="space-y-2">
									{spec.skills.map((skill) => (
										<div key={skill.skill_id} className="flex items-start gap-2 rounded-xl border border-border/70 p-2 text-sm">
											<div className="min-w-0 flex-1">
												<p className="font-medium">{skill.name || skill.skill_id}</p>
												{skill.use_when && <p className="text-xs text-muted-foreground">Dùng khi: {skill.use_when}</p>}
											</div>
											<Button
												size="xs"
												variant="ghost"
												onClick={() => update('skills', spec.skills.filter((item) => item.skill_id !== skill.skill_id))}
											>
												Bỏ
											</Button>
										</div>
									))}
									{spec.skills.length === 0 && <p className="text-xs text-muted-foreground">Chưa gắn skill nào.</p>}
								</div>
							</Section>
						</TabsContent>

						<TabsContent value="team" className="space-y-4">
							<Section title="Đồng đội cần hỏi">
								<CollaboratorsEditor items={spec.collaborates} onChange={(items) => update('collaborates', items)} />
							</Section>
							<Section title="Ví dụ hội thoại">
								<ExamplesEditor items={spec.examples} onChange={(items) => update('examples', items)} />
							</Section>
						</TabsContent>

						<TabsContent value="tests" className="space-y-4">
							<Section title="Kịch bản kiểm thử" hint="Cần ít nhất 3 kịch bản và 80% đạt trên đúng bản nháp này mới phát hành được.">
								{spec.tests.length < 3 && (
									<div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/50 p-3 text-xs">
										<span>
											Agent hiện có {spec.tests.length} kịch bản. Chưa đủ 3 kịch bản thì chưa phát hành được, và các luật agent tự học chỉ nằm ở bản nháp.
										</span>
										<Button
											size="xs"
											variant="outline"
											disabled={busy !== null}
											onClick={() =>
												sendCopilot(
													'Viết thêm kịch bản kiểm thử cho đủ ít nhất 3: một yêu cầu bình thường, một yêu cầu ngoài phạm vi, một trường hợp cần khách xác nhận hoặc chuyển người.',
												)
											}
										>
											<Sparkles /> Nhờ copilot viết kịch bản
										</Button>
									</div>
								)}
								<TestsEditor tests={spec.tests} onChange={(tests) => update('tests', tests)} />
							</Section>
							{report && (
								<Section title="Kết quả lần chạy gần nhất">
									<TestReportView report={report} />
								</Section>
							)}
						</TabsContent>

						<TabsContent value="prompt" className="space-y-4">
							<Section
								title="Tự viết prompt"
								hint="Bật để thay toàn bộ phần do form sinh ra bằng prompt của bạn. Luật agent tự học và chính sách bằng chứng của platform vẫn được gắn thêm."
								action={
									<Switch
										checked={spec.prompt_override !== null}
										onCheckedChange={(checked) => update(
												'prompt_override',
												checked
													? detail.rendered_prompt
															.split('\n\nWORKFORCE RUNTIME POLICY')[0]
															.split('\n\nLESSONS FROM PAST VERIFIED CASES')[0]
													: null,
											)}
									/>
								}
							>
								{spec.prompt_override !== null && (
									<Textarea value={spec.prompt_override} rows={14} onChange={(event) => update('prompt_override', event.target.value)} />
								)}
							</Section>
							<Section title="Prompt chạy thật của bản nháp đã lưu" hint="Đây là đúng nội dung model nhận (gồm chính sách của platform).">
								<pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg bg-muted/50 p-3 text-xs">{detail.rendered_prompt}</pre>
							</Section>
						</TabsContent>

						<TabsContent value="versions" className="space-y-4">
							<Section title="Thay đổi chưa phát hành">
								<ChangeList changes={detail.changes} />
							</Section>
							<Section title="Lịch sử phiên bản" action={<History className="size-4 text-muted-foreground" />}>
								<div className="space-y-2">
									{detail.versions.map((version) => (
										<div key={version.version} className="flex items-center gap-3 rounded-xl border border-border/70 p-3 text-sm">
											<Badge variant={version.version === detail.published_version ? 'default' : 'outline'}>v{version.version}</Badge>
											<div className="min-w-0 flex-1">
												<p className="truncate">{version.note || '—'}</p>
												<p className="text-xs text-muted-foreground">
													{AUTHOR_LABEL[version.author] ?? version.author} · {version.created_at ? new Date(version.created_at).toLocaleString('vi-VN') : ''}
													{version.evaluation?.score !== undefined ? ` · kiểm thử ${Math.round((version.evaluation.score ?? 0) * 100)}%` : ''}
												</p>
											</div>
											{version.version !== detail.published_version && (
												<Button size="sm" variant="outline" onClick={() => rollback(version.version)} disabled={busy !== null}>
													<RotateCcw /> Quay về
												</Button>
											)}
										</div>
									))}
									{detail.versions.length === 0 && <p className="text-xs text-muted-foreground">Chưa phát hành phiên bản nào.</p>}
								</div>
							</Section>
						</TabsContent>

						<TabsContent value="memory" className="space-y-4">
							<Section title="Luật agent tự học" hint="Sinh ra sau những ca được xác minh là xử lý tốt. Bạn có thể sửa, khoá hoặc xoá ở tab Hướng dẫn.">
								{learnedRules.length === 0 ? (
									<p className="text-xs text-muted-foreground">Chưa có.</p>
								) : (
									<ul className="space-y-1.5 text-sm">
										{learnedRules.map((rule) => (
											<li key={rule.id} className="flex items-start gap-2">
												<Sparkles className="mt-0.5 size-3.5 shrink-0 text-primary" />
												<span>{rule.text}</span>
												{rule.learned_from && <span className="text-xs text-muted-foreground">({rule.learned_from})</span>}
											</li>
										))}
									</ul>
								)}
							</Section>
							<Section title="Bộ nhớ kinh nghiệm" hint="Agent tự ghi và tự duyệt sau mỗi ticket; bản cũ bị thay thế chứ không bị xoá.">
								<div className="space-y-2">
									{memories.map((memory) => (
										<div key={memory.id} className={`flex items-start gap-3 rounded-xl border p-3 text-sm ${memory.status === 'active' ? 'border-border/70' : 'border-dashed opacity-60'}`}>
											<Badge variant="outline">{{ lesson: 'Bài học', fact: 'Sự kiện', preference: 'Sở thích' }[memory.kind]}</Badge>
											<div className="min-w-0 flex-1">
												<p>{memory.content}</p>
												<p className="text-xs text-muted-foreground">
													{memory.status === 'active' ? `Đã dùng ${memory.uses} lần` : memory.status === 'superseded' ? 'Đã được thay bằng bản mới' : 'Đã gỡ'}
													{memory.source_ticket ? ` · ticket ${memory.source_ticket.slice(0, 8)}` : ''}
												</p>
											</div>
											{memory.status === 'active' && (
												<Button size="sm" variant="ghost" onClick={() => retireMemory(memory.id)}>
													Gỡ
												</Button>
											)}
										</div>
									))}
									{memories.length === 0 && <p className="text-xs text-muted-foreground">Chưa có ký ức nào.</p>}
								</div>
							</Section>
						</TabsContent>
					</div>
				</Tabs>
			</main>
			<aside className="flex w-[380px] shrink-0 flex-col overflow-hidden rounded-[22px] bg-card shadow-panel">
				<CopilotPanel turns={turns} busy={busy === 'copilot'} onSend={sendCopilot} />
			</aside>
			<Dialog open={confirmRemove} onOpenChange={setConfirmRemove}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Gỡ agent {spec.name}?</DialogTitle>
						<DialogDescription>
							Agent, các phiên bản và phiên làm việc của nó bị xoá vĩnh viễn. Ticket đang mời agent này sẽ
							không còn thành viên này. Agent đang được tuyến đối tác dùng thì không gỡ được.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setConfirmRemove(false)} disabled={busy !== null}>
							Huỷ
						</Button>
						<Button variant="destructive" onClick={remove} disabled={busy !== null}>
							{busy === 'remove' ? <Spinner /> : <Trash2 />} Gỡ agent
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
