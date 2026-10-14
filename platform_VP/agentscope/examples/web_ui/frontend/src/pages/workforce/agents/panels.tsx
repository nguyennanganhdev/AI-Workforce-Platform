import { CheckCircle2, CircleAlert, Send, Sparkles, Wrench } from 'lucide-react';
import { useState } from 'react';

import type { SpecChange, TestReport } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';

const FIELD_LABEL: Record<string, string> = {
	name: 'Tên',
	description: 'Mô tả',
	audience: 'Đối tượng',
	language: 'Ngôn ngữ',
	tone: 'Giọng điệu',
	goal: 'Mục tiêu',
	scope_in: 'Trong phạm vi',
	scope_out: 'Ngoài phạm vi',
	rules: 'Luật',
	escalation: 'Chuyển người',
	tools: 'Tool',
	knowledge: 'Kiến thức',
	collaborates: 'Đồng đội',
	examples: 'Ví dụ',
	tests: 'Kiểm thử',
	extra_instructions: 'Hướng dẫn thêm',
	prompt_override: 'Prompt tự viết',
	model_tier: 'Mức model',
	memory_enabled: 'Bộ nhớ',
	self_improve: 'Tự cải tiến',
};

const ACTION_LABEL = { added: 'Thêm', removed: 'Bỏ', changed: 'Sửa' } as const;

function describe(value: unknown): string {
	if (value === null || value === undefined || value === '') return '—';
	if (typeof value === 'string') return value;
	if (typeof value === 'boolean') return value ? 'bật' : 'tắt';
	if (Array.isArray(value)) return value.map(describe).join(', ');
	if (typeof value === 'object') {
		const item = value as Record<string, unknown>;
		return String(
			item.text ?? item.scenario ?? item.tool_name ?? item.name ?? item.capability ?? item.when ?? item.user ?? JSON.stringify(item),
		);
	}
	return String(value);
}

export function ChangeList({ changes }: { changes: SpecChange[] }) {
	if (changes.length === 0) {
		return <p className="text-xs text-muted-foreground">Không có thay đổi so với bản đang phát hành.</p>;
	}
	return (
		<ul className="space-y-1.5 text-xs">
			{changes.map((change, index) => (
				<li key={index} className="rounded-lg bg-muted/50 px-2.5 py-1.5">
					<span className="font-medium">
						{ACTION_LABEL[change.action]} {FIELD_LABEL[change.field] ?? change.field}:
					</span>{' '}
					{change.action === 'changed' && change.before !== null && change.before !== undefined ? (
						<>
							<span className="text-muted-foreground line-through">{describe(change.before)}</span> →{' '}
							{describe(change.after)}
						</>
					) : (
						describe(change.action === 'removed' ? change.before : change.after)
					)}
				</li>
			))}
		</ul>
	);
}

export interface CopilotTurn {
	user: string;
	reply?: string;
	questions?: string[];
	changes?: SpecChange[];
	error?: string;
}

export function CopilotPanel({
	turns,
	busy,
	onSend,
}: {
	turns: CopilotTurn[];
	busy: boolean;
	onSend: (message: string) => void;
}) {
	const [message, setMessage] = useState('');
	const send = () => {
		const text = message.trim();
		if (!text || busy) return;
		setMessage('');
		onSend(text);
	};
	return (
		<div className="flex h-full min-h-0 flex-col">
			<header className="border-b p-4">
				<div className="flex items-center gap-2">
					<Sparkles className="size-4 text-primary" />
					<h2 className="text-sm font-medium">Builder copilot</h2>
				</div>
				<p className="mt-1 text-xs text-muted-foreground">
					Nói điều bạn muốn đổi; copilot sửa đúng chỗ trong form và cho bạn xem trước khi phát hành.
				</p>
			</header>
			<div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
				{turns.length === 0 && (
					<div className="space-y-2 text-xs text-muted-foreground">
						<p>Ví dụ:</p>
						<p>“Thêm luật: không báo giá khi chưa có ảnh hiện trường.”</p>
						<p>“Giọng thân thiện hơn, xưng em – gọi anh/chị.”</p>
						<p>“Viết thêm 3 kịch bản kiểm thử cho trường hợp khẩn cấp.”</p>
					</div>
				)}
				{turns.map((turn, index) => (
					<div key={index} className="space-y-2">
						<div className="ml-6 rounded-2xl bg-primary px-3 py-2 text-sm text-primary-foreground">
							{turn.user}
						</div>
						{turn.error && <p className="text-xs text-destructive">{turn.error}</p>}
						{turn.reply && (
							<div className="mr-6 space-y-2 rounded-2xl bg-muted px-3 py-2 text-sm">
								<p>{turn.reply}</p>
								{turn.questions && turn.questions.length > 0 && (
									<ul className="list-disc space-y-1 pl-4 text-xs">
										{turn.questions.map((question) => (
											<li key={question}>{question}</li>
										))}
									</ul>
								)}
								{turn.changes && turn.changes.length > 0 && <ChangeList changes={turn.changes} />}
							</div>
						)}
					</div>
				))}
				{busy && (
					<div className="flex items-center gap-2 text-xs text-muted-foreground">
						<Spinner /> Copilot đang sửa bản nháp…
					</div>
				)}
			</div>
			<footer className="border-t p-3">
				<div className="flex items-end gap-2">
					<Textarea
						value={message}
						rows={2}
						placeholder="Bạn muốn agent thay đổi thế nào?"
						onChange={(event) => setMessage(event.target.value)}
						onKeyDown={(event) => {
							if (event.key === 'Enter' && !event.shiftKey) {
								event.preventDefault();
								send();
							}
						}}
					/>
					<Button size="icon" onClick={send} disabled={busy || !message.trim()} aria-label="Gửi">
						<Send />
					</Button>
				</div>
			</footer>
		</div>
	);
}

export function TestReportView({ report }: { report: TestReport }) {
	return (
		<div className="space-y-3">
			<div className="flex flex-wrap items-center gap-2 text-sm">
				<Badge variant={report.publishable ? 'default' : 'destructive'}>
					{report.errors
						? `Chưa chạy được ${report.errors}/${report.total} kịch bản`
						: `${report.passed}/${report.total} đạt (${Math.round(report.pass_rate * 100)}%)`}
				</Badge>
				<span className="text-xs text-muted-foreground">
					{new Date(report.ran_at).toLocaleString('vi-VN')} ·{' '}
					{report.errors
						? 'lỗi model, không phải lỗi của agent'
						: report.publishable
							? 'đủ điều kiện phát hành'
							: 'chưa đủ điều kiện phát hành'}
				</span>
			</div>
			{report.model_error && (
				<p className="rounded-lg border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
					{report.model_error}
				</p>
			)}
			{report.results.map((result) => (
				<div key={result.test_id} className="space-y-2 rounded-xl border border-border/70 p-3 text-sm">
					<div className="flex items-start gap-2">
						{result.passed ? (
							<CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
						) : (
							<CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
						)}
						<div className="min-w-0 space-y-1">
							<p className="font-medium">{result.scenario}</p>
							{result.expected && (
								<p className="text-xs text-muted-foreground">Mong đợi: {result.expected}</p>
							)}
						</div>
					</div>
					{result.tool_calls.length > 0 && (
						<div className="flex flex-wrap gap-1.5">
							{result.tool_calls.map((call, index) => (
								<Badge key={index} variant="outline">
									<Wrench /> {call.name} {call.executed ? '' : '(mô phỏng)'}
								</Badge>
							))}
						</div>
					)}
					<p className="whitespace-pre-wrap rounded-lg bg-muted/50 p-2 text-xs">
						{result.answer || '(không có câu trả lời)'}
					</p>
					{result.checks.map((check) => (
						<p key={check.name} className={`text-xs ${check.passed ? 'text-muted-foreground' : 'text-destructive'}`}>
							{check.passed ? '✓' : '✗'} {check.name}
						</p>
					))}
					{result.judge && (
						<p className={`text-xs ${result.judge.passed ? 'text-muted-foreground' : 'text-destructive'}`}>
							Người chấm (AI): {result.judge.reason}
						</p>
					)}
				</div>
			))}
		</div>
	);
}
