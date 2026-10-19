import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { vinAdminApi } from '@/api/vinAdmin';
import type { VinAccount } from '@/api/vinAdmin';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCurrentUser } from '@/context/CurrentUserContext';

const PAGE = 25;
const STATUS: Record<string, string> = { active: 'Đang hoạt động', suspended: 'Đã khoá' };
const date = (value: string | null) =>
	value ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—';
const tokens = (value: number) => value.toLocaleString('vi-VN');

/** Customer accounts: who they are, when they last signed in, what they used this month. */
export function UsersPanel() {
	const me = useCurrentUser();
	const queries = useQueryClient();
	const [q, setQ] = useState('');
	const [status, setStatus] = useState('');
	const [offset, setOffset] = useState(0);
	const [busy, setBusy] = useState<string | null>(null);
	const [removing, setRemoving] = useState<VinAccount | null>(null);
	const filters = { q: q.trim(), status, offset, limit: PAGE };
	const page = useQuery({ queryKey: ['vin-admin', 'accounts', filters], queryFn: () => vinAdminApi.accounts(filters), retry: false });

	const act = async (account: VinAccount, task: () => Promise<unknown>, done: string) => {
		setBusy(account.user_id);
		try {
			await task();
			toast.success(done);
			await queries.invalidateQueries({ queryKey: ['vin-admin'] });
			return true;
		} catch (error) {
			toast.error(error instanceof Error ? error.message : String(error));
			return false;
		} finally {
			setBusy(null);
		}
	};
	const protectedAccount = (account: VinAccount) => account.role === 'PLATFORM_ADMIN' || account.user_id === me?.id;

	return (
		<section className="space-y-4 py-4">
			<div className="flex flex-wrap items-center gap-2">
				<div className="relative w-full sm:w-72">
					<Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" aria-hidden="true" />
					<Input
						aria-label="Tìm theo email hoặc tên"
						className="pl-8"
						placeholder="Tìm theo email hoặc tên"
						value={q}
						onChange={(event) => { setQ(event.target.value); setOffset(0); }}
					/>
				</div>
				<select
					aria-label="Lọc trạng thái"
					className="h-9 rounded-md border bg-background px-2 text-sm"
					value={status}
					onChange={(event) => { setStatus(event.target.value); setOffset(0); }}
				>
					<option value="">Tất cả trạng thái</option>
					<option value="active">Đang hoạt động</option>
					<option value="suspended">Đã khoá</option>
				</select>
				{page.data && <span className="text-sm text-muted-foreground">{page.data.total} tài khoản</span>}
			</div>

			{page.isLoading ? (
				<Skeleton className="h-64 w-full" />
			) : page.isError ? (
				<p role="alert" className="text-sm text-destructive">Chưa tải được danh sách tài khoản.</p>
			) : (
				<div className="overflow-x-auto">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Tài khoản</TableHead>
								<TableHead>Trạng thái</TableHead>
								<TableHead>Tạo lúc</TableHead>
								<TableHead>Đăng nhập cuối</TableHead>
								<TableHead className="text-right">Token tháng này</TableHead>
								<TableHead className="text-right">Thao tác</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{page.data?.items.length === 0 && (
								<TableRow>
									<TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">Không có tài khoản phù hợp.</TableCell>
								</TableRow>
							)}
							{page.data?.items.map((account) => (
								<TableRow key={account.user_id}>
									<TableCell className="min-w-56">
										<div className="font-medium">{account.email ?? account.username}</div>
										<div className="text-xs text-muted-foreground">
											{account.username}{account.role === 'PLATFORM_ADMIN' ? ' · Quản trị' : ''}
										</div>
									</TableCell>
									<TableCell>
										<Badge variant={account.status === 'active' ? 'secondary' : 'destructive'}>{STATUS[account.status] ?? account.status}</Badge>
										{account.role !== 'PLATFORM_ADMIN' && !account.eligible && (
											<span className="ml-2 text-xs text-muted-foreground">Chưa được dùng AI</span>
										)}
									</TableCell>
									<TableCell className="whitespace-nowrap text-sm">{date(account.created_at)}</TableCell>
									<TableCell className="whitespace-nowrap text-sm">{date(account.last_login_at)}</TableCell>
									<TableCell className="text-right tabular-nums text-sm">{tokens(account.month_tokens)}</TableCell>
									<TableCell className="text-right">
										{protectedAccount(account) ? (
											<span className="text-xs text-muted-foreground">—</span>
										) : (
											<div className="flex justify-end gap-2">
												<Button
													size="sm"
													variant="outline"
													disabled={busy !== null}
													onClick={() => void act(account,
														() => account.status === 'active' ? vinAdminApi.suspend(account.user_id) : vinAdminApi.reactivate(account.user_id),
														account.status === 'active' ? 'Đã khoá tài khoản và đăng xuất mọi phiên.' : 'Đã mở khoá tài khoản.')}
												>
													{account.status === 'active' ? 'Khoá' : 'Mở khoá'}
												</Button>
												<Button size="sm" variant="ghost" className="text-destructive" disabled={busy !== null} onClick={() => setRemoving(account)}>
													Xoá
												</Button>
											</div>
										)}
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			)}

			{page.data && page.data.total > PAGE && (
				<div className="flex items-center justify-end gap-2 text-sm">
					<Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Trước</Button>
					<span className="tabular-nums text-muted-foreground">{offset + 1}–{Math.min(offset + PAGE, page.data.total)} / {page.data.total}</span>
					<Button size="sm" variant="outline" disabled={page.data.next_offset === null} onClick={() => setOffset(page.data?.next_offset ?? offset)}>Sau</Button>
				</div>
			)}

			<Dialog open={removing !== null} onOpenChange={(open) => { if (!open) setRemoving(null); }}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Xoá tài khoản {removing?.email ?? removing?.username}?</DialogTitle>
						<DialogDescription>
							Tài khoản bị đăng xuất và không đăng nhập lại được. Agent, phiên chat, key provider, MCP, skill, kho tri thức và kênh
							của người này bị xoá. Không hoàn tác được.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setRemoving(null)}>Huỷ</Button>
						<Button
							variant="destructive"
							disabled={busy !== null}
							onClick={async () => {
								if (removing && await act(removing, () => vinAdminApi.deleteAccount(removing.user_id), 'Đã xoá tài khoản.')) setRemoving(null);
							}}
						>
							Xoá vĩnh viễn
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</section>
	);
}
