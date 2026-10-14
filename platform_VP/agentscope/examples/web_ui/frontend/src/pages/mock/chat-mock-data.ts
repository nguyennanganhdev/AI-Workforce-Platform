/**
 * Scripted conversations for the mock chat screen. Nothing here reaches a
 * backend.
 *
 * Each script replays one path through the Workforce design in
 * `docs/workforce/KE_HOACH_TRIEN_KHAI.md`, event by event: how a request is
 * routed to the right manager scope (2.6), which agents the Leader picks
 * (2.3, 2.4), what each agent thinks and which tool it calls, and the
 * `workflow_state` / `next_action` the turn ends on (2.7, 17.2). The figures
 * and identifiers are the plan's own fixtures (15.2), not invented ones.
 */
import type { ApprovalView } from '@/features/workforce/approvals';
import type { NextAction, WorkflowState } from '@/features/workforce/shared/contracts/workforce-v1';

export type MockAgentId =
	'leader' | 'planner' | 'hotel' | 'car' | 'calculator' | 'technical' | 'builder';

export interface MockAgent {
	/** Also picks the sticker: see `portraitFor` in `ui/clay-portrait.tsx`. */
	name: string;
	/** One line on what it is for, shown where the roster of a session is listed. */
	role: string;
}

export const MOCK_AGENTS: Record<MockAgentId, MockAgent> = {
	leader: { name: 'Leader', role: 'Điều phối, chọn agent cho từng yêu cầu' },
	planner: { name: 'Agent Lập kế hoạch', role: 'Hỏi thông tin còn thiếu, trình phương án' },
	hotel: { name: 'Agent Khách sạn', role: 'Tìm, tư vấn và đặt khách sạn' },
	car: { name: 'Agent Xe', role: 'Tìm và đặt xe' },
	calculator: { name: 'Agent Tính chi phí', role: 'Tính tổng chi phí bằng công cụ xác định' },
	technical: { name: 'Agent Kỹ thuật', role: 'Tiếp nhận và theo dõi sửa chữa' },
	builder: { name: 'Builder', role: 'Tạo và nâng cấp agent qua trò chuyện' },
};

interface EventBase {
	id: string;
	/**
	 * Lines for the collapsed "Chi tiết kỹ thuật": the identifiers and state
	 * names behind the plain-language line above them.
	 */
	detail?: string[];
}

/** Something a person said: the resident, through the partner backend, or the manager. */
export interface UserEvent extends EventBase {
	kind: 'user';
	sender: string;
	text: string;
}

/** One line of the activity log: routing, an agent joining, a hand-off, a provider event. */
export interface StepEvent extends EventBase {
	kind: 'step';
	/** Who did it. Absent for what the platform itself did. */
	agent?: MockAgentId;
	/** Agents this step brought into the session. */
	joins?: MockAgentId[];
	/** `**bold**` marks names. */
	text: string;
}

/** An agent reasoning before it acts. */
export interface ThinkingEvent extends EventBase {
	kind: 'thinking';
	agent: MockAgentId;
	seconds: number;
	text: string;
}

export interface ToolEvent extends EventBase {
	kind: 'tool';
	agent: MockAgentId;
	/** The tool's name in plain Vietnamese. */
	label: string;
	/** A write is a side effect; a read is not. */
	effect: 'read' | 'write';
	input: string;
	/** One line, shown without opening the call. */
	summary: string;
	result: string;
}

/** An agent's answer. */
export interface AgentEvent extends EventBase {
	kind: 'agent';
	agent: MockAgentId;
	/** Markdown. */
	text: string;
}

/** Where a turn leaves the workflow, and what the caller is expected to do next. */
export interface StateEvent extends EventBase {
	kind: 'state';
	state: WorkflowState;
	nextAction: NextAction;
}

/**
 * A point where the script stops until somebody acts. What follows it in the
 * script is what that action leads to.
 */
export type GateEvent = EventBase &
	(
		| {
				kind: 'gate';
				/** The person replies; the next event is their message. */
				action: 'reply';
				label: string;
		  }
		| {
				kind: 'gate';
				/** The provider's backend posts an event; nobody types anything. */
				action: 'provider';
				label: string;
		  }
		| {
				kind: 'gate';
				/** Consent for a side effect. */
				action: 'approval';
				approval: Omit<ApprovalView, 'expires_at'>;
				/** Played instead of the rest of the script when the person refuses. */
				rejected: MockEvent[];
		  }
	);

export type MockEvent =
	UserEvent | StepEvent | ThinkingEvent | ToolEvent | AgentEvent | StateEvent | GateEvent;

export interface MockConversation {
	id: string;
	/** Also picks the roster sticker. */
	name: string;
	/** Whose request it is, in the reader's words. */
	subtitle: string;
	/** The person on the other end, for the list of who is taking part. */
	requester: { name: string; note: string };
	lastMessageAt: string;
	pinned?: boolean;
	events: MockEvent[];
}

const RESIDENT = 'Cư dân căn S1-0205';
const MANAGER = 'Bạn';
const RESIDENT_REQUESTER = { name: RESIDENT, note: 'Gửi yêu cầu qua Vinhomes' };

/** 2.6.4: authenticate, resolve one route, pin the scope, bind the ticket — before any model runs. */
function intake(id: string, ticket: 'A' | 'B' | 'C'): StepEvent {
	return {
		id,
		kind: 'step',
		text: 'Tiếp nhận yêu cầu từ **Vinhomes**, xác định đúng ban quản lý **Ocean Park 1** và mở một phiên xử lý riêng',
		detail: [
			'POST /workforce/v1/partner/requests, command_type=start_workflow',
			'Route BQL-OP1-A → vinhomes / ocean-park-1 / manager-A (khóa trước khi gọi model)',
			`TICKET-${ticket} / CHAT-${ticket} → workflow-${ticket} / conversation-${ticket} / group-${ticket}`,
			'Đã lưu yêu cầu trước khi chạy, workflow_state=accepted',
		],
	};
}

/** External-tracking (17.1 C, cases 56–58, 71): a repair job that outlives the turn. */
const REPAIR: MockConversation = {
	id: 'ticket-a',
	name: 'Sửa ống nước bị vỡ',
	subtitle: 'Căn S1-0205, Ocean Park 1',
	requester: RESIDENT_REQUESTER,
	lastMessageAt: '09:12',
	pinned: true,
	events: [
		{
			id: 'a-1',
			kind: 'user',
			sender: RESIDENT,
			text: 'Hãy gọi thợ đến sửa ống nước nhà tôi bị vỡ.',
		},
		intake('a-2', 'A'),
		{
			id: 'a-3',
			kind: 'thinking',
			agent: 'leader',
			seconds: 3,
			text: 'Yêu cầu là sự cố ống nước vỡ tại căn hộ, thuộc nhóm kỹ thuật điện nước. Thư viện của ban quản lý này có Lập kế hoạch, Khách sạn, Xe, Tính chi phí và Kỹ thuật. Chỉ Agent Kỹ thuật có công cụ tạo yêu cầu sửa chữa. Không cần các agent du lịch vì không có nhu cầu lập kế hoạch hay lưu trú.',
		},
		{
			id: 'a-4',
			kind: 'step',
			agent: 'leader',
			joins: ['technical'],
			text: '**Leader** thêm **Agent Kỹ thuật** vào phiên vì sự cố thuộc nhóm điện nước',
			detail: [
				'Run: created → planning → running',
				'group.member_added, Technical v2 (ghim phiên bản cho phiên này)',
				'workflow_state=active',
			],
		},
		{
			id: 'a-5',
			kind: 'thinking',
			agent: 'technical',
			seconds: 4,
			text: 'Cư dân đã nêu rõ sự cố và căn hộ nên không cần hỏi thêm. Việc cần làm là tạo yêu cầu sửa chữa cho căn S1-0205. Sau khi tạo, công việc còn tiếp diễn ở phía nhà cung cấp, nên phải theo dõi tiếp chứ chưa thể đóng yêu cầu.',
		},
		{
			id: 'a-6',
			kind: 'tool',
			agent: 'technical',
			label: 'Tạo yêu cầu sửa chữa',
			effect: 'write',
			input: 'Căn hộ: S1-0205\nSự cố: ống nước bị vỡ',
			summary: 'Đã tạo việc, thợ Nguyễn Văn A nhận',
			result: 'Mã việc: JOB-7781\nTrạng thái: đã phân công\nThợ: Nguyễn Văn A',
			detail: [
				'create_repair_job (MCP), Tool call: proposed → executing → succeeded',
				'Ghi operation và khóa chống trùng trước khi gọi, nên thử lại không tạo việc thứ hai',
				'external_job_id=JOB-7781 gắn với workflow-A',
			],
		},
		{
			id: 'a-7',
			kind: 'agent',
			agent: 'technical',
			text: 'Đã gọi thợ **Nguyễn Văn A** đến sửa ống nước cho căn S1-0205. Tôi sẽ báo ngay khi thợ lên đường.',
		},
		{
			id: 'a-8',
			kind: 'state',
			state: 'waiting_external_event',
			nextAction: 'watch_events',
			detail: [
				'HTTP 200 trên chính POST đó, request_status=completed',
				'Phiên lưu checkpoint rồi nghỉ: không gọi model, không giữ worker trong lúc chờ',
			],
		},
		{
			id: 'a-9',
			kind: 'gate',
			action: 'provider',
			label: 'Nhà cung cấp báo thợ đang trên đường',
		},
		{
			id: 'a-10',
			kind: 'step',
			text: 'Nhà cung cấp báo thợ **đang trên đường**, sự kiện được nối vào đúng phiên này',
			detail: [
				'POST provider event, event_type=on_the_way, external_job_id=JOB-7781, provider_version=2',
				'Resolve từ operation đã lưu → workflow-A; không tạo agent hay phiên mới',
				'workflow_state: waiting_external_event → active',
			],
		},
		{
			id: 'a-11',
			kind: 'thinking',
			agent: 'leader',
			seconds: 2,
			text: 'Sự kiện thuộc việc JOB-7781 của phiên này. Chỉ cần Agent Kỹ thuật báo cho cư dân. Không gọi lại công cụ tạo việc.',
		},
		{
			id: 'a-12',
			kind: 'agent',
			agent: 'technical',
			text: 'Thợ Nguyễn Văn A đang trên đường đến căn S1-0205.',
		},
		{
			id: 'a-13',
			kind: 'state',
			state: 'waiting_external_event',
			nextAction: 'watch_events',
			detail: ['Cập nhật được gửi qua SSE, cùng event_id với lịch sử để không trùng tin'],
		},
		{
			id: 'a-14',
			kind: 'gate',
			action: 'provider',
			label: 'Nhà cung cấp báo đã sửa xong',
		},
		{
			id: 'a-15',
			kind: 'step',
			text: 'Nhà cung cấp báo **đã sửa xong**',
			detail: [
				'POST provider event, event_type=completed, provider_version=3',
				'Việc đã kết thúc ở phía nhà cung cấp; phiên vẫn mở chờ cư dân xác nhận',
			],
		},
		{
			id: 'a-16',
			kind: 'agent',
			agent: 'technical',
			text: 'Thợ báo đã sửa xong ống nước. Anh/chị kiểm tra giúp và xác nhận để tôi đóng yêu cầu.',
		},
		{
			id: 'a-17',
			kind: 'state',
			state: 'awaiting_confirmation',
			nextAction: 'confirm_close',
		},
		{
			id: 'a-18',
			kind: 'gate',
			action: 'reply',
			label: 'Đã sửa xong, cảm ơn.',
		},
		{ id: 'a-19', kind: 'user', sender: RESIDENT, text: 'Đã sửa xong, cảm ơn.' },
		{
			id: 'a-20',
			kind: 'step',
			text: 'Đóng yêu cầu theo xác nhận của cư dân',
			detail: [
				'POST /workforce/v1/partner/workflows/workflow-A/close, expected_revision=6',
				'Dừng theo dõi; chỉ đóng workflow-A, không đụng tới yêu cầu khác của cùng cư dân',
			],
		},
		{ id: 'a-21', kind: 'state', state: 'closed', nextAction: 'none' },
	],
};

/** Interactive transaction (2.4, 17.1 B, cases 5–9, 80–81): a trip with a budget. */
const TRIP: MockConversation = {
	id: 'ticket-b',
	name: 'Chuyến đi Bãi Cháy',
	subtitle: 'Căn S1-0205, Ocean Park 1',
	requester: RESIDENT_REQUESTER,
	lastMessageAt: '09:20',
	events: [
		{
			id: 'b-1',
			kind: 'user',
			sender: RESIDENT,
			text: 'Tôi muốn đi Bãi Cháy cuối tuần này, ngân sách 10 triệu.',
		},
		intake('b-2', 'B'),
		{
			id: 'b-3',
			kind: 'thinking',
			agent: 'leader',
			seconds: 3,
			text: 'Yêu cầu cần lập kế hoạch, tìm khách sạn, tìm xe và tính chi phí theo ngân sách. Chọn Lập kế hoạch, Khách sạn, Xe và Tính chi phí. Không thêm Agent Kỹ thuật vì chưa có yêu cầu kỹ thuật nào. Cư dân này còn một yêu cầu sửa ống nước đang mở, nhưng đó là phiên khác và không dùng chung ngữ cảnh.',
		},
		{
			id: 'b-4',
			kind: 'step',
			agent: 'leader',
			joins: ['planner', 'hotel', 'car', 'calculator'],
			text: '**Leader** thêm bốn agent vào phiên: **Lập kế hoạch**, **Khách sạn**, **Xe** và **Tính chi phí**',
			detail: [
				'Chọn theo năng lực trong thư viện của manager-A, không theo lô đã tạo agent',
				'group.member_added ×4, mỗi agent một session riêng trong group-B',
				'workflow_state=active',
			],
		},
		{
			id: 'b-5',
			kind: 'thinking',
			agent: 'planner',
			seconds: 4,
			text: 'Đã có điểm đến và ngân sách. “Cuối tuần này” tính từ ngày gửi 09/10/2026 theo giờ Việt Nam là thứ Bảy 10/10 và Chủ nhật 11/10/2026. Còn thiếu số người, điểm đi, số đêm và ưu tiên chi tiêu. Không hỏi lại ngân sách vì cư dân đã nói.',
		},
		{
			id: 'b-6',
			kind: 'agent',
			agent: 'planner',
			text: [
				'Tôi hiểu là anh/chị đi Bãi Cháy thứ Bảy 10/10 và Chủ nhật 11/10/2026, ngân sách 10.000.000 ₫. Tôi cần thêm:',
				'',
				'- Đi mấy người, xuất phát từ đâu?',
				'- Ở mấy đêm?',
				'- Anh/chị muốn ưu tiên tiền cho khoản nào?',
			].join('\n'),
		},
		{ id: 'b-7', kind: 'state', state: 'awaiting_user', nextAction: 'submit_reply' },
		{
			id: 'b-8',
			kind: 'gate',
			action: 'reply',
			label: '2 người, đi từ Hà Nội, ở 1 đêm. Ưu tiên khách sạn, giữ lại 2 triệu ăn uống.',
		},
		{
			id: 'b-9',
			kind: 'user',
			sender: RESIDENT,
			text: '2 người, đi từ Hà Nội, ở 1 đêm. Ưu tiên khách sạn, giữ lại 2 triệu ăn uống.',
		},
		{
			id: 'b-10',
			kind: 'step',
			text: 'Câu trả lời được đưa vào đúng phiên đang mở, giữ nguyên ngữ cảnh',
			detail: [
				'command_type=workflow_reply, workflow_id=workflow-B',
				'Lượt chạy mới (run_id mới) trên cùng group-B; không tạo phiên hay ticket khác',
				'workflow_state: awaiting_user → active',
			],
		},
		{
			id: 'b-11',
			kind: 'step',
			agent: 'planner',
			text: '**Agent Lập kế hoạch** nhờ **Agent Khách sạn** tìm phòng và **Agent Xe** tìm chuyến',
			detail: ['Trao đổi trong nhóm bằng TeamSay, kèm địa điểm, ngày và số người'],
		},
		{
			id: 'b-12',
			kind: 'tool',
			agent: 'hotel',
			label: 'Tìm phòng khách sạn',
			effect: 'read',
			input: 'Bãi Cháy, 10–11/10/2026\n2 người, 1 đêm',
			summary: '2 khách sạn còn phòng',
			result: 'Khách sạn A: 5.000.000 ₫\nKhách sạn B: 6.000.000 ₫',
			detail: ['search_hotels (Hotel MCP), chỉ đọc nên không cần xác nhận'],
		},
		{
			id: 'b-13',
			kind: 'tool',
			agent: 'car',
			label: 'Tìm xe',
			effect: 'read',
			input: 'Hà Nội ⇄ Bãi Cháy, 10–11/10/2026\n2 người',
			summary: '1 xe khứ hồi phù hợp',
			result: 'Xe khứ hồi: 2.000.000 ₫',
			detail: ['search_cars (Car MCP), chỉ đọc'],
		},
		{
			id: 'b-14',
			kind: 'thinking',
			agent: 'calculator',
			seconds: 3,
			text: 'Ngân sách 10.000.000 ₫, phải giữ 2.000.000 ₫ ăn uống. Phương án A: 5.000.000 + 2.000.000 + phí 500.000 + 2.000.000 = 9.500.000, đạt. Phương án B: 6.000.000 + 2.000.000 + 500.000 + 2.000.000 = 10.500.000, vượt 500.000. Tính bằng công cụ chứ không nhẩm.',
		},
		{
			id: 'b-15',
			kind: 'tool',
			agent: 'calculator',
			label: 'Tính tổng chi phí',
			effect: 'read',
			input: 'Ngân sách: 10.000.000 ₫\nGiữ lại ăn uống: 2.000.000 ₫\nPhí đã biết: 500.000 ₫',
			summary: 'A đạt 9.500.000 ₫, B vượt ngân sách',
			result: 'Phương án A: 9.500.000 ₫ (đạt)\nPhương án B: 10.500.000 ₫ (vượt 500.000 ₫)',
			detail: ['Công cụ tính có sẵn của platform, kết quả xác định'],
		},
		{
			id: 'b-16',
			kind: 'agent',
			agent: 'planner',
			text: [
				'Có hai phương án cho 2 người, 1 đêm:',
				'',
				'| Khoản | Phương án A | Phương án B |',
				'|---|---|---|',
				'| Khách sạn | 5.000.000 ₫ | 6.000.000 ₫ |',
				'| Xe khứ hồi | 2.000.000 ₫ | 2.000.000 ₫ |',
				'| Phí | 500.000 ₫ | 500.000 ₫ |',
				'| Ăn uống giữ lại | 2.000.000 ₫ | 2.000.000 ₫ |',
				'| **Tổng** | **9.500.000 ₫** | **10.500.000 ₫** |',
				'',
				'Phương án A nằm trong ngân sách. Phương án B vượt 500.000 ₫. Báo giá có hiệu lực đến 18:00 hôm nay. Anh/chị chọn phương án nào?',
			].join('\n'),
		},
		{ id: 'b-17', kind: 'state', state: 'awaiting_user', nextAction: 'submit_reply' },
		{
			id: 'b-18',
			kind: 'gate',
			action: 'reply',
			label: '@hotel khách sạn A có hồ bơi không?',
		},
		{
			id: 'b-19',
			kind: 'user',
			sender: RESIDENT,
			text: '@hotel khách sạn A có hồ bơi không?',
		},
		{
			id: 'b-20',
			kind: 'step',
			agent: 'leader',
			text: 'Câu hỏi gọi tên **Agent Khách sạn** nên được chuyển thẳng cho agent đó, kèm ngữ cảnh khách sạn A đang tư vấn',
			detail: [
				'command_type=workflow_reply, cùng workflow-B',
				'@hotel trong nhóm: không cần Leader chọn lại agent',
			],
		},
		{
			id: 'b-21',
			kind: 'tool',
			agent: 'hotel',
			label: 'Xem tiện ích khách sạn',
			effect: 'read',
			input: 'Khách sạn A, Bãi Cháy',
			summary: 'Có hồ bơi ngoài trời',
			result: 'Hồ bơi ngoài trời\nBữa sáng\nChỗ đỗ xe',
			detail: ['get_hotel_detail (Hotel MCP), chỉ đọc'],
		},
		{
			id: 'b-22',
			kind: 'agent',
			agent: 'hotel',
			text: 'Khách sạn A có hồ bơi ngoài trời, giá phòng đã gồm bữa sáng và có chỗ đỗ xe.',
		},
		{ id: 'b-23', kind: 'state', state: 'awaiting_user', nextAction: 'submit_reply' },
		{
			id: 'b-24',
			kind: 'gate',
			action: 'reply',
			label: 'Tôi chọn phương án A, đặt giúp tôi.',
		},
		{
			id: 'b-25',
			kind: 'user',
			sender: RESIDENT,
			text: 'Tôi chọn phương án A, đặt giúp tôi.',
		},
		{
			id: 'b-26',
			kind: 'thinking',
			agent: 'planner',
			seconds: 3,
			text: 'Cư dân đã chọn phương án A và yêu cầu đặt. Đặt phòng và đặt xe là thao tác ghi, tạo giao dịch thật. Phải có xác nhận của cư dân cho đúng phương án và đúng giá trước khi gọi công cụ đặt.',
		},
		{
			id: 'b-27',
			kind: 'step',
			agent: 'planner',
			text: '**Agent Lập kế hoạch** đề xuất đặt phương án A và dừng lại chờ cư dân đồng ý',
			detail: [
				'Tool call: proposed → awaiting_approval',
				'Chưa có lệnh ghi nào được gọi (zero write calls)',
			],
		},
		{
			id: 'b-28',
			kind: 'state',
			state: 'awaiting_approval',
			nextAction: 'submit_approval',
		},
		{
			id: 'b-29',
			kind: 'gate',
			action: 'approval',
			approval: {
				approval_id: 'approval-b-1',
				call_id: 'call-b-1',
				status: 'pending',
				arguments_hash: 'mock-arguments',
				quote_hash: 'mock-quote',
				quote: {
					provider: 'Khách sạn A và xe Hà Nội – Bãi Cháy',
					option: 'phương án A',
					dates: ['10/10/2026', '11/10/2026'],
					amount: { amount_minor: 7_000_000, currency: 'VND' },
					fees: { amount_minor: 500_000, currency: 'VND' },
					cancellation_terms: 'Hủy miễn phí trước 18:00 ngày 09/10/2026',
					quote_ref: 'QUOTE-A',
					quote_version: '1',
				},
				decision_history: [],
			},
			rejected: [
				{
					id: 'b-r1',
					kind: 'step',
					text: 'Cư dân **từ chối** giao dịch, không có lệnh đặt nào được gọi',
					detail: ['Tool call: awaiting_approval → rejected, dừng trước khi thực thi'],
				},
				{
					id: 'b-r2',
					kind: 'agent',
					agent: 'planner',
					text: 'Tôi đã ghi nhận anh/chị từ chối. Chưa có giao dịch nào được tạo. Anh/chị muốn đổi phương án hay điều chỉnh ngân sách?',
				},
				{
					id: 'b-r3',
					kind: 'state',
					state: 'awaiting_user',
					nextAction: 'submit_reply',
				},
			],
		},
		{
			id: 'b-30',
			kind: 'step',
			text: 'Cư dân **đồng ý** giao dịch cho đúng phương án A và đúng báo giá',
			detail: [
				'Tool call: awaiting_approval → approved → executing',
				'Xác nhận gắn với người gửi, lệnh gọi, tham số và báo giá; không dùng lại cho lệnh khác',
			],
		},
		{
			id: 'b-31',
			kind: 'tool',
			agent: 'hotel',
			label: 'Đặt phòng khách sạn',
			effect: 'write',
			input: 'Khách sạn A, 10–11/10/2026\n2 người, 1 đêm',
			summary: 'Đã xác nhận, mã HB-2291',
			result: 'Trạng thái: đã xác nhận\nMã đặt phòng: HB-2291',
			detail: ['book_hotel (Hotel MCP), Tool call: executing → succeeded'],
		},
		{
			id: 'b-32',
			kind: 'tool',
			agent: 'car',
			label: 'Đặt xe',
			effect: 'write',
			input: 'Hà Nội ⇄ Bãi Cháy, 10–11/10/2026\n2 người',
			summary: 'Đã xác nhận, mã CR-5530',
			result: 'Trạng thái: đã xác nhận\nMã đặt xe: CR-5530',
			detail: ['book_car (Car MCP), Tool call: executing → succeeded'],
		},
		{
			id: 'b-33',
			kind: 'agent',
			agent: 'planner',
			text: [
				'Đã đặt xong phương án A:',
				'',
				'- Khách sạn A, 1 đêm cho 2 người, mã **HB-2291**',
				'- Xe khứ hồi Hà Nội – Bãi Cháy, mã **CR-5530**',
				'',
				'Tổng đã đặt là 7.500.000 ₫, còn 2.000.000 ₫ ăn uống theo yêu cầu. Anh/chị xác nhận để tôi đóng yêu cầu.',
			].join('\n'),
		},
		{
			id: 'b-34',
			kind: 'state',
			state: 'awaiting_confirmation',
			nextAction: 'confirm_close',
			detail: ['Cả hai công cụ trả kết quả ngay nên không cần chờ sự kiện từ nhà cung cấp'],
		},
		{ id: 'b-35', kind: 'gate', action: 'reply', label: 'Xác nhận, cảm ơn.' },
		{ id: 'b-36', kind: 'user', sender: RESIDENT, text: 'Xác nhận, cảm ơn.' },
		{
			id: 'b-37',
			kind: 'step',
			text: 'Đóng yêu cầu theo xác nhận của cư dân',
			detail: ['POST /workforce/v1/partner/workflows/workflow-B/close'],
		},
		{ id: 'b-38', kind: 'state', state: 'closed', nextAction: 'none' },
	],
};

/** Response-only (17.1 A, cases 34, 79): a read-only lookup that closes itself. */
const LOOKUP: MockConversation = {
	id: 'ticket-c',
	name: 'Hỏi giờ nhận phòng khách sạn',
	subtitle: 'Căn S1-0205, Ocean Park 1',
	requester: RESIDENT_REQUESTER,
	lastMessageAt: 'hôm qua',
	events: [
		{
			id: 'c-1',
			kind: 'user',
			sender: RESIDENT,
			text: 'Khách sạn A ở Bãi Cháy nhận phòng lúc mấy giờ?',
		},
		intake('c-2', 'C'),
		{
			id: 'c-3',
			kind: 'thinking',
			agent: 'leader',
			seconds: 2,
			text: 'Câu hỏi chỉ tra cứu thông tin một khách sạn. Chỉ cần Agent Khách sạn. Không thêm cả bốn agent du lịch chỉ vì chúng được tạo cùng một lô.',
		},
		{
			id: 'c-4',
			kind: 'step',
			agent: 'leader',
			joins: ['hotel'],
			text: '**Leader** thêm **Agent Khách sạn** vào phiên vì đây là câu hỏi tra cứu khách sạn',
			detail: ['group.member_added, Hotel v3', 'workflow_state=active'],
		},
		{
			id: 'c-5',
			kind: 'tool',
			agent: 'hotel',
			label: 'Xem thông tin khách sạn',
			effect: 'read',
			input: 'Khách sạn A, Bãi Cháy',
			summary: 'Nhận phòng 14:00, trả phòng 12:00',
			result: 'Nhận phòng: từ 14:00\nTrả phòng: trước 12:00',
			detail: ['get_hotel_detail (Hotel MCP), chỉ đọc'],
		},
		{
			id: 'c-6',
			kind: 'agent',
			agent: 'hotel',
			text: 'Khách sạn A nhận phòng từ 14:00 và trả phòng trước 12:00.',
		},
		{
			id: 'c-7',
			kind: 'step',
			text: 'Tra cứu chỉ đọc đã đủ kết quả nên yêu cầu tự đóng',
			detail: [
				'Policy chỉ đọc đã phát hành cho phép auto-close',
				'Không tạo operation, không cần SSE, không cần POST close',
			],
		},
		{
			id: 'c-8',
			kind: 'state',
			state: 'closed',
			nextAction: 'none',
			detail: ['HTTP 200, một lượt là xong'],
		},
	],
};

/** Builder with reuse (2.2, 2.5, cases 21, 36): a batch that only creates what is missing. */
const BUILD: MockConversation = {
	id: 'build-1',
	name: 'Tạo nhiều agent du lịch',
	subtitle: 'Trò chuyện với Builder',
	requester: { name: MANAGER, note: 'Quản lý khu vực Ocean Park 1' },
	lastMessageAt: 'hôm qua',
	events: [
		{
			id: 'd-1',
			kind: 'user',
			sender: MANAGER,
			text: 'Tạo team agent du lịch gồm lập kế hoạch, khách sạn, xe và tính chi phí.',
		},
		{
			id: 'd-2',
			kind: 'thinking',
			agent: 'builder',
			seconds: 4,
			text: '“Team” ở đây là tạo hàng loạt bốn agent độc lập, không phải một nhóm cố định. Trước khi tạo phải tìm agent cùng nghiệp vụ trong thư viện của tài khoản này. Hotel Agent v3 đã phát hành, tìm và đặt được khách sạn, các kết nối của nó đang hoạt động. Ba nghiệp vụ còn lại chưa có agent nào.',
		},
		{
			id: 'd-3',
			kind: 'step',
			agent: 'builder',
			text: '**Builder** đối chiếu từng nghiệp vụ với thư viện agent của bạn',
			detail: [
				'Build: analyzing → checking_existing → proposal_ready',
				'So theo mục tiêu, hành động, đầu vào/đầu ra và quyền thực thi, không so theo tên',
			],
		},
		{
			id: 'd-4',
			kind: 'agent',
			agent: 'builder',
			text: [
				'Đã có **Hotel Agent v3** đáp ứng phần tìm và đặt khách sạn trong thư viện. Chỉ cần tạo thêm ba agent:',
				'',
				'| Nghiệp vụ | Đề xuất |',
				'|---|---|',
				'| Khách sạn | Đã có, không cần tạo lại |',
				'| Lập kế hoạch | Tạo mới |',
				'| Xe | Tạo mới |',
				'| Tính chi phí | Tạo mới |',
				'',
				'Sau khi phát hành, Leader sẽ chọn các agent phù hợp mỗi khi có yêu cầu. Bạn đồng ý với danh sách này chứ?',
			].join('\n'),
		},
		{ id: 'd-5', kind: 'gate', action: 'reply', label: 'Đồng ý, tạo ba agent mới.' },
		{ id: 'd-6', kind: 'user', sender: MANAGER, text: 'Đồng ý, tạo ba agent mới.' },
		{
			id: 'd-7',
			kind: 'step',
			agent: 'builder',
			text: '**Builder** kiểm tra lại đề xuất rồi tạo bản nháp riêng cho từng agent',
			detail: [
				'Kiểm tra trùng lần hai trước khi cấp định danh mới',
				'Lô chỉ để theo dõi tiến độ; không phải nhóm, không có danh sách thành viên',
			],
		},
		{
			id: 'd-8',
			kind: 'thinking',
			agent: 'builder',
			seconds: 3,
			text: 'Agent Xe cam kết đặt xe nên bắt buộc có công cụ đặt xe thật, câu lệnh không thay được công cụ. Agent Lập kế hoạch chỉ điều phối nên không cần công cụ của đối tác. Agent Tính chi phí dùng công cụ tính có sẵn để kết quả xác định.',
		},
		{
			id: 'd-9',
			kind: 'tool',
			agent: 'builder',
			label: 'Chọn công cụ từ các kết nối đã bật',
			effect: 'read',
			input: 'Lập kế hoạch, Xe, Tính chi phí',
			summary: 'Đủ công cụ cho cả ba agent',
			result: 'Xe: tìm xe, đặt xe\nLập kế hoạch: trao đổi trong nhóm\nTính chi phí: công cụ tính có sẵn',
			detail: [
				'Chỉ lấy công cụ đúng phạm vi; bật kết nối không tự thêm công cụ vào agent cũ',
			],
		},
		{
			id: 'd-10',
			kind: 'step',
			agent: 'builder',
			text: 'Chạy đánh giá riêng cho từng bản nháp',
			detail: ['Draft: draft → validating → evaluable → evaluating → passed (×3)'],
		},
		{
			id: 'd-11',
			kind: 'agent',
			agent: 'builder',
			text: 'Ba bản nháp đều đạt đánh giá: Lập kế hoạch, Xe và Tính chi phí. Tôi không tự phát hành. Bạn xem báo cáo từng agent rồi quyết định phát hành.',
		},
		{ id: 'd-12', kind: 'gate', action: 'reply', label: 'Phát hành cả ba.' },
		{ id: 'd-13', kind: 'user', sender: MANAGER, text: 'Phát hành cả ba.' },
		{
			id: 'd-14',
			kind: 'step',
			agent: 'builder',
			text: 'Phát hành ba agent vào thư viện chung của bạn',
			detail: [
				'passed + người dùng bấm phát hành → phiên bản bất biến + deployment đang chạy',
				'Batch: ready → completed; không sinh nhóm xử lý nào',
			],
		},
		{
			id: 'd-15',
			kind: 'agent',
			agent: 'builder',
			text: 'Đã phát hành. Thư viện của bạn hiện có bốn agent du lịch độc lập: Lập kế hoạch v1, Hotel Agent v3, Xe v1 và Tính chi phí v1.',
		},
	],
};

export const MOCK_CONVERSATIONS: MockConversation[] = [REPAIR, TRIP, LOOKUP, BUILD];
