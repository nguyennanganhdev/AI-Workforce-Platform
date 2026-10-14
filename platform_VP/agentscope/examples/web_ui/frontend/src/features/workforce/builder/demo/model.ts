export type Scenario = 'knowledge' | 'travel' | 'missing';
export type Stage = 'start' | 'clarify' | 'outline' | 'configure' | 'done';
export interface DemoAgent {
	id: string;
	name: string;
	objective: string;
	instructions: string;
	tools: string[];
	knowledge: string[];
	blocker?: string;
}
export interface DemoMessage {
	id: string;
	role: 'user' | 'builder';
	text: string;
}
export interface DemoState {
	version: 1;
	stage: Stage;
	scenario: Scenario;
	messages: DemoMessage[];
	agents: DemoAgent[];
}
export const scenarios: { id: Scenario; title: string; description: string; prompt: string }[] = [
	{
		id: 'knowledge',
		title: 'Trợ lý tri thức',
		description: 'Một agent, trả lời từ tài liệu nội bộ',
		prompt: 'Tạo một trợ lý giải đáp nội quy cho cư dân từ tài liệu của ban quản lý.',
	},
	{
		id: 'travel',
		title: 'Đội ngũ du lịch',
		description: 'Hai agent với nhiệm vụ bổ trợ nhau',
		prompt: 'Tạo agent tư vấn du lịch và agent đặt khách sạn cho khách hàng.',
	},
	{
		id: 'missing',
		title: 'Điều phối dịch vụ',
		description: 'Khám phá cách xử lý khi thiếu công cụ',
		prompt: 'Tạo agent đặt lịch sửa chữa và theo dõi tiến độ dịch vụ.',
	},
];
export const toolOptions = [
	'Tra cứu tài liệu',
	'Tìm địa điểm',
	'Tìm khách sạn',
	'Đặt khách sạn',
	'Tra cứu yêu cầu',
];
export const knowledgeOptions = ['Nội quy cư dân', 'Cẩm nang du lịch', 'Quy trình dịch vụ'];
export const initialState = (): DemoState => ({
	version: 1,
	stage: 'start',
	scenario: 'knowledge',
	messages: [],
	agents: [],
});
export function createAgents(scenario: Scenario): DemoAgent[] {
	const agent = (
		id: string,
		name: string,
		objective: string,
		tools: string[],
		knowledge: string[],
	): DemoAgent => ({
		id,
		name,
		objective,
		tools,
		knowledge,
		instructions: `Bạn là ${name}. ${objective} Hỏi lại khi thiếu thông tin. Chỉ trả lời dựa trên nguồn đã kiểm chứng và yêu cầu xác nhận trước thao tác đặt dịch vụ.`,
	});
	if (scenario === 'travel')
		return [
			agent(
				'travel',
				'Chuyên viên tư vấn du lịch',
				'Tìm điểm đến và đề xuất lịch trình phù hợp với nhu cầu, thời gian và ngân sách.',
				['Tìm địa điểm'],
				['Cẩm nang du lịch'],
			),
			agent(
				'hotel',
				'Trợ lý đặt khách sạn',
				'Tìm khách sạn, so sánh lựa chọn và hỗ trợ đặt phòng sau khi khách xác nhận.',
				['Tìm khách sạn', 'Đặt khách sạn'],
				['Cẩm nang du lịch'],
			),
		];
	if (scenario === 'missing')
		return [
			{
				...agent(
					'service',
					'Điều phối viên dịch vụ',
					'Tiếp nhận yêu cầu sửa chữa, đặt lịch và theo dõi tiến độ xử lý.',
					['Tra cứu yêu cầu'],
					['Quy trình dịch vụ'],
				),
				blocker:
					'Chưa có công cụ đặt lịch sửa chữa. Thử kịch bản khác hoặc bắt đầu lại với phạm vi chỉ tra cứu.',
			},
		];
	return [
		agent(
			'knowledge',
			'Trợ lý cư dân',
			'Giải đáp nội quy, tiện ích và hướng dẫn cư dân dựa trên tài liệu của ban quản lý.',
			['Tra cứu tài liệu'],
			['Nội quy cư dân'],
		),
	];
}
export function canCreate(agents: DemoAgent[]) {
	return (
		agents.length > 0 &&
		agents.every(
			(a) =>
				a.name.trim() &&
				a.objective.trim() &&
				a.instructions.trim() &&
				a.tools.length &&
				!a.blocker,
		)
	);
}
