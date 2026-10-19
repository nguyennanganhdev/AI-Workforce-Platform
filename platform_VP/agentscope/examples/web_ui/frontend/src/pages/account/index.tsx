import { useQuery } from '@tanstack/react-query';

import { personalApi } from '@/api/personal';
import { Button } from '@/components/ui/button';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { usePlatformAccess } from '@/context/platform-access';

const number = new Intl.NumberFormat('vi-VN');

export function AccountPage() {
	const user = useCurrentUser()!;
	const access = usePlatformAccess();
	const usage = useQuery({ queryKey: ['personal-usage', user.id, access?.view?.workspace_id], queryFn: personalApi.usage, retry: false });
	return (
		<main className="mx-auto h-full max-w-4xl space-y-8 overflow-y-auto p-5 sm:p-8">
			<header className="space-y-2">
				<h1 className="text-2xl font-semibold tracking-tight">Tài khoản và hạn mức</h1>
				<p className="text-sm text-muted-foreground">Thông tin tài khoản và mức sử dụng được hệ thống ghi nhận.</p>
			</header>
			<dl className="grid gap-x-8 gap-y-4 rounded-xl border bg-background p-5 sm:grid-cols-2">
				<div><dt className="text-sm text-muted-foreground">Tên đăng nhập</dt><dd className="mt-1 break-all">{user.username}</dd></div>
				<div><dt className="text-sm text-muted-foreground">Email</dt><dd className="mt-1 break-all">{user.email}</dd></div>
				<div><dt className="text-sm text-muted-foreground">Trạng thái</dt><dd className="mt-1">{user.status === 'active' ? 'Đang hoạt động' : 'Chưa hoạt động'}</dd></div>
				<div><dt className="text-sm text-muted-foreground">Dùng AI cá nhân</dt><dd className="mt-1">{access?.view?.eligible ? 'Đã được cấp quyền' : 'Chờ xác minh điều kiện sử dụng'}</dd></div>
			</dl>
			<section aria-labelledby="usage-heading" className="space-y-4">
				<div className="flex flex-wrap items-center justify-between gap-3">
					<h2 id="usage-heading" className="text-lg font-semibold">Sử dụng model</h2>
					<Button variant="outline" className="min-h-11" disabled={usage.isFetching} onClick={() => void usage.refetch()}>Cập nhật</Button>
				</div>
				{usage.isPending ? <p role="status">Đang tải mức sử dụng…</p> : usage.isError ? <p role="alert" className="text-sm">Chưa tải được mức sử dụng. Vui lòng thử lại.</p> : <>
					<p className="text-sm text-muted-foreground">Múi giờ: {usage.data.timezone}. Token đang giữ chỗ chưa phải chi phí đã quyết toán.</p>
					{usage.data.pending_reconciliation > 0 && <p role="status" className="rounded-lg border p-3 text-sm">{number.format(usage.data.pending_reconciliation)} lượt đang chờ đối soát. Số liệu có thể được cập nhật sau.</p>}
					{usage.data.effective_limits && <div className="space-y-2"><h3 className="text-sm font-semibold">Hạn mức khả dụng · chính sách v{usage.data.policy_revision}</h3>
						<div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><caption className="sr-only">Hạn mức và số token còn lại</caption>
							<thead className="bg-muted"><tr>{['Đối tượng / kỳ', 'Giới hạn', 'Đã dùng', 'Giữ chỗ', 'Còn lại'].map((label) => <th key={label} scope="col" className="p-3">{label}</th>)}</tr></thead>
							<tbody>{usage.data.effective_limits.map((limit) => <tr key={`${limit.subject}:${limit.window}`} className="border-t"><th scope="row" className="p-3 font-normal">{limit.subject === `user:${user.id}` ? 'Cá nhân' : limit.subject} · {limit.window}</th>{[limit.limit, limit.used, limit.reserved, limit.remaining].map((value, index) => <td key={index} className="p-3 text-right tabular-nums">{number.format(value)}</td>)}</tr>)}</tbody>
						</table></div></div>}
					{usage.data.buckets.length === 0 ? <p className="rounded-xl border p-6 text-sm text-muted-foreground">Chưa có số liệu sử dụng được ghi nhận. Hạn mức khả dụng sẽ được kiểm tra khi bắt đầu tác vụ.</p> :
						<div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm">
							<caption className="sr-only">Token theo kỳ sử dụng</caption>
							<thead className="bg-muted"><tr><th className="p-4" scope="col">Kỳ</th><th className="p-4 text-right" scope="col">Đã dùng</th><th className="p-4 text-right" scope="col">Đang giữ chỗ</th></tr></thead>
							<tbody>{usage.data.buckets.map((bucket) => <tr className="border-t" key={bucket.window}><th scope="row" className="p-4 font-normal">{bucket.window}</th><td className="p-4 text-right tabular-nums">{number.format(bucket.used)}</td><td className="p-4 text-right tabular-nums">{number.format(bucket.reserved)}</td></tr>)}</tbody>
						</table></div>}
				</>}
			</section>
		</main>
	);
}
