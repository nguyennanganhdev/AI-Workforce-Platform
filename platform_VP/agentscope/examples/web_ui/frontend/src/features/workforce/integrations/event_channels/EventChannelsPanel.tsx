import { channelReadiness } from './readiness';
import type { EventChannelView, Readiness } from './readiness';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
const readinessLabels: Record<Readiness, string> = {
	ready: 'Sẵn sàng',
	blocked: 'Chưa sẵn sàng',
	unsupported: 'Không hỗ trợ',
	not_required: 'Không cần',
};
const statusLabels: Record<EventChannelView['status'], string> = {
	configured: 'Đã cấu hình',
	disabled: 'Đã tắt gọi mới',
	drifted: 'Schema đã thay đổi',
	unconfigured: 'Chưa cấu hình',
	error: 'Lỗi cấu hình',
};
const blockerLabels: Record<EventChannelView['blockers'][number], string> = {
	CONNECTION_DISABLED: 'Kết nối đang tắt.',
	SCHEMA_DRIFT: 'Cần kiểm tra và đăng ký phiên bản schema mới.',
	PROTOCOL_NOT_CONFIGURED: 'Chưa đăng ký protocol.',
	CORRELATION_NOT_READY: 'Chưa cấu hình đối chiếu operation/job.',
	PROVIDER_AUTH_NOT_READY: 'Chưa sẵn sàng xác thực Provider Event API.',
	QUERY_BINDING_UNAVAILABLE: 'Tool truy vấn trạng thái chưa khả dụng.',
};

export function EventChannelsPanel({
	channels,
	loading = false,
	error = false,
	onRetry,
}: {
	channels: readonly EventChannelView[];
	loading?: boolean;
	error?: boolean;
	onRetry?: () => void;
}) {
	if (loading) return <p role="status">Đang tải cấu hình protocol…</p>;
	if (error) return (
		<Alert variant="destructive">
			<AlertDescription>
				<p>Không tải được trạng thái protocol.</p>
				{onRetry && <Button type="button" variant="outline" onClick={onRetry}>Thử lại</Button>}
			</AlertDescription>
		</Alert>
	);
	if (!channels.length) return <p>Chưa có protocol được đăng ký.</p>;

	return (
		<Table>
			<TableCaption>
				Capability cấu hình cần được xác minh với kết nối và quyền hiện hành.
				Provider Event API có thể tiếp tục nhận cho job đã pin khi tắt gọi mới.
			</TableCaption>
			<TableHeader><TableRow>
				{['Tool / protocol', 'Cấu hình', 'Tạo job', 'Provider Event API',
					'Query qua MCP', 'Correlation', 'Điểm cần xử lý'].map((title) => (
					<TableHead key={title} scope="col">{title}</TableHead>
				))}
			</TableRow></TableHeader>
			<TableBody>{channels.map((channel) => {
				const readiness = channelReadiness(channel);
				return <TableRow key={channel.tool_version_id}>
					<TableCell>
						<p className="font-medium">{channel.name}</p>
						<p className="text-xs text-muted-foreground">
							{channel.tool_version_id} · protocol {channel.protocol_version}
						</p>
						{channel.capabilities.includes('approval') && (
							<Badge variant="outline">Cần xác nhận</Badge>
						)}
					</TableCell>
					<TableCell>{statusLabels[channel.status]}</TableCell>
					{(['create', 'providerEvent', 'statusQuery', 'correlation'] as const).map((key) => (
						<TableCell key={key}>
							<Badge variant={readiness[key] === 'ready' ? 'secondary' : 'outline'}>
								{readinessLabels[readiness[key]]}
							</Badge>
						</TableCell>
					))}
					<TableCell className="whitespace-normal min-w-48">
						{channel.blockers.map((code) => <p key={code}>{blockerLabels[code]}</p>)}
						{channel.capabilities.includes('create')
							&& !channel.capabilities.some((c) => ['receive_status', 'status_query'].includes(c))
							&& <p>Chỉ tạo job; chưa hỗ trợ theo dõi tiến độ.</p>}
					</TableCell>
				</TableRow>;
			})}</TableBody>
		</Table>
	);
}
