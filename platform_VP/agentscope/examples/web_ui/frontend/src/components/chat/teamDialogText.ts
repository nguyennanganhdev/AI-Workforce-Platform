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
	if (/CaseSay|CaseFinalize/.test(raw) && /không có lượt|không có.*đang mở|dừng retry|không gửi|kết thúc/i.test(raw)) {
		return 'Đã lưu thông tin để tiếp tục ở lượt trao đổi tiếp theo.';
	}
	if (/WORKER_RUN_FAILED|evidence gate rejected/i.test(raw)) {
		return 'Agent chưa hoàn tất xác minh. Leader cần kiểm tra báo cáo trước khi trả lời.';
	}
	if (/context.*budget|ngân sách context/i.test(raw)) {
		return 'Lượt xử lý trước bị gián đoạn do hội thoại quá dài. Bằng chứng của phiếu vẫn được lưu.';
	}
	const eventStatus = /^\(Hệ thống\)\s*Sự kiện /.test(raw)
		? /\(trạng thái ([^)]+)\)/.exec(raw)?.[1]
		: undefined;
	if (eventStatus) {
		const labels: Record<string, string> = {
			offered: 'Đã mời nhân viên nhận việc.', accepted: 'Nhân viên đã nhận việc.',
			en_route: 'Nhân viên đang di chuyển.', arrived: 'Nhân viên đã đến.',
			in_progress: 'Nhân viên đang xử lý.', quote_ready: 'Báo giá đã sẵn sàng, đang chờ cư dân duyệt.',
			result_published: 'Nhân viên đã gửi kết quả, đang chờ cư dân xác nhận.',
			resident_confirmed: 'Cư dân đã xác nhận kết quả.', closed: 'Phiếu đã hoàn tất.',
		};
		if (labels[eventStatus]) return labels[eventStatus];
	}
	return raw
		.replace(/<team-message[^>]*>/g, '')
		.replace(/<\/team-message>/g, '')
		.split('\n')
		.filter((line) => !/^\s*(handoff_id|task_id|reference_event_ids)=/.test(line))
		.join('\n')
		.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, '')
		.replace(/\b[0-9a-f]{32,64}\b/gi, '')
		.replace(/@[0-9a-f]{6,}\b/gi, '')
		.replace(/\bE\d+\b[:,]?\s*/g, '')
		.replace(/\b(ticket_id|workflow_id|operation_id|approval_id)\s*[:=]\s*[,.;]?/g, '')
		.trim();
}

export function toolLabel(name: string): string {
	const labels: Record<string, string> = {
		vh_ticket_get: 'Kiểm tra tiến độ phiếu', vh_staff_list: 'Tra nhân viên phù hợp',
		vh_knowledge_search: 'Tra hướng dẫn nghiệp vụ', vh_work_order_dispatch: 'Điều phối nhân viên',
		vh_work_order_reschedule: 'Cập nhật lịch hẹn', vh_ticket_add_note: 'Ghi nhận thông tin',
		vh_ticket_cancel: 'Hủy yêu cầu', CaseEvidence: 'Đọc lại bằng chứng',
	};
	return labels[name.split('__').at(-1) ?? name] ?? 'Xác minh thông tin';
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
