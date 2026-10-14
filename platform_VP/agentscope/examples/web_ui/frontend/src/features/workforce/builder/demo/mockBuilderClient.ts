import { canCreate, createAgents } from './model';
import type { DemoState, Scenario } from './model';

export type DemoAction =
	| { type: 'message'; text: string; scenario: Scenario }
	| { type: 'approve' }
	| { type: 'publish' };

// Local simulation only. A production adapter can implement this same boundary.
export async function mockBuilderClient(
	state: DemoState,
	action: DemoAction,
	signal: AbortSignal,
	fail = false,
): Promise<DemoState> {
	await new Promise<void>((resolve, reject) => {
		if (signal.aborted) {
			reject(new DOMException('Aborted', 'AbortError'));
			return;
		}
		const abort = () => {
			clearTimeout(timer);
			reject(new DOMException('Aborted', 'AbortError'));
		};
		const timer = setTimeout(() => {
			signal.removeEventListener('abort', abort);
			resolve();
		}, 850);
		signal.addEventListener('abort', abort, { once: true });
	});
	if (fail) throw new Error('Đây là lỗi giả lập. Dữ liệu của bạn được giữ nguyên; hãy thử lại.');
	const next = structuredClone(state);
	let reply: string;
	if (action.type === 'message') {
		if (!action.text.trim() || !['start', 'clarify'].includes(state.stage))
			throw new Error('Hãy hoàn thành bước hiện tại trước.');
		next.messages.push({ id: crypto.randomUUID(), role: 'user', text: action.text });
		if (state.stage === 'start') {
			next.scenario = action.scenario;
			next.stage = 'clarify';
			reply =
				'Mình đã nhận yêu cầu. Agent sẽ phục vụ ai và bạn muốn ưu tiên điều gì? Ví dụ: hỗ trợ cư dân bằng tiếng Việt, câu trả lời ngắn gọn và có nguồn tham khảo.';
		} else {
			next.stage = 'outline';
			next.agents = createAgents(state.scenario);
			reply = `Phương án demo gồm ${next.agents.length} agent. Bạn có thể xem vai trò ở phần Đề xuất và duyệt phương án để chỉnh cấu hình chi tiết. Phản hồi đang chạy theo kịch bản mẫu đã chọn.`;
		}
	} else if (action.type === 'approve') {
		if (state.stage !== 'outline') throw new Error('Chưa có phương án để duyệt.');
		next.stage = 'configure';
		reply =
			'Phương án đã được duyệt. Bạn có thể chỉnh tên, nhiệm vụ, hướng dẫn, công cụ và nguồn kiến thức trước khi tạo thử.';
	} else {
		if (state.stage !== 'configure' || !canCreate(state.agents))
			throw new Error('Hãy hoàn thiện cấu hình và xử lý thông tin còn thiếu.');
		next.stage = 'done';
		reply = `Đã hoàn tất mô phỏng tạo ${next.agents.length} agent. Cấu hình chỉ được lưu trong phiên demo này; chưa có agent nào được tạo trên hệ thống.`;
	}
	next.messages.push({ id: crypto.randomUUID(), role: 'builder', text: reply });
	return next;
}
