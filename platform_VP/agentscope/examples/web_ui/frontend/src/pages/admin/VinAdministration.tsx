import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { knowledgeBaseApi } from '@/api';
import type { AdminAccount } from '@/api/admin';
import { vinAdminApi } from '@/api/vinAdmin';
import type { VinCatalogEntry, VinCatalogView, VinGrant, VinQuotaPolicy } from '@/api/vinAdmin';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { usePlatformAccess } from '@/context/platform-access';

const QUOTAS = [
	['daily_tokens', 'Token mỗi ngày', 0, Number.MAX_SAFE_INTEGER], ['monthly_tokens', 'Token mỗi tháng', 0, Number.MAX_SAFE_INTEGER],
	['max_output_tokens', 'Token đầu ra tối đa mỗi lượt', 1, 32768], ['max_concurrency', 'Số lượt đồng thời tối đa', 1, 100],
	['embedding_daily_tokens', 'Token embedding mỗi ngày', 0, Number.MAX_SAFE_INTEGER],
	['storage_bytes', 'Dung lượng lưu trữ (byte)', 0, Number.MAX_SAFE_INTEGER], ['max_file_bytes', 'Kích thước tối đa mỗi file (byte)', 0, Number.MAX_SAFE_INTEGER],
] as const;
const options = 'h-9 w-full rounded-md border bg-background px-2 text-sm';
const split = (value: string) => [...new Set(value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean))];
const expires = (value: string) => value ? new Date(value).toISOString() : null;

function Field({ label, children }: { label: string; children: ReactNode }) {
	return <Label className="grid gap-2 text-sm">{label}{children}</Label>;
}

function PolicyEditor({ perform, busy }: { perform: (action: () => Promise<unknown>, message: string) => Promise<void>; busy: boolean }) {
	const [kind, setKind] = useState('role');
	const [subject, setSubject] = useState('VIN_USER');
	const [values, setValues] = useState<Record<string, string>>({});
	const [models, setModels] = useState('');
	const [enabled, setEnabled] = useState(false);
	const [inspect, setInspect] = useState('');
	const [selected, setSelected] = useState('');
	const usage = useQuery({ queryKey: ['vin-admin-usage', selected], queryFn: () => vinAdminApi.usage(selected), enabled: !!selected, retry: false });
	return <div className="max-w-3xl space-y-8"><form className="space-y-4" onSubmit={(event) => {
		event.preventDefault();
		const policy = Object.fromEntries(QUOTAS.map(([key]) => [key, Number(values[key])])) as unknown as VinQuotaPolicy;
		void perform(() => vinAdminApi.savePolicy(`${kind}:${subject.trim()}`, { ...policy, models: split(models), enabled }), 'Đã lưu chính sách quota.');
	}}>
		<h2 className="font-semibold">Chính sách quota Vin</h2>
		<p className="text-sm text-muted-foreground">Nhập đầy đủ chính sách thay thế cho đối tượng đã chọn. Người dùng ưu tiên quota cá nhân, rồi nhóm, rồi vai trò; pool là hạn mức dùng chung của nhóm.</p>
		<p className="text-sm text-muted-foreground">API hiện chưa trả cấu hình policy đã lưu; các ô trống bên dưới không phải giá trị hiện tại.</p>
		<div className="grid gap-3 sm:grid-cols-2"><Field label="Loại đối tượng"><select className={options} value={kind} onChange={(event) => { setKind(event.target.value); setSubject(event.target.value === 'role' ? 'VIN_USER' : ''); }}>
			<option value="role">Vai trò</option><option value="user">Người dùng</option><option value="group">Nhóm</option><option value="pool">Pool nhóm</option>
		</select></Field><Field label="ID đối tượng"><Input required maxLength={240} value={subject} onChange={(event) => setSubject(event.target.value)} /></Field></div>
		<div className="grid gap-3 sm:grid-cols-2">{QUOTAS.map(([key, label, min, max]) => <Field key={key} label={label}><Input type="number" required min={min} max={max} step="1" value={values[key] ?? ''} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></Field>)}</div>
		<Field label="Model được phép (cách nhau bằng dấu phẩy)"><Textarea required maxLength={5000} value={models} onChange={(event) => setModels(event.target.value)} /></Field>
		<Label className="flex items-center gap-2"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Cho phép dùng chính sách này</Label>
		<Button disabled={busy} type="submit">Áp dụng chính sách thay thế</Button>
	</form>
		<section className="space-y-3 border-t pt-4"><h3 className="font-medium">Kiểm tra hạn mức hiệu lực của người dùng</h3><Field label="User ID xem hạn mức"><Input value={inspect} onChange={(event) => setInspect(event.target.value)} /></Field><Button type="button" variant="outline" disabled={!inspect.trim() || usage.isFetching} onClick={() => { if (selected === inspect.trim()) void usage.refetch(); else setSelected(inspect.trim()); }}>Xem hạn mức hiệu lực</Button>
			{usage.isError && <p role="alert">Chưa đọc được hạn mức; kiểm tra user, policy và quyền trong workspace.</p>}
			{usage.data && <div className="space-y-1 text-sm"><p>Chính sách hiệu lực v{usage.data.policy_revision} · Chờ đối soát: {usage.data.pending_reconciliation}</p>{usage.data.effective_limits?.map((limit) => <p key={`${limit.subject}:${limit.window}`}>{limit.subject} · {limit.window}: giới hạn {limit.limit}, còn {limit.remaining}</p>)}</div>}
		</section>
	</div>;
}

const emptyEntry = (owner: string): VinCatalogEntry => ({ kind: 'mcp', resource_id: '', owner_id: owner, version: 1, name: '',
	description: '', environment: 'production', model_names: [], tool_names: [], active: true });

function CatalogEditor({ entry, setEntry, perform, busy, onPublished }: { entry: VinCatalogEntry; setEntry: (value: VinCatalogEntry) => void;
	perform: (action: () => Promise<unknown>, message: string) => Promise<void>; busy: boolean; onPublished: (id: string) => void }) {
	return <form className="max-w-3xl space-y-4" onSubmit={(event) => {
		event.preventDefault();
		const fields = new FormData(event.currentTarget);
		void perform(async () => {
			const result = await vinAdminApi.publish({ ...entry,
				model_names: entry.kind === 'credential' ? split(String(fields.get('model_names') ?? '')) : entry.model_names,
				tool_names: entry.kind === 'mcp' ? split(String(fields.get('tool_names') ?? '')) : entry.tool_names }); onPublished(result.id);
		}, 'Đã ghi phiên bản catalog. Chỉ đối tượng được cấp quyền mới được dùng.');
	}}>
		<h2 className="font-semibold">Ghi phiên bản catalog</h2>
		<p className="text-sm text-muted-foreground">Chọn tài nguyên đã tạo trên Platform. Cập nhật hoặc tắt tài nguyên cần phiên bản lớn hơn bản hiện tại; khách hàng chỉ được xem/chọn/dùng.</p>
		<div className="grid gap-3 sm:grid-cols-2"><Field label="Loại tài nguyên"><select className={options} value={entry.kind} onChange={(event) => setEntry({ ...entry, kind: event.target.value as VinCatalogEntry['kind'] })}>
			<option value="credential">Provider</option><option value="mcp">MCP</option><option value="skill">Skill</option><option value="knowledge_base">Knowledge base</option><option value="agent">Agent</option>
		</select></Field><Field label="Môi trường"><select className={options} value={entry.environment} onChange={(event) => setEntry({ ...entry, environment: event.target.value as 'production' | 'sandbox' })}><option value="production">Production</option><option value="sandbox">Sandbox</option></select></Field>
			<Field label="ID tài nguyên"><Input required maxLength={255} value={entry.resource_id} onChange={(event) => setEntry({ ...entry, resource_id: event.target.value })} /></Field>
			<Field label="ID chủ tài nguyên"><Input required maxLength={255} value={entry.owner_id} onChange={(event) => setEntry({ ...entry, owner_id: event.target.value })} /></Field>
			<Field label="Tên hiển thị"><Input required maxLength={255} value={entry.name} onChange={(event) => setEntry({ ...entry, name: event.target.value })} /></Field>
			<Field label="Phiên bản catalog"><Input type="number" required min="1" step="1" value={entry.version} onChange={(event) => setEntry({ ...entry, version: Number(event.target.value) })} /></Field></div>
		<Field label="Mô tả"><Textarea maxLength={3000} value={entry.description} onChange={(event) => setEntry({ ...entry, description: event.target.value })} /></Field>
		{entry.kind === 'credential' && <Field label="Model được phép"><Input name="model_names" key={entry.model_names.join(',')} defaultValue={entry.model_names.join(', ')} /></Field>}
		{entry.kind === 'mcp' && <Field label="Tool được phép"><Textarea name="tool_names" key={entry.tool_names.join(',')} defaultValue={entry.tool_names.join(', ')} /></Field>}
		<Label className="flex items-center gap-2"><input type="checkbox" checked={entry.active} onChange={(event) => setEntry({ ...entry, active: event.target.checked })} /> Tài nguyên đang hoạt động</Label>
		<Button type="submit" disabled={busy}>Ghi phiên bản catalog</Button>
	</form>;
}

function AccessEditor({ catalogId, setCatalogId, perform, busy }: { catalogId: string; setCatalogId: (value: string) => void;
	perform: (action: () => Promise<unknown>, message: string) => Promise<void>; busy: boolean }) {
	const [subjectKind, setSubjectKind] = useState<VinGrant['subject_kind']>('user');
	const [subject, setSubject] = useState('');
	const [permissions, setPermissions] = useState<VinGrant['permissions']>(['view']);
	const [expiry, setExpiry] = useState('');
	const [grantId, setGrantId] = useState('');
	const [group, setGroup] = useState('');
	const [user, setUser] = useState('');
	const [membershipId, setMembershipId] = useState('');
	return <div className="max-w-3xl space-y-8">
		<form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void perform(async () => {
			const result = await vinAdminApi.grant({ catalog_id: catalogId, subject_kind: subjectKind, subject_id: subject.trim(), permissions, expires_at: expires(expiry) });
			setGrantId(result.id);
		}, 'Đã cấp quyền catalog.'); }}>
			<h2 className="font-semibold">Cấp quyền dùng catalog</h2>
			<Field label="Catalog ID"><Input required value={catalogId} onChange={(event) => setCatalogId(event.target.value)} /></Field>
			<div className="grid gap-3 sm:grid-cols-2"><Field label="Đối tượng nhận quyền"><select className={options} value={subjectKind} onChange={(event) => setSubjectKind(event.target.value as VinGrant['subject_kind'])}><option value="user">Người dùng</option><option value="group">Nhóm</option><option value="role">Vai trò</option></select></Field>
				<Field label="ID nhận quyền"><Input required value={subject} onChange={(event) => setSubject(event.target.value)} /></Field></div>
			<div className="flex flex-wrap gap-4">{(['view', 'bind', 'execute'] as const).map((permission) => <Label key={permission} className="flex items-center gap-2"><input type="checkbox" checked={permissions.includes(permission)} onChange={(event) => setPermissions(event.target.checked ? [...permissions, permission] : permissions.filter((value) => value !== permission))} />{{ view: 'Xem', bind: 'Chọn/gắn', execute: 'Sử dụng' }[permission]}</Label>)}</div>
			<Field label="Hết hạn quyền (tùy chọn)"><Input type="datetime-local" value={expiry} onChange={(event) => setExpiry(event.target.value)} /></Field>
			<Button type="submit" disabled={busy || permissions.length === 0}>Cấp quyền</Button>
		</form>
		<form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void perform(() => vinAdminApi.revokeGrant(grantId), 'Đã thu hồi quyền catalog.'); }}>
			<Field label="Grant ID vừa tạo hoặc cần thu hồi"><Input required value={grantId} onChange={(event) => setGrantId(event.target.value)} /></Field><Button type="submit" variant="outline" disabled={busy}>Thu hồi grant</Button>
		</form>
		<form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void perform(async () => { const result = await vinAdminApi.membership(user, group, null); setMembershipId(result.id); }, 'Đã thêm thành viên nhóm quota/catalog.'); }}>
			<h2 className="font-semibold">Nhóm người dùng</h2><Field label="User ID thành viên"><Input required value={user} onChange={(event) => setUser(event.target.value)} /></Field><Field label="Group ID"><Input required value={group} onChange={(event) => setGroup(event.target.value)} /></Field>
			<Button type="submit" disabled={busy}>Thêm thành viên nhóm</Button>
		</form>
		<form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void perform(() => vinAdminApi.revokeMembership(membershipId), 'Đã thu hồi thành viên nhóm.'); }}>
			<Field label="Membership ID cần thu hồi"><Input required value={membershipId} onChange={(event) => setMembershipId(event.target.value)} /></Field><Button type="submit" variant="outline" disabled={busy}>Thu hồi membership</Button>
		</form>
		<p className="text-xs text-muted-foreground">API chưa có danh sách grants/memberships hiện hành. Lưu ID trả về để thu hồi; các ô này không đại diện toàn bộ quyền đang được cấp.</p>
	</div>;
}

export function VinAdministration({ accounts }: { accounts: AdminAccount[] }) {
	const user = useCurrentUser()!;
	const access = usePlatformAccess();
	const quota = access?.view?.capabilities['quota.manage'] === true;
	const catalog = access?.view?.capabilities['catalog.manage'] === true;
	const [tab, setTab] = useState(quota ? 'quota' : 'catalog');
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState('');
	const [error, setError] = useState('');
	const [entry, setEntry] = useState(() => emptyEntry(user.id));
	const [catalogId, setCatalogId] = useState('');
	const [kind, setKind] = useState('knowledge_base');
	const [environment, setEnvironment] = useState('production');
	const visible = useQuery({ queryKey: ['vin-admin-visible-catalog', user.tenant_id, kind, environment], queryFn: () => vinAdminApi.catalog(kind, environment), enabled: catalog, retry: false });
	const knowledge = useQuery({ queryKey: ['vin-admin-knowledge', user.tenant_id, user.id], queryFn: () => knowledgeBaseApi.listAll(), enabled: catalog, retry: false });
	const perform = async (action: () => Promise<unknown>, done: string) => {
		setBusy(true); setError(''); setMessage('');
		try { await action(); setMessage(done); if (catalog) await visible.refetch(); }
		catch (failure) { setError(failure instanceof Error ? failure.message : 'Chưa lưu được thay đổi.'); }
		finally { setBusy(false); }
	};
	if (!quota && !catalog) return <p role="alert">Không có quyền quản trị quota/catalog trong workspace hiện tại.</p>;
	const choose = (item: VinCatalogView) => {
		setEntry({ kind: item.kind, resource_id: item.resource_id, owner_id: item.owner_id, version: item.version + 1,
			name: item.name, description: item.description, environment: item.environment, model_names: item.model_names, tool_names: item.tool_names, active: item.active });
		setCatalogId(item.catalog_id); setTab('catalog');
	};
	return <section className="min-w-0 space-y-4">
		{message && <p role="status" className="rounded border p-3 text-sm">{message}</p>}{error && <p role="alert" className="rounded border border-destructive p-3 text-sm">{error}</p>}
		<Tabs value={tab} onValueChange={setTab}><TabsList className="flex h-auto flex-wrap justify-start">{quota && <TabsTrigger value="quota">Quota</TabsTrigger>}{catalog && <><TabsTrigger value="catalog">Catalog</TabsTrigger><TabsTrigger value="access">Cấp quyền & nhóm</TabsTrigger><TabsTrigger value="knowledge">Thư viện KB Vin</TabsTrigger></>}</TabsList>
			{quota && <TabsContent value="quota" className="space-y-8"><PolicyEditor perform={perform} busy={busy} />
				<section className="space-y-3"><h2 className="font-semibold">Điều kiện dùng AI cá nhân</h2>{accounts.filter((account) => account.role === 'VIN_USER').map((account) => <div key={account.id} className="flex flex-wrap items-center gap-3 border-b py-2 text-sm"><span>{account.username} · {account.id}</span><Button size="sm" variant="outline" disabled={busy} onClick={() => void perform(() => vinAdminApi.eligibility(account.id, true), 'Đã bật điều kiện dùng AI.')}>Bật điều kiện AI</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => void perform(() => vinAdminApi.eligibility(account.id, false), 'Đã tắt điều kiện dùng AI.')}>Tắt điều kiện AI</Button></div>)}</section>
			</TabsContent>}
			{catalog && <><TabsContent value="catalog" className="space-y-8"><CatalogEditor entry={entry} setEntry={setEntry} perform={perform} busy={busy} onPublished={setCatalogId} />
				<section className="space-y-3"><h2 className="font-semibold">Catalog được cấp cho tài khoản quản trị này</h2><p className="text-sm text-muted-foreground">Danh sách hiện tại chỉ gồm tài nguyên đang hoạt động mà bạn được cấp xem; chưa phải toàn bộ catalog quản trị.</p>
					<div className="flex flex-wrap gap-3"><select aria-label="Loại catalog xem" className={options + ' max-w-48'} value={kind} onChange={(event) => setKind(event.target.value)}>{['credential', 'agent', 'knowledge_base', 'mcp', 'skill'].map((value) => <option key={value}>{value}</option>)}</select><select aria-label="Môi trường catalog xem" className={options + ' max-w-48'} value={environment} onChange={(event) => setEnvironment(event.target.value)}><option value="production">Production</option><option value="sandbox">Sandbox</option></select></div>
					{visible.isError && <p role="alert">Chưa tải được catalog.</p>}{visible.data?.items.map((item) => <div key={item.catalog_id} className="flex flex-wrap items-center justify-between gap-3 border-b py-3 text-sm"><span>{item.name} · v{item.version} · {item.resource_id}</span><Button variant="outline" size="sm" onClick={() => choose(item)}>Chuẩn bị phiên bản kế tiếp</Button></div>)}
				</section></TabsContent><TabsContent value="access"><AccessEditor catalogId={catalogId} setCatalogId={setCatalogId} perform={perform} busy={busy} /></TabsContent>
				<TabsContent value="knowledge" className="space-y-4"><h2 className="font-semibold">Thư viện KB Vin</h2><p className="text-sm text-muted-foreground">Tạo, nhập tài liệu và kiểm tra trạng thái index tại trang Knowledge hiện có; sau đó đưa KB được duyệt vào catalog và cấp quyền đọc/dùng.</p><Button asChild variant="outline"><Link to="/knowledge">Mở Knowledge</Link></Button>
					{knowledge.isError && <p role="alert">Chưa tải được Knowledge.</p>}{knowledge.data?.map((kb) => <div key={kb.id} className="flex flex-wrap justify-between gap-3 border-b py-3 text-sm"><span>{kb.name} · {kb.id} · {kb.status_counts.ready} tài liệu sẵn sàng / {kb.status_counts.error} lỗi</span><Button size="sm" variant="outline" disabled={kb.editable === false} onClick={() => { setEntry({ ...emptyEntry(''), kind: 'knowledge_base', resource_id: kb.id, name: kb.name, description: kb.description }); setTab('catalog'); }}>Chuẩn bị KB vào catalog</Button></div>)}
				</TabsContent></>}
		</Tabs>
	</section>;
}
