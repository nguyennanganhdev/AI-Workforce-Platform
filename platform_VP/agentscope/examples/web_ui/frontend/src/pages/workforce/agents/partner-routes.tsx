import { Cable } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { studioApi } from '@/api';
import type { PartnerRoute } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';

const STATUS = {
	pending_confirmation: 'Chờ đối tác xác nhận',
	active: 'Đang hoạt động',
	revoked: 'Đã thu hồi',
} as const;

/** Lets the area manager route a partner's tickets to their agents. */
export function PartnerRoutesDialog() {
	const [open, setOpen] = useState(false);
	const [routes, setRoutes] = useState<PartnerRoute[] | null>(null);
	const [unavailable, setUnavailable] = useState(false);
	const [clientId, setClientId] = useState('');
	const [reference, setReference] = useState('');

	const load = () =>
		studioApi
			.partnerRoutes()
			.then((items) => {
				setRoutes(items);
				setUnavailable(false);
			})
			.catch(() => setUnavailable(true));

	useEffect(() => {
		if (open) load();
	}, [open]);

	const grant = async () => {
		try {
			await studioApi.grantPartnerRoute(clientId.trim(), reference.trim());
			setClientId('');
			setReference('');
			toast.success('Đã cấp tuyến. Đối tác cần xác nhận bằng mã tuyến.');
			load();
		} catch (error) {
			toast.error(error instanceof Error ? error.message : String(error));
		}
	};

	return (
		<>
			<Button variant="outline" onClick={() => setOpen(true)}>
				<Cable /> Kết nối đối tác
			</Button>
			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent className="sm:max-w-2xl">
					<DialogHeader>
						<DialogTitle>Kết nối đối tác</DialogTitle>
						<DialogDescription>
							Cho ứng dụng của đối tác gửi ticket của khách đến các agent của bạn. Đối tác xác nhận tuyến bằng
							mã tuyến và số phiên bản bên dưới.
						</DialogDescription>
					</DialogHeader>
					{unavailable ? (
						<p className="text-sm text-muted-foreground">
							API đối tác chưa bật trên server (WORKFORCE_PARTNER_API=true) hoặc tài khoản chưa được xác minh là quản
							lý khu vực.
						</p>
					) : (
						<div className="space-y-4">
							<div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
								<Input value={clientId} placeholder="Mã client của đối tác" onChange={(e) => setClientId(e.target.value)} />
								<Input
									value={reference}
									placeholder="Mã toà/khu đối tác dùng (vd: tower-a)"
									onChange={(e) => setReference(e.target.value)}
								/>
								<Button onClick={grant} disabled={!clientId.trim() || !reference.trim()}>
									Cấp tuyến
								</Button>
							</div>
							<div className="space-y-2">
								{(routes ?? []).map((route) => (
									<div key={route.route_id} className="flex flex-wrap items-center gap-2 rounded-xl border p-3 text-sm">
										<Badge variant={route.status === 'active' ? 'default' : 'outline'}>{STATUS[route.status]}</Badge>
										<span>
											{route.partner_client_id} · {route.external_management_ref}
										</span>
										<span className="ml-auto font-mono text-xs text-muted-foreground">
											tuyến {route.route_id} · v{route.revision}
										</span>
									</div>
								))}
								{routes?.length === 0 && <p className="text-xs text-muted-foreground">Chưa có tuyến nào.</p>}
							</div>
						</div>
					)}
				</DialogContent>
			</Dialog>
		</>
	);
}
