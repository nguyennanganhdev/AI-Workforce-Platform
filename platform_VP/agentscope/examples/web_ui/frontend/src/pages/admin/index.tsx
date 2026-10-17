import { Check, LogOut, MapPinned, Network, Plus, Search, ShieldCheck, UserCheck, UserPlus, X } from 'lucide-react';
import { type ComponentType, type CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { adminApi } from '@/api/admin';
import type { AdminAccount, DirectoryArea, DirectoryDomain } from '@/api/admin';
import type { AuthUser } from '@/api/auth';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from '@/components/ui/dialog';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuBadge,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarProvider,
	SidebarTrigger,
	useSidebar,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCueTheme } from '@/hooks/useCueTheme';

function errorText(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

function when(value: string | null): string {
	return value ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : 'Chưa đăng nhập';
}

/** A small form in a dialog; ``submit`` resolves true when the dialog may close. */
function FormDialog({
	trigger,
	title,
	description,
	fields,
	submitLabel,
	onSubmit,
}: {
	trigger: React.ReactNode;
	title: string;
	description: string;
	fields: { name: string; label: string; type?: string; hint?: string; options?: { value: string; label: string }[] }[];
	submitLabel: string;
	onSubmit: (values: Record<string, string>) => Promise<boolean>;
}) {
	const empty = Object.fromEntries(fields.map((field) => [field.name, field.options?.[0]?.value ?? '']));
	const [open, setOpen] = useState(false);
	const [values, setValues] = useState<Record<string, string>>(empty);
	const [saving, setSaving] = useState(false);
	const complete = fields.every((field) => values[field.name]?.trim());
	return (
		<Dialog
			open={open}
			onOpenChange={(next) => {
				setOpen(next);
				if (next) setValues(empty);
			}}
		>
			<DialogTrigger asChild>{trigger}</DialogTrigger>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{title}</DialogTitle>
					<DialogDescription>{description}</DialogDescription>
				</DialogHeader>
				<form
					className="space-y-4"
					onSubmit={async (event) => {
						event.preventDefault();
						setSaving(true);
						const done = await onSubmit(values);
						setSaving(false);
						if (done) setOpen(false);
					}}
				>
					{fields.map((field) => (
						<div key={field.name} className="grid gap-2">
							<Label htmlFor={`f-${field.name}`}>{field.label}</Label>
							{field.options ? (
								<select
									id={`f-${field.name}`}
									className="h-9 rounded-md border bg-background px-2 text-sm"
									value={values[field.name]}
									onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
								>
									{field.options.map((option) => (
										<option key={option.value} value={option.value}>
											{option.label}
										</option>
									))}
								</select>
							) : (
								<Input
									id={`f-${field.name}`}
									type={field.type ?? 'text'}
									value={values[field.name]}
									onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
								/>
							)}
							{field.hint && <p className="text-xs text-muted-foreground">{field.hint}</p>}
						</div>
					))}
					<DialogFooter>
						<Button type="submit" disabled={!complete || saving}>
							{submitLabel}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}

function AreaTable({ areas, accounts }: { areas: DirectoryArea[]; accounts: Map<string, AdminAccount> }) {
	if (areas.length === 0) {
		return <p className="py-6 text-center text-sm text-muted-foreground">Không có khu nào khớp.</p>;
	}
	return (
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead>Khu</TableHead>
					<TableHead>Tài khoản BQL</TableHead>
					<TableHead>Trạng thái</TableHead>
					<TableHead>Đăng nhập gần nhất</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{areas.map((area) => (
					<TableRow key={area.id}>
						<TableCell>
							<p className="font-medium">{area.name}</p>
							<p className="text-xs text-muted-foreground">{area.id}</p>
						</TableCell>
						{area.managers.length === 0 ? (
							<TableCell colSpan={3} className="text-sm text-muted-foreground">
								Chưa có BQL. BQL của khu tự đăng ký, rồi chờ duyệt ở trên.
							</TableCell>
						) : (
							<>
								<TableCell>
									{area.managers.map((manager) => (
										<div key={manager.id}>
											<p className="font-medium">{manager.username}</p>
											<p className="text-xs text-muted-foreground">{accounts.get(manager.id)?.email}</p>
										</div>
									))}
									{area.managers.length > 1 && (
										<p className="mt-1 text-xs text-destructive">Khu có nhiều BQL: chỉ giữ một tài khoản.</p>
									)}
								</TableCell>
								<TableCell>
									{area.managers.map((manager) =>
										manager.status === 'active' ? (
											<Badge key={manager.id} variant="secondary">Đang hoạt động</Badge>
										) : (
											<Badge key={manager.id} variant="outline">Chờ duyệt</Badge>
										),
									)}
								</TableCell>
								<TableCell className="text-sm text-muted-foreground">
									{area.managers.map((manager) => (
										<p key={manager.id}>{when(accounts.get(manager.id)?.last_login_at ?? null)}</p>
									))}
								</TableCell>
							</>
						)}
					</TableRow>
				))}
			</TableBody>
		</Table>
	);
}

type Section = 'areas' | 'pending' | 'admins';

/** One admin page: a title, what it is for, its actions, then its content. */
function Page({ title, hint, action, children }: { title: string; hint: string; action?: React.ReactNode; children: React.ReactNode }) {
	return (
		<main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
			<div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3 pb-3">
				<div className="min-w-0">
					<h1 className="text-[17px]/6 font-semibold">{title}</h1>
					<p className="mt-0.5 text-[13px]/[18px] text-muted-foreground">{hint}</p>
				</div>
				{action}
			</div>
			<Separator />
			<div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">{children}</div>
		</main>
	);
}

/** Figures in a row, no boxes: the number carries the weight. */
function Figures({ items }: { items: { label: string; value: number; warn?: boolean }[] }) {
	return (
		<dl className="flex flex-wrap gap-x-10 gap-y-3 py-4">
			{items.map((item) => (
				<div key={item.label}>
					<dt className="text-[13px]/[18px] text-muted-foreground">{item.label}</dt>
					<dd
						className={`text-2xl font-semibold tabular-nums ${item.warn && item.value > 0 ? 'text-amber-600 dark:text-amber-400' : ''}`}
					>
						{item.value}
					</dd>
				</div>
			))}
		</dl>
	);
}

/** A Cue nav row, as in the settings sidebar. */
const ITEM =
	'h-10 gap-3 rounded-xl px-3 text-[15px]/5 [&_svg]:size-[18px] group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span]:sr-only';

function AdminSidebar({
	user,
	title,
	items,
	section,
	onSection,
	onLogout,
}: {
	user: AuthUser;
	title: string;
	items: { key: Section; label: string; icon: ComponentType; count?: number }[];
	section: Section;
	onSection: (section: Section) => void;
	onLogout: () => void;
}) {
	const { isMobile, setOpenMobile } = useSidebar();
	return (
		<Sidebar collapsible={isMobile ? 'offcanvas' : 'icon'} className="cue-column border-r border-sidebar-border">
			<SidebarHeader className="h-12 shrink-0 justify-center px-4 py-0 group-data-[collapsible=icon]:px-2">
				<p className="truncate text-[15px]/5 font-semibold group-data-[collapsible=icon]:sr-only">{title}</p>
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup className="px-2 py-1">
					<SidebarGroupContent>
						<SidebarMenu>
							{items.map((item) => (
								<SidebarMenuItem key={item.key}>
									<SidebarMenuButton
										className={ITEM}
										isActive={section === item.key}
										tooltip={item.label}
										onClick={() => {
											onSection(item.key);
											setOpenMobile(false);
										}}
									>
										<item.icon />
										<span>{item.label}</span>
									</SidebarMenuButton>
									{item.count ? <SidebarMenuBadge>{item.count}</SidebarMenuBadge> : null}
								</SidebarMenuItem>
							))}
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter className="border-t border-sidebar-border p-2">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<button
							type="button"
							title={user.username}
							className="flex h-12 w-full items-center gap-3 rounded-xl px-2 hover:bg-[var(--cue-bg-hover,var(--accent))] group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
						>
							<span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--cue-avatar-user,#e5484d)] text-[15px] font-medium text-white">
								{user.username.charAt(0).toUpperCase()}
							</span>
							<span className="min-w-0 flex-1 truncate text-left text-[15px]/5 group-data-[collapsible=icon]:hidden">
								{user.username}
							</span>
						</button>
					</DropdownMenuTrigger>
					<DropdownMenuContent side="right" align="end" className="w-auto min-w-48">
						<DropdownMenuLabel className="font-normal text-muted-foreground">{user.username}</DropdownMenuLabel>
						<DropdownMenuSeparator />
						<DropdownMenuItem variant="destructive" onClick={onLogout}>
							<LogOut /> Đăng xuất
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</SidebarFooter>
		</Sidebar>
	);
}

export function AdminPage({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
	useCueTheme();
	const platform = user.role === 'PLATFORM_ADMIN';
	const [accounts, setAccounts] = useState<AdminAccount[]>([]);
	const [directory, setDirectory] = useState<DirectoryDomain[]>([]);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState<string | null>(null);
	const [query, setQuery] = useState('');
	const [section, setSection] = useState<Section>('areas');

	const load = useCallback(async () => {
		try {
			const [all, domains] = await Promise.all([adminApi.accounts(), adminApi.directory()]);
			setAccounts(all);
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

	const byId = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts]);
	const pending = accounts.filter((account) => account.role === 'AREA_MANAGER' && account.status === 'pending');
	const domainAdmins = accounts.filter((account) => account.role === 'DOMAIN_ADMIN');
	const areas = directory.flatMap((domain) => domain.areas);
	const ownDomain = directory.find((domain) => domain.id === user.domain_id);
	const domainOptions = directory.map((domain) => ({ value: domain.id, label: domain.name }));
	const match = (area: DirectoryArea) => {
		const text = query.trim().toLowerCase();
		if (!text) return true;
		const people = area.managers.map((manager) => `${manager.username} ${byId.get(manager.id)?.email ?? ''}`).join(' ');
		return `${area.name} ${area.id} ${people}`.toLowerCase().includes(text);
	};

	const addArea = (domainId?: string) => (
		<FormDialog
			trigger={
				<Button size="sm" variant="outline" disabled={busy !== null}>
					<Plus /> Thêm khu
				</Button>
			}
			title="Thêm khu"
			description="Khu là nơi một BQL quản lý. Sau khi thêm, BQL của khu tự đăng ký và chờ duyệt."
			fields={[
				...(domainId ? [] : [{ name: 'domain', label: 'Domain', options: domainOptions }]),
				{ name: 'id', label: 'Mã khu', hint: 'Chữ thường, không dấu, ví dụ ocean-park-3.' },
				{ name: 'name', label: 'Tên khu' },
			]}
			submitLabel="Thêm khu"
			onSubmit={(values) =>
				run('area', () => adminApi.saveArea(domainId ?? values.domain, values.id.trim(), values.name.trim()), 'Đã thêm khu.')
			}
		/>
	);

	const search = (
		<div className="relative w-full sm:w-64">
			<Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
			<Input
				className="pl-8"
				placeholder="Tìm khu, BQL, email"
				value={query}
				onChange={(event) => setQuery(event.target.value)}
			/>
		</div>
	);

	const figures = [
		...(platform ? [{ label: 'Domain', value: directory.length }] : []),
		{ label: 'Khu', value: areas.length },
		{ label: 'BQL đang hoạt động', value: areas.flatMap((area) => area.managers).filter((m) => m.status === 'active').length },
		{ label: 'Chờ duyệt', value: pending.length, warn: true },
		{ label: 'Khu chưa có BQL', value: areas.filter((area) => area.managers.length === 0).length, warn: true },
	];

	const items: { key: Section; label: string; icon: ComponentType; count?: number }[] = [
		{ key: 'areas', label: platform ? 'Domain, khu và BQL' : 'Khu và BQL', icon: platform ? Network : MapPinned },
		{ key: 'pending', label: 'BQL chờ duyệt', icon: UserCheck, count: pending.length },
		...(platform ? [{ key: 'admins' as const, label: 'Quản trị domain', icon: ShieldCheck }] : []),
	];

	const content = loading ? (
		<main className="flex-1 space-y-4 p-4">
			<Skeleton className="h-10 w-72" />
			<Skeleton className="h-16 w-full" />
			<Skeleton className="h-64 w-full" />
		</main>
	) : section === 'pending' ? (
		<Page title="BQL chờ duyệt" hint="Mỗi khu có đúng một BQL. Duyệt xong, BQL đăng nhập và dùng platform cho khu của mình.">
			{pending.length === 0 ? (
				<Empty className="border-none">
					<EmptyHeader>
						<EmptyMedia variant="icon">
							<UserCheck />
						</EmptyMedia>
						<EmptyTitle>Không có tài khoản chờ duyệt</EmptyTitle>
						<EmptyDescription>BQL của một khu tự đăng ký; tài khoản mới hiện ở đây để bạn duyệt.</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Tài khoản</TableHead>
							<TableHead>Khu</TableHead>
							<TableHead>Đăng ký lúc</TableHead>
							<TableHead />
						</TableRow>
					</TableHeader>
					<TableBody>
						{pending.map((account) => {
							const area = areas.find((item) => item.domain_id === account.domain_id && item.id === account.area_id);
							return (
								<TableRow key={account.id}>
									<TableCell>
										<p className="font-medium">{account.username}</p>
										<p className="text-xs text-muted-foreground">{account.email}</p>
									</TableCell>
									<TableCell>
										{area?.name ?? account.area_id}
										{platform && <p className="text-xs text-muted-foreground">{account.domain_id}</p>}
									</TableCell>
									<TableCell className="text-sm text-muted-foreground">{when(account.created_at)}</TableCell>
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
							);
						})}
					</TableBody>
				</Table>
			)}
		</Page>
	) : section === 'admins' ? (
		<Page
			title="Quản trị domain"
			hint="Mỗi domain có người quản trị riêng: thêm khu và duyệt BQL trong domain đó, không thấy domain khác."
			action={
				<FormDialog
					trigger={
						<Button size="sm" disabled={busy !== null || directory.length === 0}>
							<UserPlus /> Tạo quản trị domain
						</Button>
					}
					title="Tạo quản trị domain"
					description="Tài khoản này chỉ quản lý khu và BQL của domain được chọn."
					fields={[
						{ name: 'domain_id', label: 'Domain', options: domainOptions },
						{ name: 'email', label: 'Email', type: 'email' },
						{ name: 'username', label: 'Tên đăng nhập' },
						{ name: 'password', label: 'Mật khẩu', type: 'password', hint: 'Tối thiểu 12 ký tự.' },
					]}
					submitLabel="Tạo tài khoản"
					onSubmit={async (values) => {
						if (values.password.length < 12) {
							toast.error('Mật khẩu cần tối thiểu 12 ký tự.');
							return false;
						}
						const body = {
							email: values.email.trim(),
							username: values.username.trim(),
							password: values.password,
							domain_id: values.domain_id,
						};
						return run('domain-admin', () => adminApi.createDomainAdmin(body), 'Đã tạo quản trị domain.');
					}}
				/>
			}
		>
			{domainAdmins.length === 0 ? (
				<p className="py-6 text-center text-sm text-muted-foreground">Chưa có quản trị domain nào.</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Tài khoản</TableHead>
							<TableHead>Domain</TableHead>
							<TableHead>Đăng nhập gần nhất</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{domainAdmins.map((admin) => (
							<TableRow key={admin.id}>
								<TableCell>
									<p className="font-medium">{admin.username}</p>
									<p className="text-xs text-muted-foreground">{admin.email}</p>
								</TableCell>
								<TableCell>{directory.find((domain) => domain.id === admin.domain_id)?.name ?? admin.domain_id}</TableCell>
								<TableCell className="text-sm text-muted-foreground">{when(admin.last_login_at)}</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			)}
		</Page>
	) : platform ? (
		<Page
			title="Domain, khu và BQL"
			hint="Domain là một đối tác tích hợp (ví dụ Vinhomes). Mỗi khu trong domain có một BQL."
			action={
				<div className="flex flex-wrap items-center gap-2">
					{search}
					<FormDialog
						trigger={
							<Button size="sm" variant="outline" disabled={busy !== null}>
								<Plus /> Thêm domain
							</Button>
						}
						title="Thêm domain"
						description="Một đối tác tích hợp mới. Sau đó tạo quản trị domain và các khu của nó."
						fields={[
							{ name: 'id', label: 'Mã domain', hint: 'Chữ thường, không dấu, ví dụ vinhomes.' },
							{ name: 'name', label: 'Tên domain' },
						]}
						submitLabel="Thêm domain"
						onSubmit={(values) => run('domain', () => adminApi.saveDomain(values.id.trim(), values.name.trim()), 'Đã thêm domain.')}
					/>
				</div>
			}
		>
			<Figures items={figures} />
			{directory.length === 0 ? (
				<p className="py-6 text-center text-sm text-muted-foreground">Chưa có domain nào. Thêm domain đầu tiên.</p>
			) : (
				<Tabs defaultValue={directory[0].id}>
					<TabsList className="flex-wrap">
						{directory.map((domain) => (
							<TabsTrigger key={domain.id} value={domain.id}>
								{domain.name}
								<span className="ml-1.5 text-xs text-muted-foreground tabular-nums">{domain.areas.length}</span>
							</TabsTrigger>
						))}
					</TabsList>
					{directory.map((domain) => {
						const admins = domainAdmins.filter((admin) => admin.domain_id === domain.id);
						return (
							<TabsContent key={domain.id} value={domain.id} className="space-y-3 pt-2">
								<div className="flex flex-wrap items-center gap-2 text-sm">
									<span className="text-muted-foreground">Quản trị domain:</span>
									{admins.length === 0 ? (
										<span className="text-muted-foreground">chưa có</span>
									) : (
										admins.map((admin) => (
											<Badge key={admin.id} variant="secondary">
												{admin.username}
											</Badge>
										))
									)}
									<span className="ml-auto">{addArea(domain.id)}</span>
								</div>
								<AreaTable areas={domain.areas.filter(match)} accounts={byId} />
							</TabsContent>
						);
					})}
				</Tabs>
			)}
		</Page>
	) : (
		<Page
			title="Khu và BQL"
			hint="Mỗi khu có một BQL. Thêm khu mới, rồi BQL của khu tự đăng ký và chờ bạn duyệt."
			action={
				<div className="flex flex-wrap items-center gap-2">
					{search}
					{addArea(user.domain_id ?? undefined)}
				</div>
			}
		>
			<Figures items={figures} />
			<AreaTable areas={areas.filter(match)} accounts={byId} />
		</Page>
	);

	return (
		<SidebarProvider
			className="h-screen min-h-0 bg-canvas"
			open={false}
			style={{ '--sidebar-width': '16rem', '--sidebar-width-icon': '3.5rem' } as CSSProperties}
		>
			<AdminSidebar
				user={user}
				title={platform ? 'Quản trị platform' : `Quản trị ${ownDomain?.name ?? user.domain_id ?? 'domain'}`}
				items={items}
				section={section}
				onSection={setSection}
				onLogout={onLogout}
			/>
			<div className="flex min-w-0 flex-1 flex-col">
				{/* Mobile only: the one way to reach the drawer. */}
				<div className="flex h-12 shrink-0 items-center gap-2 px-2 md:hidden">
					<SidebarTrigger />
					<span className="text-[17px]/6 font-medium">Quản trị</span>
				</div>
				<div className="flex min-h-0 flex-1">{content}</div>
			</div>
		</SidebarProvider>
	);
}
