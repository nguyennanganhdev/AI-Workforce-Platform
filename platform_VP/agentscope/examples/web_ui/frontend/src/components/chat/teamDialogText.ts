/** Text helpers of the room conversation cards (see TeamDialog.tsx). */

/** Tool calls that are a message to someone, not work: shown as cards. */
export const DIALOG_TOOLS = new Set(['AgentInvite', 'TeamSay', 'CaseSay', 'CaseFinalize']);

/** An agent's name without its room handle (`KyThuat@7d00a7e0`). */
export function cleanName(name: string | undefined | null): string {
	return (name ?? '').replace(/@[0-9a-f]{6,}$/, '').trim();
}

export const KIND_LABEL: Record<string, string> = {
	assign: 'Giao việc',
	handoff: 'Giao việc',
	result: 'Báo kết quả',
	answer: 'Trả lời',
	question: 'Hỏi',
	review: 'Phản hồi',
	progress: 'Tiến độ',
	error: 'Báo lỗi',
	conflict: 'Mâu thuẫn',
	need_customer_info: 'Cần hỏi người dùng',
	ask_customer: 'Hỏi người dùng',
	requires_user_input: 'Cần người dùng',
	user_input_proposal: 'Đề xuất hỏi người dùng',
	customer: 'Người dùng',
	reply: 'Gửi người dùng',
	tool: 'Tra cứu / thao tác',
	partner_event: 'Sự kiện đối tác',
};

/** Strip the runtime envelope of a team message: tags, handoff/task ids. */
export function teamMessageText(raw: string): string {
	return raw
		.replace(/<team-message[^>]*>/g, '')
		.replace(/<\/team-message>/g, '')
		.split('\n')
		.filter((line) => !/^\s*(handoff_id|task_id|reference_event_ids)=/.test(line))
		.join('\n')
		.trim();
}

/** `field: value` lines of a structured hand-over (partner ticket). */
export function parseHandover(text: string): { shown: [string, string][]; hidden: string[] } | null {
	const lines = text.split('\n').map((line) => line.trim()).filter(Boolean);
	const fields: [string, string][] = [];
	const hidden: string[] = [];
	let machine = 0;
	for (const line of lines) {
		const match = /^([^:]{1,40}):\s*(.+)$/.exec(line);
		if (!match) {
			hidden.push(line);
			continue;
		}
		// snake_case keys are for agents and systems, not for people.
		if (/^[a-z][a-z0-9_]*$/.test(match[1])) {
			machine += 1;
			hidden.push(line);
		} else fields.push([match[1], match[2]]);
	}
	return machine > 0 && fields.length >= 3 ? { shown: fields, hidden } : null;
}

/** The sender and kind of a team hint (its JSON source), or null. */
export function teamHintSource(source: string | null | undefined): { sender: string; kind?: string } | null {
	if (!source) return null;
	try {
		const parsed = JSON.parse(source) as { label?: string; sublabel?: string; kind?: string };
		return parsed.label === 'team' ? { sender: parsed.sublabel ?? '', kind: parsed.kind } : null;
	} catch {
		return null;
	}
}
