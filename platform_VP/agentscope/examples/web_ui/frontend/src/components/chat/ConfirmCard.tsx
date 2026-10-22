import type { ToolCallBlock } from '@agentscope-ai/agentscope/message';
import { useState } from 'react';

import { agentApi } from '@/api/agent';
import { Button } from '@/components/ui/button';

/** A pending action is answered by an explicit, call-bound decision. */
export function ConfirmCard({ toolCall, onUserConfirm, agentId }: {
	toolCall: ToolCallBlock;
	onUserConfirm: (confirm: boolean, rules?: ToolCallBlock['suggested_rules']) => Promise<void>;
	/** The agent asking; with it, an MCP tool can be allowed for good. */
	agentId?: string | null;
}) {
	const [decision, setDecision] = useState<boolean | 'always' | null>(null);
	const canAlwaysAllow = Boolean(agentId) && toolCall.name.startsWith('mcp__');
	let details: Record<string, unknown> | null = null;
	try {
		const value = JSON.parse(toolCall.input);
		if (value && typeof value === 'object' && !Array.isArray(value)) details = value;
	} catch {
		// Preserve the original payload when it is not a JSON object.
	}
	const action = toolCall.name.split('__').at(-1)?.replaceAll('_', ' ') ?? toolCall.name;
	const decide = async (confirm: boolean) => {
		setDecision(confirm);
		try {
			await onUserConfirm(confirm);
		} catch {
			setDecision(null);
		}
	};
	// Save "run without asking" for this tool of this agent, then approve
	// this call; the setting can be undone in the agent's tool settings.
	const alwaysAllow = async () => {
		if (!agentId) return;
		setDecision('always');
		try {
			await agentApi.setToolPolicy(agentId, toolCall.name, 'auto');
			await onUserConfirm(true);
		} catch {
			setDecision(null);
		}
	};
	return (
		<div className="bg-muted ring ring-border rounded-2xl w-full px-5 py-4 space-y-3 text-sm">
			<p>Mình chuẩn bị thực hiện: <strong>{action}</strong>.</p>
			<div className="max-h-[200px] overflow-auto break-words">
				{details ? <dl className="space-y-1">
					{Object.entries(details).map(([key, value]) => <div key={key}>
						<dt className="inline font-medium">{key.replaceAll('_', ' ')}: </dt>
						<dd className="inline">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
					</div>)}
				</dl> : <p className="whitespace-pre-wrap">{toolCall.input}</p>}
			</div>
			<p>Thao tác này chưa được thực hiện. Vui lòng kiểm tra thông tin rồi chọn một phương án.</p>
			<div className="flex justify-end gap-2">
				<Button
					variant="outline"
					disabled={decision !== null}
					onClick={() => void decide(false)}
				>
					{decision === false ? 'Đang từ chối…' : 'Từ chối'}
				</Button>
				{canAlwaysAllow && (
					<Button
						variant="outline"
						disabled={decision !== null}
						title="Lần sau agent chạy tool này không cần hỏi. Đổi lại được trong phần Tool của agent."
						onClick={() => void alwaysAllow()}
					>
						{decision === 'always' ? 'Đang lưu…' : 'Luôn cho phép'}
					</Button>
				)}
				<Button
					disabled={decision !== null}
					onClick={() => void decide(true)}
				>
					{decision === true ? 'Đang xác nhận…' : 'Xác nhận'}
				</Button>
			</div>
		</div>
	);
}
