import { CircleAlert, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { workforceApi } from '@/api';
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
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { formatApiErrorForAlert } from '@/lib/api-error';

const MAX_INSTRUCTIONS = 4000;

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/** The two things a platform user may tune on the fixed Leader. */
export function LeaderSettingsDialog({ open, onOpenChange }: Props) {
	const [instructions, setInstructions] = useState('');
	const [maxIters, setMaxIters] = useState(50);
	const [loading, setLoading] = useState(false);
	// Saving is allowed only over settings that were actually loaded, so a
	// failed load can never overwrite saved instructions with empty defaults.
	const [loaded, setLoaded] = useState(false);
	const [attempt, setAttempt] = useState(0);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		if (!open) return;
		let cancelled = false;
		setLoading(true);
		setLoaded(false);
		setError('');
		workforceApi
			.leaderSettings()
			.then((settings) => {
				if (cancelled) return;
				setInstructions(settings.instructions);
				setMaxIters(settings.max_iters);
				setLoaded(true);
			})
			.catch((e) => !cancelled && setError(formatApiErrorForAlert(e)))
			.finally(() => !cancelled && setLoading(false));
		return () => {
			cancelled = true;
		};
	}, [open, attempt]);

	const stepsValid = Number.isInteger(maxIters) && maxIters >= 5 && maxIters <= 100;

	const save = async () => {
		if (!loaded || !stepsValid) return;
		setSaving(true);
		setError('');
		try {
			await workforceApi.saveLeaderSettings({ instructions, max_iters: maxIters });
			toast.success('Đã lưu cài đặt Leader. Áp dụng từ tin nhắn tiếp theo.');
			onOpenChange(false);
		} catch (e) {
			setError(formatApiErrorForAlert(e));
		} finally {
			setSaving(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[560px]">
				<DialogHeader>
					<DialogTitle>Cài đặt Leader</DialogTitle>
					<DialogDescription>
						Tên, model và chính sách vận hành của Leader do nền tảng quản lý. Hướng dẫn thêm được đặt sau chính sách đó;
						khi mâu thuẫn, chính sách nền tảng được ưu tiên.
					</DialogDescription>
				</DialogHeader>
				{loading && (
					<p className="flex items-center gap-2 text-sm text-muted-foreground">
						<Loader2 className="size-4 animate-spin" /> Đang tải…
					</p>
				)}
				{!loading && !loaded && (
					<Button variant="outline" size="sm" className="self-start" onClick={() => setAttempt((n) => n + 1)}>
						Tải lại cài đặt
					</Button>
				)}
				{loaded && (
					<FieldGroup>
						<Field>
							<FieldLabel htmlFor="leader-instructions">Hướng dẫn thêm cho Leader</FieldLabel>
							<Textarea
								id="leader-instructions"
								rows={8}
								maxLength={MAX_INSTRUCTIONS}
								value={instructions}
								onChange={(e) => setInstructions(e.target.value)}
								placeholder="Ví dụ: Ưu tiên phiếu khẩn cấp về điện nước; luôn xưng hô anh/chị với cư dân."
							/>
							<p className="text-xs text-muted-foreground">
								{instructions.length}/{MAX_INSTRUCTIONS} ký tự
							</p>
						</Field>
						<Field>
							<FieldLabel htmlFor="leader-max-iters">Số bước suy luận tối đa mỗi lượt</FieldLabel>
							<Input
								id="leader-max-iters"
								type="number"
								min={5}
								max={100}
								value={Number.isNaN(maxIters) ? '' : maxIters}
								onChange={(e) => setMaxIters(e.target.valueAsNumber)}
								aria-invalid={!stepsValid}
							/>
							<p className="text-xs text-muted-foreground">Từ 5 đến 100. Nhiều bước hơn cho phép xử lý phiếu dài hơn nhưng tốn token hơn.</p>
						</Field>
					</FieldGroup>
				)}
				{error && (
					<Alert variant="destructive">
						<CircleAlert />
						<AlertDescription className="whitespace-pre-wrap">{error}</AlertDescription>
					</Alert>
				)}
				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
						Huỷ
					</Button>
					<Button onClick={save} disabled={!loaded || saving || !stepsValid}>
						{saving && <Loader2 className="size-4 animate-spin" />}
						Lưu
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
