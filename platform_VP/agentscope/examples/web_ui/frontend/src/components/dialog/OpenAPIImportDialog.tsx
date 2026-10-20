import { CircleAlert, FileCode2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { mcpApi } from '@/api';
import { ApiError } from '@/api/client';
import type { OpenAPIImportRequest, OpenAPIPreview } from '@/api/types';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onInstalled: () => void;
}

type AuthType = OpenAPIImportRequest['auth_type'];

const SELECT_CLASS =
	'h-8 rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50';

function slug(text: string): string {
	return text
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '_')
		.replace(/^_+|_+$/g, '')
		.slice(0, 40);
}

export function OpenAPIImportDialog({ open, onOpenChange, onInstalled }: Props) {
	const [specUrl, setSpecUrl] = useState('');
	const [specText, setSpecText] = useState('');
	const [preview, setPreview] = useState<OpenAPIPreview | null>(null);
	const [selected, setSelected] = useState<Set<string>>(new Set());
	const [name, setName] = useState('');
	const [displayName, setDisplayName] = useState('');
	const [baseUrl, setBaseUrl] = useState('');
	const [authType, setAuthType] = useState<AuthType>('none');
	const [authName, setAuthName] = useState('');
	const [authValue, setAuthValue] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!open) return;
		setError(null);
	}, [open]);

	const reset = () => {
		setSpecUrl('');
		setSpecText('');
		setPreview(null);
		setSelected(new Set());
		setName('');
		setDisplayName('');
		setBaseUrl('');
		setAuthType('none');
		setAuthName('');
		setAuthValue('');
	};

	const source = () => ({
		spec_url: specUrl.trim() || null,
		spec_text: specText.trim() || null,
	});

	const read = async () => {
		setBusy(true);
		setError(null);
		try {
			const result = await mcpApi.previewOpenAPI(source());
			setPreview(result);
			setSelected(new Set(result.operations.slice(0, result.max_operations).map((op) => op.name)));
			setBaseUrl(result.base_urls[0] ?? '');
			setDisplayName((current) => current || result.title);
			setName((current) => current || slug(result.title) || 'partner_api');
		} catch (value) {
			setError(value instanceof ApiError ? value.detail : (value as Error).message);
		} finally {
			setBusy(false);
		}
	};

	const create = async () => {
		setBusy(true);
		setError(null);
		try {
			const installed = await mcpApi.importOpenAPI({
				...source(),
				name,
				display_name: displayName || null,
				base_url: baseUrl,
				operations: [...selected],
				auth_type: authType,
				auth_name: authName,
				auth_value: authValue || null,
			});
			onInstalled();
			onOpenChange(false);
			reset();
			if (installed.last_sync_error) {
				toast.warning(`Đã tạo ${installed.display_name}, nhưng kiểm tra kết nối lỗi: ${installed.last_sync_error}`);
			} else {
				toast.success(`Đã tạo ${installed.tools.length} tool từ ${installed.display_name}.`);
			}
		} catch (value) {
			setError(value instanceof ApiError ? value.detail : (value as Error).message);
		} finally {
			setBusy(false);
		}
	};

	const toggle = (opName: string, on: boolean) => {
		setSelected((current) => {
			const next = new Set(current);
			if (on) next.add(opName);
			else next.delete(opName);
			return next;
		});
	};

	const operations = preview?.operations ?? [];
	const tooMany = preview !== null && selected.size > preview.max_operations;
	const needsAuthName = authType === 'header' || authType === 'query';
	const canCreate =
		preview !== null &&
		selected.size > 0 &&
		!tooMany &&
		Boolean(name) &&
		Boolean(baseUrl) &&
		(!needsAuthName || Boolean(authName.trim()));

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<div className="mb-1 flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
						<FileCode2 className="size-4" />
					</div>
					<DialogTitle>Nhập API từ OpenAPI</DialogTitle>
					<DialogDescription>
						Dành cho đối tác có API nhưng không có MCP. Mỗi endpoint bạn chọn sẽ thành một tool
						cho agent; platform gọi API thay agent. API key được lưu ẩn và không hiển thị lại.
					</DialogDescription>
				</DialogHeader>

				<div className="grid gap-3">
					<div className="grid gap-2">
						<Label htmlFor="openapi-url">Link OpenAPI / Swagger (JSON hoặc YAML)</Label>
						<Input
							id="openapi-url"
							type="url"
							value={specUrl}
							onChange={(event) => setSpecUrl(event.target.value)}
							placeholder="https://api.partner.com/openapi.json"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor="openapi-text">Hoặc dán nội dung spec</Label>
						<Textarea
							id="openapi-text"
							value={specText}
							onChange={(event) => setSpecText(event.target.value)}
							placeholder='{"openapi": "3.0.0", ...}'
							className="max-h-40 min-h-16 font-mono text-xs"
						/>
					</div>
					<div>
						<Button variant="outline" onClick={read} disabled={busy || (!specUrl.trim() && !specText.trim())}>
							{busy && !preview ? <Spinner /> : <FileCode2 />}
							{preview ? 'Đọc lại spec' : 'Đọc spec'}
						</Button>
					</div>
				</div>

				{preview && (
					<div className="grid gap-4 border-t pt-4">
						<div className="grid gap-4 sm:grid-cols-2">
							<div className="grid gap-2">
								<Label htmlFor="openapi-name">Mã MCP</Label>
								<Input
									id="openapi-name"
									value={name}
									onChange={(event) => setName(event.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
								/>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="openapi-display">Tên hiển thị</Label>
								<Input
									id="openapi-display"
									value={displayName}
									onChange={(event) => setDisplayName(event.target.value)}
								/>
							</div>
							<div className="grid gap-2 sm:col-span-2">
								<Label htmlFor="openapi-base">Địa chỉ API (base URL)</Label>
								<Input
									id="openapi-base"
									type="url"
									list="openapi-base-urls"
									value={baseUrl}
									onChange={(event) => setBaseUrl(event.target.value)}
									placeholder="https://api.partner.com/v1"
								/>
								<datalist id="openapi-base-urls">
									{preview.base_urls.map((url) => (
										<option key={url} value={url} />
									))}
								</datalist>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="openapi-auth">Xác thực</Label>
								<select
									id="openapi-auth"
									value={authType}
									onChange={(event) => setAuthType(event.target.value as AuthType)}
									className={SELECT_CLASS}
								>
									<option value="none">Không cần</option>
									<option value="bearer">Bearer token</option>
									<option value="header">API key trong header</option>
									<option value="query">API key trong query</option>
								</select>
							</div>
							{needsAuthName && (
								<div className="grid gap-2">
									<Label htmlFor="openapi-auth-name">
										{authType === 'header' ? 'Tên header' : 'Tên tham số'}
									</Label>
									<Input
										id="openapi-auth-name"
										value={authName}
										onChange={(event) => setAuthName(event.target.value)}
										placeholder={authType === 'header' ? 'X-API-Key' : 'api_key'}
									/>
								</div>
							)}
							{authType !== 'none' && (
								<div className="grid gap-2 sm:col-span-2">
									<Label htmlFor="openapi-auth-value">API key / token</Label>
									<Input
										id="openapi-auth-value"
										type="password"
										autoComplete="new-password"
										value={authValue}
										onChange={(event) => setAuthValue(event.target.value)}
										placeholder="••••••••••••"
									/>
								</div>
							)}
						</div>

						<div className="grid gap-2">
							<div className="flex items-center justify-between gap-2">
								<Label>
									Endpoint thành tool · đã chọn {selected.size}/{operations.length}
								</Label>
								<div className="flex gap-1">
									<Button
										size="sm"
										variant="ghost"
										onClick={() =>
											setSelected(new Set(operations.slice(0, preview.max_operations).map((op) => op.name)))
										}
									>
										Chọn hết
									</Button>
									<Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
										Bỏ chọn
									</Button>
								</div>
							</div>
							<div className="max-h-64 overflow-y-auto rounded-lg border">
								{operations.map((op) => (
									<label
										key={op.name}
										className="flex cursor-pointer items-start gap-2.5 border-b px-3 py-2 last:border-b-0 hover:bg-muted/40"
									>
										<Checkbox
											className="mt-0.5"
											checked={selected.has(op.name)}
											onCheckedChange={(value) => toggle(op.name, value === true)}
										/>
										<span className="min-w-0">
											<span className="block font-mono text-xs">
												<span className="font-semibold">{op.method}</span> {op.path}
											</span>
											<span className="line-clamp-1 text-xs text-muted-foreground">
												{op.description}
											</span>
										</span>
									</label>
								))}
								{operations.length === 0 && (
									<p className="px-3 py-4 text-sm text-muted-foreground">Spec không có endpoint nào dùng được.</p>
								)}
							</div>
							{tooMany && (
								<p className="text-xs text-destructive">
									Chọn tối đa {preview.max_operations} endpoint để agent không bị quá tải tool.
								</p>
							)}
							{preview.skipped.length > 0 && (
								<p className="text-xs text-muted-foreground">
									Bỏ qua {preview.skipped.length} endpoint gửi file/multipart: {preview.skipped.slice(0, 3).join(', ')}
									{preview.skipped.length > 3 ? '…' : ''}
								</p>
							)}
						</div>
					</div>
				)}

				{error && (
					<Alert variant="destructive">
						<CircleAlert />
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				)}

				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)}>
						Hủy
					</Button>
					<Button onClick={create} disabled={busy || !canCreate}>
						{busy && preview ? <Spinner /> : <FileCode2 />}
						Tạo MCP từ API
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
