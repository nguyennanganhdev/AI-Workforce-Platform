import { CircleAlert, PlugZap } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { mcpApi } from '@/api';
import { ApiError } from '@/api/client';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onInstalled: () => void;
}

export function DirectMCPDialog({ open, onOpenChange, onInstalled }: Props) {
	const [name, setName] = useState('');
	const [displayName, setDisplayName] = useState('');
	const [url, setUrl] = useState('');
	const [apiKey, setApiKey] = useState('');
	const [authMode, setAuthMode] = useState<'bearer' | 'x-api-key'>('bearer');
	const [installing, setInstalling] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!open) return;
		setError(null);
	}, [open]);

	const install = async () => {
		setInstalling(true);
		setError(null);
		try {
			const installed = await mcpApi.installDirect({
				name,
				display_name: displayName || null,
				url,
				api_key: apiKey || null,
				auth_header: authMode === 'bearer' ? 'Authorization' : 'X-API-Key',
				auth_scheme: authMode === 'bearer' ? 'Bearer' : '',
			});
			onInstalled();
			onOpenChange(false);
			setName('');
			setDisplayName('');
			setUrl('');
			setApiKey('');
			toast.success(`Đã đăng ký ${installed.tools.length} tool từ MCP ${installed.display_name}.`);
		} catch (value) {
			setError(value instanceof ApiError ? value.detail : (value as Error).message);
		} finally {
			setInstalling(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<div className="mb-1 flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
						<PlugZap className="size-4" />
					</div>
					<DialogTitle>Kết nối MCP đối tác</DialogTitle>
					<DialogDescription>
						Platform sẽ kết nối thử, đọc danh sách tool rồi mới đăng ký. API Key không
						 được trả lại qua API hoặc hiển thị sau khi lưu.
					</DialogDescription>
				</DialogHeader>

				<div className="grid gap-4 py-1 sm:grid-cols-2">
					<div className="grid gap-2">
						<Label htmlFor="direct-mcp-name">Mã MCP</Label>
						<Input
							id="direct-mcp-name"
							value={name}
							onChange={(event) => setName(event.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
							placeholder="partner_hotel"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor="direct-mcp-display-name">Tên hiển thị</Label>
						<Input
							id="direct-mcp-display-name"
							value={displayName}
							onChange={(event) => setDisplayName(event.target.value)}
							placeholder="Hotel Partner"
						/>
					</div>
					<div className="grid gap-2 sm:col-span-2">
						<Label htmlFor="direct-mcp-url">MCP URL</Label>
						<Input
							id="direct-mcp-url"
							type="url"
							value={url}
							onChange={(event) => setUrl(event.target.value)}
							placeholder="https://partner.example.com/mcp"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor="direct-mcp-api-key">API Key</Label>
						<Input
							id="direct-mcp-api-key"
							type="password"
							autoComplete="new-password"
							value={apiKey}
							onChange={(event) => setApiKey(event.target.value)}
							placeholder="••••••••••••"
						/>
					</div>
					<div className="grid gap-2">
						<Label htmlFor="direct-mcp-auth">Kiểu xác thực</Label>
						<select
							id="direct-mcp-auth"
							value={authMode}
							onChange={(event) => setAuthMode(event.target.value as 'bearer' | 'x-api-key')}
							className="h-8 rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
						>
							<option value="bearer">Authorization: Bearer</option>
							<option value="x-api-key">X-API-Key</option>
						</select>
					</div>
				</div>

				{error && (
					<Alert variant="destructive">
						<CircleAlert />
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				)}

				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)}>Hủy</Button>
					<Button onClick={install} disabled={installing || !name || !url}>
						{installing ? <Spinner /> : <PlugZap />}
						Kiểm tra và cài đặt
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
