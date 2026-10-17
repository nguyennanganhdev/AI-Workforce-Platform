import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import type { ReactNode } from 'react';

import { vinAdminApi } from '@/api/vinAdmin';
import type { VinPage } from '@/api/vinAdmin';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Filters = Record<string, string | number | boolean | undefined>;
export type AdminAction = (action: () => Promise<unknown>, message: string) => Promise<void>;

function Paged<T>({ title, filters, load, render }: { title: string; filters: Filters;
	load: (filters: Filters) => Promise<VinPage<T>>; render: (row: T) => ReactNode }) {
	const [offset, setOffset] = useState(0);
	const result = useQuery({ queryKey: ['vin-admin', title, filters, offset], queryFn: () => load({ ...filters, offset, limit: 10 }), retry: false });
	return <section className="space-y-3" aria-label={title}><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium">{title}</h3>
		<Button size="sm" variant="ghost" disabled={result.isFetching} onClick={() => void result.refetch()}>Tải lại danh sách</Button></div>
		{result.isError && <p role="alert">Chưa đọc được danh sách. Hãy tải lại trước khi sửa.</p>}
		{result.isPending ? <p role="status">Đang tải…</p> : result.data && <>
			{result.data.items.length === 0 && <p className="text-sm text-muted-foreground">Không có bản ghi phù hợp.</p>}
			{result.data.items.map((row, index) => <div key={index} className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm">{render(row)}</div>)}
			<div className="flex flex-wrap items-center gap-3 text-sm"><span>{result.data.total} bản ghi · từ {result.data.total ? offset + 1 : 0}</span>
				<Button size="sm" variant="outline" disabled={offset === 0 || result.isFetching} onClick={() => setOffset(Math.max(0, offset - 10))}>Trang trước</Button>
				<Button size="sm" variant="outline" disabled={result.data.next_offset === null || result.isFetching} onClick={() => setOffset(result.data!.next_offset!)}>Trang sau</Button></div>
		</>}
	</section>;
}

export function AdminRecords<T>(props: Parameters<typeof Paged<T>>[0]) {
	return <Paged key={JSON.stringify(props.filters)} {...props} />;
}

export function AccessRecords({ perform, busy }: { perform: AdminAction; busy: boolean }) {
	const [subject, setSubject] = useState('');
	const [group, setGroup] = useState('');
	return <div className="space-y-6"><div className="space-y-2"><Input aria-label="Lọc grant theo ID nhận quyền" placeholder="Lọc grant theo ID nhận quyền" value={subject} onChange={(event) => setSubject(event.target.value)} />
		<AdminRecords title="Quyền catalog đã cấp" filters={{ subject_id: subject }} load={vinAdminApi.grants} render={(row) => <>
			<span>{row.subject_kind}:{row.subject_id} · {row.permissions.join(', ')} · {row.active ? 'Đang cấp' : 'Đã thu hồi'} · v{row.revision}<br />{row.catalog_id}</span>
			<Button size="sm" variant="outline" disabled={busy || !row.active} onClick={() => void perform(() => vinAdminApi.revokeGrant(row.id, row.revision), 'Đã thu hồi quyền catalog.')}>Thu hồi quyền {row.subject_id}</Button></>} /></div>
		<div className="space-y-2"><Input aria-label="Lọc thành viên theo nhóm" placeholder="Lọc thành viên theo nhóm" value={group} onChange={(event) => setGroup(event.target.value)} />
			<AdminRecords title="Thành viên nhóm" filters={{ group_id: group }} load={vinAdminApi.memberships} render={(row) => <><span>{row.user_id} · nhóm {row.group_id} · {row.active ? 'Đang tham gia' : 'Đã thu hồi'} · v{row.revision}</span>
				<Button size="sm" variant="outline" disabled={busy || !row.active} onClick={() => void perform(() => vinAdminApi.revokeMembership(row.id, row.revision), 'Đã thu hồi thành viên nhóm.')}>Thu hồi thành viên {row.user_id}</Button></>} /></div>
	</div>;
}

export function EligibilityRecords({ perform, busy }: { perform: AdminAction; busy: boolean }) {
	const [user, setUser] = useState('');
	return <div className="space-y-3"><Input aria-label="Lọc điều kiện AI theo User ID" placeholder="Lọc theo User ID" value={user} onChange={(event) => setUser(event.target.value)} />
		<AdminRecords title="Điều kiện dùng AI cá nhân" filters={{ user_id: user }} load={vinAdminApi.accounts} render={(row) => <>
			<span>{row.username} · {row.user_id} · {row.eligible ? 'Được dùng AI' : 'Chưa được dùng AI'} · v{row.revision}</span>
			<Button size="sm" variant="outline" disabled={busy || row.role !== 'VIN_USER'} onClick={() => void perform(() => vinAdminApi.eligibility(row.user_id, !row.eligible, row.revision), 'Đã cập nhật điều kiện dùng AI.')}>{row.eligible ? 'Tắt' : 'Bật'} AI {row.username}</Button></>} />
	</div>;
}

export function LibraryReview({ catalogId, perform, busy }: { catalogId: string; perform: AdminAction; busy: boolean }) {
	const [status, setStatus] = useState('');
	return <div className="space-y-3"><label className="grid gap-2 text-sm">Trạng thái duyệt<select className="h-9 rounded-md border bg-background px-2" value={status} onChange={(event) => setStatus(event.target.value)}>
		<option value="">Tất cả</option><option value="candidate">Chờ duyệt</option><option value="approved">Đã duyệt</option><option value="retired">Ngừng dùng</option></select></label>
		<AdminRecords title="Tài liệu thư viện Vin" filters={{ review_status: status, catalogId }} load={(filters) => vinAdminApi.documents(catalogId, { review_status: filters.review_status, offset: filters.offset, limit: filters.limit })} render={(doc) => <>
			<span>{doc.filename} · {doc.status} · {doc.review_status} · bản {doc.version}<br />Nguồn: {doc.source_ref || 'Chưa khai báo'}</span>
			<div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy || doc.status !== 'ready' || doc.review_status === 'approved'} onClick={() => void perform(() => vinAdminApi.review(catalogId, doc.document_id, 'approved', doc.revision), 'Đã duyệt tài liệu thư viện.')}>Duyệt {doc.filename}</Button>
				<Button size="sm" variant="ghost" disabled={busy || doc.review_status === 'retired'} onClick={() => void perform(() => vinAdminApi.review(catalogId, doc.document_id, 'retired', doc.revision), 'Đã ngừng dùng tài liệu thư viện.')}>Ngừng dùng {doc.filename}</Button></div></>} />
	</div>;
}
