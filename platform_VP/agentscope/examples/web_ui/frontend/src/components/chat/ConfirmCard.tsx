import type { ToolCallBlock } from '@agentscope-ai/agentscope/message';

/** A pending action is answered through the normal chat composer. */
export function ConfirmCard({ toolCall }: {
	toolCall: ToolCallBlock;
	onUserConfirm: (confirm: boolean, rules?: ToolCallBlock['suggested_rules']) => Promise<void>;
}) {
	let details: Record<string, unknown> | null = null;
	try {
		const value = JSON.parse(toolCall.input);
		if (value && typeof value === 'object' && !Array.isArray(value)) details = value;
	} catch {
		// Preserve the original payload when it is not a JSON object.
	}
	const code = toolCall.id.slice(-8);
	const action = toolCall.name.split('__').at(-1)?.replaceAll('_', ' ') ?? toolCall.name;
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
			<p>Thao tác này chưa được thực hiện. Bạn hãy nhắn <strong>xác nhận {code}</strong> để thực hiện đúng thông tin trên, hoặc <strong>hủy {code}</strong> để đổi phương án.</p>
			<p className="text-muted-foreground">You can also reply “confirm {code}” or “cancel {code}” in chat.</p>
		</div>
	);
}
