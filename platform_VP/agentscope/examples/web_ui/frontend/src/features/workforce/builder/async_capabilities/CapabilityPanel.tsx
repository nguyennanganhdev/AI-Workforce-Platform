import type { AgentProposal } from '../types';

export function CapabilityPanel({ item }: { item: AgentProposal }) {
	const { requirement, selection } = item;
	const policy = requirement.policy_proposal;
	const blockers = [...item.blockers, ...selection.blockers];
	return (
		<section className="space-y-3 rounded-lg border p-4" aria-label={`Năng lực ${requirement.agent_key}`}>
			<h3 className="font-semibold">{requirement.business_profile.objective}</h3>
			<p>Tác động: {({ read: 'Chỉ đọc', write: 'Thay đổi dữ liệu', external_operation: 'Công việc bên ngoài' })[requirement.effect]}</p>
			<p>{requirement.tracking_intent === 'track_to_completion' ? 'Theo dõi đến hoàn tất' : requirement.tracking_intent === 'create_only' ? 'Không yêu cầu theo dõi dài hạn' : 'Cần làm rõ phạm vi theo dõi'}</p>
			<ul className="list-inside list-disc">
				{requirement.capabilities.map(cap => <li key={cap.capability}>
					{cap.capability} · {cap.required ? 'Bắt buộc' : 'Tùy chọn'} · {selection.covered.includes(cap.capability) ? 'Đã có' : 'Còn thiếu'}
					<p className="text-sm text-muted-foreground">{cap.reason}</p>
				</li>)}
			</ul>
			{selection.bindings.map(binding => <p key={`${binding.tool_version_id}:${binding.required_capability}`} className="text-sm">Tool {binding.tool_id}: {binding.selection_reason}</p>)}
			<p>Khả năng: {selection.support.map(value => ({ response_only: 'Trả lời chỉ đọc', interactive: 'Trao đổi / xác nhận với người dùng', external_tracking: 'Theo dõi công việc bên ngoài' })[value] || value).join(', ') || 'Chưa xác định'}</p>
			{selection.tracking_channel !== 'none' && <p>Kênh theo dõi: {selection.tracking_channel === 'provider_events' ? 'Sự kiện từ nhà cung cấp' : 'Tra cứu trạng thái'}</p>}
			{selection.completion_policy && <p>Đóng công việc: {selection.completion_policy === 'explicit_close' ? 'Xác nhận đóng' : 'Tự đóng khi đã đủ kết quả chỉ đọc'}</p>}
			{policy && <div className="space-y-1 text-sm">
				<p>Hoàn tất khi: {policy.completion_condition}</p>
				<p>Dữ kiện cần: {policy.required_facts.join(', ')}</p>
				<p>{policy.human_confirmation ? 'Cần người dùng xác nhận kết quả' : 'Không yêu cầu xác nhận thêm theo policy'}</p>
				<p>Khi hết thời hạn: {policy.timeout_behavior === 'status_query' ? 'Tra cứu trạng thái' : 'Yêu cầu xử lý bổ sung'}</p>
			</div>}
			{blockers.length > 0 && <div role="alert" className="rounded border border-destructive p-3">
				<p className="font-medium">Chưa thể xác nhận</p>
				<ul>{blockers.map((blocker, index) => <li key={`${blocker.code}:${index}`}>{blocker.message}</li>)}</ul>
			</div>}
		</section>
	);
}
