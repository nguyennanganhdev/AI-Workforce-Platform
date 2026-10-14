import { Check, LogOut, Plus, ShieldCheck, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { adminApi } from '@/api/admin';
import type { AdminAccount, DirectoryDomain } from '@/api/admin';
import type { AuthUser } from '@/api/auth';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const ROLE_LABEL: Record<string, string> = {
	PLATFORM_ADMIN: 'Quản trị platform',
	DOMAIN_ADMIN: 'Quản trị domain',
	AREA_MANAGER: 'BQL khu',
};

function errorText(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
	return (
		<section className="space-y-3 rounded-[22px] bg-card p-5 shadow-panel">
			<div>
				<h2 className="text-base font-medium">{title}</h2>
				{hint && <p className="text-xs text-muted-foreground">{hint}</p>}
			</div>
			{children}
		</section>
	);
}

export function AdminPage({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
	const platform = user.role === 'PLATFORM_ADMIN';
	const [pending, setPending] = useState<AdminAccount[]>([]);
	const [directory, setDirectory] = useState<DirectoryDomain[]>([]);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState<string | null>(null);
	const [domainForm, setDomainForm] = useState({ id: '', name: '' });
	const [areaForm, setAreaForm] = useState({ domain: user.domain_id ?? '', id: '', name: '' });
	const [adminForm, setAdminForm] = useState({ email: '', username: '', password: '', domain_id: '' });

	const load = useCallback(async () => {
		try {
			const [accounts, domains] = await Promise.all([adminApi.accounts('pending'), adminApi.directory()]);
			setPending(accounts);
			setDirectory(domains);
		} catch (error) {
			toast.error(errorText(error));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		load();
	}, [load]);

	const run = async (label: string, task: () => Promise<unknown>, done: string) => {
		setBusy(label);
		try {
			await task();
			toast.success(done);
			await load();
			return true;
		} catch (error) {
			toast.error(errorText(error));
			return false;
		} finally {
			setBusy(null);
		}
	};

	if (loading) {
		return (
			<div className="flex min-h-screen items-center justify-center">
				<Spinner />
			</div>
		);
	}

	return (
		<div className="min-h-screen space-y-4 bg-canvas p-6">
			<header className="flex flex-wrap items-center gap-3">
				<ShieldCheck className="size-5" />
				<h1 className="text-lg font-medium">Quản trị platform</h1>
				<Badge variant="outline">{ROLE_LABEL[user.role] ?? user.role}</Badge>
				{user.domain_id && <Badge variant="secondary">Domain {user.domain_id}</Badge>}
				<span className="ml-auto text-sm text-muted-foreground">{user.username}</span>
				<Button size="sm" variant="ghost" onClick={onLogout}>
					<LogOut /> Đăng xuất
				</Button>
			</header>

			<Section
				title="Tài khoản BQL chờ duyệt"
				hint="Mỗi khu có đúng một tài khoản BQL. Duyệt xong, BQL đăng nhập và dùng platform cho khu của mình."
			>
				{pending.length === 0 ? (
					<p className="text-sm text-muted-foreground">Không có tài khoản nào chờ duyệt.</p>
				) : (
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Tài khoản</TableHead>
								<TableHead>Domain</TableHead>
								<TableHead>Khu</TableHead>
								<TableHead>Đăng ký lúc</TableHead>
								<TableHead />
							</TableRow>
						</TableHeader>
						<TableBody>
							{pending.map((account) => (
								<TableRow key={account.id}>
									<TableCell>
										<p className="font-medium">{account.username}</p>
										<p className="text-xs text-muted-foreground">{account.email}</p>
									</TableCell>
									<TableCell>{account.domain_id}</TableCell>
									<TableCell>{account.area_id}</TableCell>
									<TableCell className="text-xs">{new Date(account.created_at).toLocaleString('vi-VN')}</TableCell>
									<TableCell className="space-x-1 text-right">
										<Button
											size="sm"
											disabled={busy !== null}
											onClick={() => run(`approve-${account.id}`, () => adminApi.approve(account.id), `Đã duyệt ${account.username}.`)}
										>
											<Check /> Duyệt
										</Button>
										<Button
											size="sm"
											variant="ghost"
											disabled={busy !== null}
											onClick={() => run(`reject-${account.id}`, () => adminApi.reject(account.id), `Đã từ chối ${account.username}.`)}
										>
											<X /> Từ chối
										</Button>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				)}
			</Section>

			<Section title="Domain và khu" hint="Domain là một đối tác tích hợp (ví dụ Vinhomes); khu là nơi một BQL quản lý.">
				<div className="space-y-3">
					{directory.map((domain) => (
						<div key={domain.id} className="rounded-xl border border-border/70 p-3">
							<div className="flex items-center gap-2">
								<p className="font-medium">{domain.name}</p>
								<Badge variant="outline">{domain.id}</Badge>
								{domain.status !== 'active' && <Badge variant="secondary">{domain.status}</Badge>}
							</div>
							<div className="mt-2 grid gap-1 text-sm md:grid-cols-2">
								{domain.areas.map((area) => (
									<div key={area.id} className="flex items-center gap-2">
										<span>{area.name}</span>
										<span className="text-xs text-muted-foreground">({area.id})</span>
										{area.managers.map((manager) => (
											<Badge key={manager.id} variant={manager.status === 'active' ? 'default' : 'secondary'}>
												BQL {manager.username} · {manager.status === 'active' ? 'đang hoạt động' : 'chờ duyệt'}
											</Badge>
										))}
										{area.managers.length === 0 && <Badge variant="outline">chưa có BQL</Badge>}
										{area.managers.length > 1 && (
											<Badge variant="destructive">nhiều BQL (tạo trước quy tắc một BQL/khu)</Badge>
										)}
									</div>
								))}
								{domain.areas.length === 0 && <p className="text-xs text-muted-foreground">Chưa có khu.</p>}
							</div>
						</div>
					))}
				</div>
				<div className="grid gap-2 md:grid-cols-4">
					<select
						className="h-9 rounded-md border bg-background px-2 text-sm"
						value={areaForm.domain}
						disabled={!platform}
						onChange={(event) => setAreaForm({ ...areaForm, domain: event.target.value })}
					>
						<option value="">Chọn domain</option>
						{directory.map((domain) => (
							<option key={domain.id} value={domain.id}>
								{domain.name}
							</option>
						))}
					</select>
					<Input placeholder="Mã khu (vd: ocean-park-3)" value={areaForm.id} onChange={(event) => setAreaForm({ ...areaForm, id: event.target.value })} />
					<Input placeholder="Tên khu" value={areaForm.name} onChange={(event) => setAreaForm({ ...areaForm, name: event.target.value })} />
					<Button
						disabled={busy !== null || !areaForm.domain || !areaForm.id || !areaForm.name}
						onClick={async () => {
							if (await run('area', () => adminApi.saveArea(areaForm.domain, areaForm.id.trim(), areaForm.name.trim()), 'Đã lưu khu.')) {
								setAreaForm({ ...areaForm, id: '', name: '' });
							}
						}}
					>
						<Plus /> Thêm khu
					</Button>
				</div>
				{platform && (
					<div className="grid gap-2 md:grid-cols-4">
						<Input placeholder="Mã domain (vd: vinhomes)" value={domainForm.id} onChange={(event) => setDomainForm({ ...domainForm, id: event.target.value })} />
						<Input placeholder="Tên domain" value={domainForm.name} onChange={(event) => setDomainForm({ ...domainForm, name: event.target.value })} />
						<Button
							variant="outline"
							disabled={busy !== null || !domainForm.id || !domainForm.name}
							onClick={async () => {
								if (await run('domain', () => adminApi.saveDomain(domainForm.id.trim(), domainForm.name.trim()), 'Đã lưu domain.')) {
									setDomainForm({ id: '', name: '' });
								}
							}}
						>
							<Plus /> Thêm domain
						</Button>
					</div>
				)}
			</Section>

			{platform && (
				<Section title="Quản trị domain" hint="Mỗi domain tích hợp có một người quản trị: thêm khu và duyệt BQL trong domain đó.">
					<div className="grid gap-2 md:grid-cols-5">
						<Input placeholder="Email" value={adminForm.email} onChange={(event) => setAdminForm({ ...adminForm, email: event.target.value })} />
						<Input placeholder="Tên đăng nhập" value={adminForm.username} onChange={(event) => setAdminForm({ ...adminForm, username: event.target.value })} />
						<Input
							type="password"
							placeholder="Mật khẩu (≥ 12 ký tự)"
							value={adminForm.password}
							onChange={(event) => setAdminForm({ ...adminForm, password: event.target.value })}
						/>
						<select
							className="h-9 rounded-md border bg-background px-2 text-sm"
							value={adminForm.domain_id}
							onChange={(event) => setAdminForm({ ...adminForm, domain_id: event.target.value })}
						>
							<option value="">Chọn domain</option>
							{directory.map((domain) => (
								<option key={domain.id} value={domain.id}>
									{domain.name}
								</option>
							))}
						</select>
						<Button
							disabled={busy !== null || !adminForm.email || !adminForm.username || adminForm.password.length < 12 || !adminForm.domain_id}
							onClick={async () => {
								if (await run('domain-admin', () => adminApi.createDomainAdmin(adminForm), 'Đã tạo quản trị domain.')) {
									setAdminForm({ email: '', username: '', password: '', domain_id: '' });
								}
							}}
						>
							<Plus /> Tạo
						</Button>
					</div>
				</Section>
			)}
		</div>
	);
}
