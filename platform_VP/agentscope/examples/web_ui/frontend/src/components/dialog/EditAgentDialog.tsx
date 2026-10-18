import {
	ChevronDown,
	ChevronRight,
	CircleAlert,
	Database,
	Loader2,
	Save,
	Wrench,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { workforceApi } from '@/api';
import type { AgentToolSettings, AgentView, ContextConfig, InviteConfig, ReActConfig } from '@/api';
import { defaultAgentFormValues } from '@/components/form/agent-form-utils';
import {
	AgentFormFields,
	type AgentFormValues,
	type AgentSection,
} from '@/components/form/AgentFormFields';
import type { SchemaFormValue } from '@/components/form/SchemaForm';
import { Alert, AlertDescription } from '@/components/ui/alert.tsx';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogDescription,
} from '@/components/ui/dialog';
import { useAgents } from '@/hooks/useAgents';
import { useAgentSchema } from '@/hooks/useAgentSchema';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	agent: AgentView;
	onUpdated?: () => void;
}

export function EditAgentDialog({ open, onOpenChange, agent, onUpdated }: Props) {
	const { update } = useAgents();
	const { t } = useTranslation();
	const { schema } = useAgentSchema();
	const [submitting, setSubmitting] = useState(false);
	const [values, setValues] = useState<AgentFormValues | null>(null);
	const [errorMsg, setErrorMsg] = useState('');
	const [toolSettings, setToolSettings] = useState<AgentToolSettings | null>(null);
	const [selectedToolIds, setSelectedToolIds] = useState<Set<string>>(new Set());
	const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useState<Set<string>>(
		new Set(),
	);
	const [openMcps, setOpenMcps] = useState<Set<string>>(new Set());
	const [toolsLoading, setToolsLoading] = useState(false);
	const builderManaged = agent.data.execution_mode != null;

	useEffect(() => {
		if (!open || !schema) {
			if (!open) {
				setValues(null);
				setErrorMsg('');
			}
			return;
		}
		// Start from schema defaults, then overlay the existing agent's data so
		// any unset fields fall back to defaults rather than empty.
		const base = defaultAgentFormValues(schema);
		const d = agent.data;
		setValues({
			identity: {
				...base.identity,
				name: d.name,
				system_prompt: d.system_prompt,
			},
			context_config: { ...base.context_config, ...(d.context_config ?? {}) },
			react_config: { ...base.react_config, ...(d.react_config ?? {}) },
			invite_config: { ...base.invite_config, ...(d.invite_config ?? {}) },
		});
		setErrorMsg('');
	}, [open, schema, agent]);

	useEffect(() => {
		if (!open || !builderManaged) {
			setToolSettings(null);
			setSelectedToolIds(new Set());
			setSelectedKnowledgeBaseIds(new Set());
			setOpenMcps(new Set());
			setToolsLoading(false);
			return;
		}
		let active = true;
		setToolsLoading(true);
		workforceApi
			.getAgentTools(agent.id)
			.then((settings) => {
				if (!active) return;
				setToolSettings(settings);
				setSelectedToolIds(new Set(settings.selected_tool_ids));
				setSelectedKnowledgeBaseIds(new Set(settings.selected_knowledge_base_ids));
				setErrorMsg('');
			})
			.catch((error) => {
				if (active) setErrorMsg(formatApiErrorForAlert(error));
			})
			.finally(() => {
				if (active) setToolsLoading(false);
			});
		return () => {
			active = false;
		};
	}, [open, builderManaged, agent.id]);

	const handleChange = (section: AgentSection, key: string, value: SchemaFormValue) => {
		setErrorMsg('');
		setValues((prev) =>
			prev ? { ...prev, [section]: { ...prev[section], [key]: value } } : prev,
		);
	};

	const handleSubmit = async () => {
		if (!values) return;
		const name = (values.identity.name as string | undefined)?.trim();
		if (!name) return;
		setErrorMsg('');
		setSubmitting(true);
		try {
			if (builderManaged && toolSettings) {
				await workforceApi.updateAgentTools(
					agent.id,
					[...selectedToolIds],
					[...selectedKnowledgeBaseIds],
				);
			}
			await update(
				agent.id,
				{
					name,
					system_prompt: values.identity.system_prompt as string | undefined,
					context_config: values.context_config as unknown as ContextConfig,
					react_config: values.react_config as unknown as ReActConfig,
					invite_config: values.invite_config as unknown as InviteConfig,
				},
				{ silent: true },
			);
			onOpenChange(false);
			onUpdated?.();
		} catch (e) {
			setErrorMsg(formatApiErrorForAlert(e));
		} finally {
			setSubmitting(false);
		}
	};

	const name = (values?.identity.name as string | undefined)?.trim() ?? '';
	const nameValid = !!name;
	const toolsReady = !builderManaged || (!toolsLoading && toolSettings !== null);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[680px] !max-w-[calc(100vw-2rem)]">
				<DialogHeader className="flex-row items-center gap-3 pr-8">
					<ClayAvatar id={agent.id} label={name || agent.data.name} size={44} />
					<div className="flex min-w-0 flex-col gap-1">
						<DialogTitle>{t('dialog-agent-edit.title')}</DialogTitle>
						<DialogDescription>{t('dialog-agent-edit.description')}</DialogDescription>
					</div>
				</DialogHeader>
				<div className="no-scrollbar -mx-6 max-h-[75vh] overflow-y-auto px-6">
					{schema && values ? (
						<AgentFormFields schema={schema} values={values} onChange={handleChange} />
					) : (
						<p className="text-muted-foreground text-sm">{t('common.loading')}</p>
					)}
					{builderManaged && (
						<section className="mt-6 border-t pt-5">
							<div className="mb-3 flex items-start gap-2">
								<Wrench className="mt-0.5 size-4 text-primary" />
								<div>
									<h3 className="text-sm font-medium">Tool của MCP</h3>
									<p className="text-xs text-muted-foreground">
										Mở từng MCP để chọn chính xác những tool agent được phép sử
										dụng.
									</p>
								</div>
							</div>
							{toolsLoading ? (
								<div className="flex items-center gap-2 rounded-lg border p-3 text-sm text-muted-foreground">
									<Loader2 className="size-4 animate-spin" /> Đang tải danh sách
									MCP…
								</div>
							) : toolSettings?.mcps.length ? (
								<div className="space-y-2">
									{toolSettings.mcps.map((mcp) => {
										const expanded = openMcps.has(mcp.mcp_id);
										const selectedCount = mcp.tools.filter((tool) =>
											selectedToolIds.has(tool.id),
										).length;
										return (
											<Collapsible
												key={mcp.mcp_id}
												open={expanded}
												onOpenChange={(next) =>
													setOpenMcps((current) => {
														const copy = new Set(current);
														if (next) copy.add(mcp.mcp_id);
														else copy.delete(mcp.mcp_id);
														return copy;
													})
												}
												className="overflow-hidden rounded-lg border"
											>
												<CollapsibleTrigger asChild>
													<button
														type="button"
														className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-muted/50"
													>
														{expanded ? (
															<ChevronDown className="size-4" />
														) : (
															<ChevronRight className="size-4" />
														)}
														<span className="flex-1 font-medium">
															{mcp.mcp_name}
														</span>
														<span className="text-xs text-muted-foreground">
															{selectedCount}/{mcp.tools.length} tool
														</span>
													</button>
												</CollapsibleTrigger>
												<CollapsibleContent className="border-t bg-muted/15 p-2">
													<div className="space-y-1">
														{mcp.tools.map((tool) => (
															<label
																key={tool.id}
																className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-background"
															>
																<Checkbox
																	checked={selectedToolIds.has(
																		tool.id,
																	)}
																	onCheckedChange={(checked) =>
																		setSelectedToolIds(
																			(current) => {
																				const copy =
																					new Set(
																						current,
																					);
																				if (
																					checked === true
																				)
																					copy.add(
																						tool.id,
																					);
																				else
																					copy.delete(
																						tool.id,
																					);
																				return copy;
																			},
																		)
																	}
																	className="mt-0.5"
																/>
																<span className="min-w-0">
																	<span className="block font-mono text-xs font-medium">
																		{tool.tool_name}
																	</span>
																	{tool.description && (
																		<span className="mt-0.5 block text-xs text-muted-foreground">
																			{tool.description}
																		</span>
																	)}
																</span>
															</label>
														))}
													</div>
												</CollapsibleContent>
											</Collapsible>
										);
									})}
								</div>
							) : (
								<p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
									Chưa có MCP đang bật hoặc MCP chưa công bố tool nào.
								</p>
							)}
							<div className="mb-3 mt-6 flex items-start gap-2 border-t pt-5">
								<Database className="mt-0.5 size-4 text-primary" />
								<div>
									<h3 className="text-sm font-medium">Knowledge Base mặc định</h3>
									<p className="text-xs text-muted-foreground">
										Các KB này được gắn vào mọi session mới của agent ở chế độ
										agentic.
									</p>
								</div>
							</div>
							{toolsLoading ? (
								<div className="flex items-center gap-2 rounded-lg border p-3 text-sm text-muted-foreground">
									<Loader2 className="size-4 animate-spin" /> Đang tải Knowledge
									Base…
								</div>
							) : toolSettings?.knowledge_bases.length ? (
								<div className="max-h-64 space-y-1 overflow-y-auto rounded-lg border p-2">
									{toolSettings.knowledge_bases.map((knowledge) => (
										<label
											key={knowledge.id}
											className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-muted/50"
										>
											<Checkbox
												checked={selectedKnowledgeBaseIds.has(knowledge.id)}
												onCheckedChange={(checked) =>
													setSelectedKnowledgeBaseIds((current) => {
														const copy = new Set(current);
														if (checked === true)
															copy.add(knowledge.id);
														else copy.delete(knowledge.id);
														return copy;
													})
												}
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
								<p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
									Chưa có Knowledge Base nào để gắn cho agent.
								</p>
							)}
						</section>
					)}
				</div>
				{errorMsg && (
					<Alert variant="destructive">
						<CircleAlert />
						<AlertDescription className="whitespace-pre-wrap">
							{errorMsg}
						</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button
						variant="ghost"
						onClick={() => onOpenChange(false)}
						disabled={submitting}
					>
						{t('common.cancel')}
					</Button>
					<Button
						onClick={handleSubmit}
						disabled={!nameValid || submitting || !schema || !values || !toolsReady}
					>
						{submitting ? <Loader2 className="animate-spin" /> : <Save />}
						{submitting ? t('common.saving') : t('dialog-agent-edit.submit')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
