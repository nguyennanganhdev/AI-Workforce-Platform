import { Lock, Plus, Sparkles, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';

import type {
	AgentSpec,
	CatalogTool,
	KnowledgeBaseView,
	SpecCollaborator,
	SpecEscalation,
	SpecExample,
	SpecKnowledge,
	SpecRule,
	SpecTest,
	SpecTool,
} from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';

const newId = () =>
	typeof crypto !== 'undefined' && 'randomUUID' in crypto
		? crypto.randomUUID().replace(/-/g, '')
		: Math.random().toString(36).slice(2);

export type SpecUpdate = <K extends keyof AgentSpec>(key: K, value: AgentSpec[K]) => void;

export function Section({
	title,
	hint,
	children,
	action,
}: {
	title: string;
	hint?: string;
	children: ReactNode;
	action?: ReactNode;
}) {
	return (
		<section className="space-y-3 border-t border-border/70 pt-5 first:border-t-0 first:pt-0">
			<div className="flex items-start justify-between gap-3">
				<div>
					<h3 className="text-sm font-medium">{title}</h3>
					{hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
				</div>
				{action}
			</div>
			{children}
		</section>
	);
}

export function TextField({
	label,
	value,
	onChange,
	placeholder,
	multiline = false,
	rows = 3,
}: {
	label: string;
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
	multiline?: boolean;
	rows?: number;
}) {
	return (
		<div className="space-y-1.5">
			<Label className="text-xs text-muted-foreground">{label}</Label>
			{multiline ? (
				<Textarea
					value={value}
					rows={rows}
					placeholder={placeholder}
					onChange={(event) => onChange(event.target.value)}
				/>
			) : (
				<Input
					value={value}
					placeholder={placeholder}
					onChange={(event) => onChange(event.target.value)}
				/>
			)}
		</div>
	);
}

function RemoveButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
	return (
		<Button variant="ghost" size="icon-sm" onClick={onClick} disabled={disabled} aria-label="Xoá">
			<Trash2 />
		</Button>
	);
}

function AddButton({ onClick, label }: { onClick: () => void; label: string }) {
	return (
		<Button variant="outline" size="sm" onClick={onClick}>
			<Plus /> {label}
		</Button>
	);
}

export function StringListEditor({
	items,
	onChange,
	placeholder,
	addLabel,
}: {
	items: string[];
	onChange: (items: string[]) => void;
	placeholder: string;
	addLabel: string;
}) {
	return (
		<div className="space-y-2">
			{items.map((item, index) => (
				<div key={index} className="flex items-center gap-2">
					<Input
						value={item}
						placeholder={placeholder}
						onChange={(event) =>
							onChange(items.map((value, i) => (i === index ? event.target.value : value)))
						}
					/>
					<RemoveButton onClick={() => onChange(items.filter((_, i) => i !== index))} />
				</div>
			))}
			<AddButton label={addLabel} onClick={() => onChange([...items, ''])} />
		</div>
	);
}

const SOURCE_LABEL: Record<string, string> = {
	manager: 'BQL',
	builder: 'Builder',
	agent: 'Agent tự học',
	template: 'Mẫu',
	legacy: 'Có sẵn',
};

export function RulesEditor({
	rules,
	onChange,
}: {
	rules: SpecRule[];
	onChange: (rules: SpecRule[]) => void;
}) {
	const update = (index: number, patch: Partial<SpecRule>) =>
		onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
	return (
		<div className="space-y-2">
			{rules.map((rule, index) => (
				<div
					key={rule.id || index}
					className={`space-y-2 rounded-xl border p-3 ${rule.source === 'agent' ? 'border-primary/40 bg-primary/5' : 'border-border/70'}`}
				>
					<div className="flex items-start gap-2">
						<Textarea
							value={rule.text}
							rows={2}
							placeholder="Ví dụ: Không báo giá khi chưa có ảnh hiện trường"
							onChange={(event) => update(index, { text: event.target.value })}
						/>
						<RemoveButton onClick={() => onChange(rules.filter((_, i) => i !== index))} />
					</div>
					<div className="flex flex-wrap items-center gap-3 text-xs">
						<button
							type="button"
							className={`rounded-full border px-2 py-0.5 ${rule.level === 'must' ? 'border-primary bg-primary text-primary-foreground' : 'border-border'}`}
							onClick={() => update(index, { level: rule.level === 'must' ? 'should' : 'must' })}
						>
							{rule.level === 'must' ? 'Bắt buộc' : 'Nên làm'}
						</button>
						<Badge variant="outline">
							{rule.source === 'agent' && <Sparkles />}
							{SOURCE_LABEL[rule.source] ?? rule.source}
						</Badge>
						{rule.learned_from && (
							<span className="text-muted-foreground">từ {rule.learned_from}</span>
						)}
						<label className="ml-auto flex items-center gap-1.5 text-muted-foreground">
							<Lock className="size-3" /> Khoá (agent không được sửa)
							<Switch
								checked={rule.locked}
								onCheckedChange={(checked) => update(index, { locked: checked })}
							/>
						</label>
					</div>
				</div>
			))}
			<AddButton
				label="Thêm luật"
				onClick={() =>
					onChange([
						...rules,
						{ id: newId(), text: '', level: 'must', source: 'manager', locked: false, learned_from: '' },
					])
				}
			/>
		</div>
	);
}

export function EscalationEditor({
	items,
	onChange,
}: {
	items: SpecEscalation[];
	onChange: (items: SpecEscalation[]) => void;
}) {
	return (
		<div className="space-y-2">
			{items.map((item, index) => (
				<div key={item.id || index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
					<Input
						value={item.when}
						placeholder="Khi nào (có nguy cơ cháy nổ...)"
						onChange={(event) =>
							onChange(items.map((v, i) => (i === index ? { ...v, when: event.target.value } : v)))
						}
					/>
					<Input
						value={item.to}
						placeholder="Chuyển cho ai (bảo vệ, BQL...)"
						onChange={(event) =>
							onChange(items.map((v, i) => (i === index ? { ...v, to: event.target.value } : v)))
						}
					/>
					<RemoveButton onClick={() => onChange(items.filter((_, i) => i !== index))} />
				</div>
			))}
			<AddButton
				label="Thêm trường hợp chuyển người"
				onClick={() => onChange([...items, { id: newId(), when: '', to: '' }])}
			/>
		</div>
	);
}

export function ToolsEditor({
	tools,
	catalog,
	onChange,
}: {
	tools: SpecTool[];
	catalog: CatalogTool[];
	onChange: (tools: SpecTool[]) => void;
}) {
	const selected = new Set(tools.map((tool) => tool.tool_id));
	const available = catalog.filter((tool) => !selected.has(tool.tool_id));
	const update = (index: number, patch: Partial<SpecTool>) =>
		onChange(tools.map((tool, i) => (i === index ? { ...tool, ...patch } : tool)));
	return (
		<div className="space-y-3">
			{tools.map((tool, index) => (
				<div key={tool.tool_id} className="space-y-2 rounded-xl border border-border/70 p-3">
					<div className="flex items-center justify-between gap-2">
						<div>
							<p className="font-mono text-sm">{tool.tool_name}</p>
							<p className="text-xs text-muted-foreground">
								{tool.mcp_name || tool.mcp_id} ·{' '}
								{tool.read_only ? 'chỉ đọc' : 'có ghi dữ liệu'}
							</p>
						</div>
						<RemoveButton onClick={() => onChange(tools.filter((_, i) => i !== index))} />
					</div>
					<Input
						value={tool.use_when}
						placeholder="Dùng khi nào (ví dụ: cần phân loại sự cố)"
						onChange={(event) => update(index, { use_when: event.target.value })}
					/>
					<label className="flex items-center gap-2 text-xs text-muted-foreground">
						<Switch
							checked={tool.requires_consent}
							onCheckedChange={(checked) => update(index, { requires_consent: checked })}
						/>
						Cần khách xác nhận trước khi chạy
					</label>
				</div>
			))}
			{available.length > 0 ? (
				<div className="space-y-1">
					<Label className="text-xs text-muted-foreground">Thêm tool từ kho MCP</Label>
					<div className="flex flex-wrap gap-1.5">
						{available.map((tool) => (
							<Button
								key={tool.tool_id}
								variant="outline"
								size="xs"
								title={tool.description}
								onClick={() =>
									onChange([
										...tools,
										{
											tool_id: tool.tool_id,
											mcp_id: tool.mcp_id,
											mcp_name: tool.mcp_name,
											tool_name: tool.tool_name,
											use_when: '',
											requires_consent: !tool.read_only,
											read_only: tool.read_only,
										},
									])
								}
							>
								<Plus /> {tool.tool_name}
							</Button>
						))}
					</div>
				</div>
			) : (
				<p className="text-xs text-muted-foreground">
					Kho tool trống hoặc đã chọn hết. Thêm MCP ở trang MCP để có thêm tool.
				</p>
			)}
		</div>
	);
}

export function KnowledgeEditor({
	items,
	bases,
	onChange,
}: {
	items: SpecKnowledge[];
	bases: KnowledgeBaseView[];
	onChange: (items: SpecKnowledge[]) => void;
}) {
	const selected = new Set(items.map((item) => item.kb_id));
	return (
		<div className="space-y-3">
			{items.map((item, index) => (
				<div key={item.kb_id} className="flex items-center gap-2 rounded-xl border border-border/70 p-3">
					<div className="min-w-0 flex-1 space-y-1.5">
						<p className="text-sm font-medium">{item.name || item.kb_id}</p>
						<Input
							value={item.use_for}
							placeholder="Dùng cho việc gì (quy trình, bảng giá...)"
							onChange={(event) =>
								onChange(items.map((v, i) => (i === index ? { ...v, use_for: event.target.value } : v)))
							}
						/>
					</div>
					<RemoveButton onClick={() => onChange(items.filter((_, i) => i !== index))} />
				</div>
			))}
			<div className="flex flex-wrap gap-1.5">
				{bases
					.filter((base) => !selected.has(base.id))
					.map((base) => (
						<Button
							key={base.id}
							variant="outline"
							size="xs"
							onClick={() => onChange([...items, { kb_id: base.id, name: base.name, use_for: '' }])}
						>
							<Plus /> {base.name}
						</Button>
					))}
				{bases.length === 0 && (
					<p className="text-xs text-muted-foreground">
						Chưa có kho kiến thức. Tạo ở trang Knowledge rồi gắn vào agent.
					</p>
				)}
			</div>
		</div>
	);
}

export function CollaboratorsEditor({
	items,
	onChange,
}: {
	items: SpecCollaborator[];
	onChange: (items: SpecCollaborator[]) => void;
}) {
	return (
		<div className="space-y-2">
			{items.map((item, index) => (
				<div key={item.id || index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
					<Input
						value={item.capability}
						placeholder="Năng lực (tính chi phí, kỹ thuật...)"
						onChange={(event) =>
							onChange(items.map((v, i) => (i === index ? { ...v, capability: event.target.value } : v)))
						}
					/>
					<Input
						value={item.ask_when}
						placeholder="Hỏi khi nào"
						onChange={(event) =>
							onChange(items.map((v, i) => (i === index ? { ...v, ask_when: event.target.value } : v)))
						}
					/>
					<RemoveButton onClick={() => onChange(items.filter((_, i) => i !== index))} />
				</div>
			))}
			<AddButton
				label="Thêm đồng đội"
				onClick={() => onChange([...items, { id: newId(), capability: '', ask_when: '' }])}
			/>
		</div>
	);
}

export function ExamplesEditor({
	items,
	onChange,
}: {
	items: SpecExample[];
	onChange: (items: SpecExample[]) => void;
}) {
	return (
		<div className="space-y-2">
			{items.map((item, index) => (
				<div key={item.id || index} className="space-y-2 rounded-xl border border-border/70 p-3">
					<div className="flex gap-2">
						<Input
							value={item.user}
							placeholder="Khách nói..."
							onChange={(event) =>
								onChange(items.map((v, i) => (i === index ? { ...v, user: event.target.value } : v)))
							}
						/>
						<RemoveButton onClick={() => onChange(items.filter((_, i) => i !== index))} />
					</div>
					<Textarea
						value={item.agent}
						rows={2}
						placeholder="Agent nên trả lời / làm..."
						onChange={(event) =>
							onChange(items.map((v, i) => (i === index ? { ...v, agent: event.target.value } : v)))
						}
					/>
				</div>
			))}
			<AddButton
				label="Thêm ví dụ"
				onClick={() => onChange([...items, { id: newId(), user: '', agent: '' }])}
			/>
		</div>
	);
}

const splitList = (value: string) =>
	value
		.split(',')
		.map((item) => item.trim())
		.filter(Boolean);

export function TestsEditor({
	tests,
	onChange,
}: {
	tests: SpecTest[];
	onChange: (tests: SpecTest[]) => void;
}) {
	const update = (index: number, patch: Partial<SpecTest>) =>
		onChange(tests.map((test, i) => (i === index ? { ...test, ...patch } : test)));
	return (
		<div className="space-y-2">
			{tests.map((test, index) => (
				<div key={test.id || index} className="space-y-2 rounded-xl border border-border/70 p-3">
					<div className="flex gap-2">
						<Textarea
							value={test.scenario}
							rows={2}
							placeholder="Khách nói gì trong kịch bản"
							onChange={(event) => update(index, { scenario: event.target.value })}
						/>
						<RemoveButton onClick={() => onChange(tests.filter((_, i) => i !== index))} />
					</div>
					<Textarea
						value={test.expected}
						rows={2}
						placeholder="Hành vi mong đợi (agent phải làm/không được làm gì)"
						onChange={(event) => update(index, { expected: event.target.value })}
					/>
					<div className="grid gap-2 md:grid-cols-3">
						<Input
							value={test.must_include.join(', ')}
							placeholder="Phải có (cách nhau dấu phẩy)"
							onChange={(event) => update(index, { must_include: splitList(event.target.value) })}
						/>
						<Input
							value={test.must_not_include.join(', ')}
							placeholder="Không được có"
							onChange={(event) => update(index, { must_not_include: splitList(event.target.value) })}
						/>
						<Input
							value={test.expect_tool}
							placeholder="Tool phải gọi (tuỳ chọn)"
							onChange={(event) => update(index, { expect_tool: event.target.value })}
						/>
					</div>
				</div>
			))}
			<AddButton
				label="Thêm kịch bản kiểm thử"
				onClick={() =>
					onChange([
						...tests,
						{ id: newId(), scenario: '', expected: '', must_include: [], must_not_include: [], expect_tool: '' },
					])
				}
			/>
		</div>
	);
}
