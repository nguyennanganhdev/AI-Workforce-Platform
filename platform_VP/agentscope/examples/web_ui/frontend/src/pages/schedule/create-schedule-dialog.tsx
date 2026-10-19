import { format } from 'date-fns';
import { ChevronDownIcon, CircleAlert, Loader2, PlusCircle } from 'lucide-react';
import * as React from 'react';

import { channelApi } from '@/api';
import type { ChannelRecord, ChatModelConfig, PermissionMode } from '@/api';
import { AgentSelect } from '@/components/select/AgentSelect';
import { LlmSelect } from '@/components/select/LlmSelect';
import { PermissionModeSelect } from '@/components/select/PermissionModeSelect';
import { TimezoneSelect } from '@/components/select/TimezoneSelect';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useAgents } from '@/hooks/useAgents';
import { useSchedules } from '@/hooks/useSchedules';
import { useTranslation } from '@/i18n/useI18n';

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCreated?: () => void;
}

type FreqType = 'once' | 'daily' | 'weekly' | 'monthly';

function getDefaultForm() {
	const now = new Date();
	const hh = String(now.getHours()).padStart(2, '0');
	const mm = String(now.getMinutes()).padStart(2, '0');
	return {
		name: '',
		description: '',
		freq: 'daily' as FreqType,
		date: now,
		time: `${hh}:${mm}`,
		endDate: undefined as Date | undefined,
		agentId: '',
		chatModelConfig: null as ChatModelConfig | null,
		permissionMode: 'dont_ask' as PermissionMode,
		timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
		stateful: false,
		deliverChannelId: '',
		deliverChatId: '',
	};
}

/** Common unattended jobs; each only reads and reports. */
const TEMPLATES: { label: string; name: string; description: string; freq: FreqType; time: string; weekday?: number }[] = [
	{
		label: 'Báo cáo ticket 8:00 hằng ngày', name: 'Báo cáo ticket hằng ngày', freq: 'daily', time: '08:00',
		description: 'Tổng hợp yêu cầu: số yêu cầu mới, đang xử lý, đã xong và quá hạn từ hôm qua đến giờ. Nêu tối đa 3 việc cần chú ý. Chỉ đọc và báo cáo, không thực hiện thao tác ghi.',
	},
	{
		label: 'Rà soát quá hạn 14:00', name: 'Rà soát ticket quá hạn', freq: 'daily', time: '14:00',
		description: 'Liệt kê ticket quá hạn phản hồi hoặc quá hạn xử lý, kèm người đang giữ và việc tiếp theo nên làm. Chỉ đọc và báo cáo, không tự giao việc hay hủy yêu cầu.',
	},
	{
		label: 'Tổng kết tuần thứ Hai 8:30', name: 'Tổng kết tuần', freq: 'weekly', time: '08:30', weekday: 1,
		description: 'Tổng kết tuần trước: số ticket theo loại, thời gian xử lý trung bình, ticket mở lại và các điểm cần cải thiện. Chỉ đọc và báo cáo.',
	},
];

function nextWeekday(day: number): Date {
	const date = new Date();
	date.setDate(date.getDate() + ((day - date.getDay() + 7) % 7));
	return date;
}

function buildCronExpr(freq: FreqType, time: string, date: Date | undefined): string {
	const [h, m] = time.split(':').map(Number);
	switch (freq) {
		case 'daily':
			return `${m} ${h} * * *`;
		case 'weekly': {
			const weekday = date ? date.getDay() : 1;
			return `${m} ${h} * * ${weekday}`;
		}
		case 'monthly': {
			const monthDay = date ? date.getDate() : 1;
			return `${m} ${h} ${monthDay} * *`;
		}
		default:
			return '';
	}
}

function DatePickerButton({
	date,
	onSelect,
	placeholder,
	disabled,
}: {
	date: Date | undefined;
	onSelect: (d: Date | undefined) => void;
	placeholder: string;
	disabled?: boolean;
}) {
	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					disabled={disabled}
					className="w-32 justify-between font-normal"
				>
					{date ? format(date, 'PPP') : placeholder}
					<ChevronDownIcon className="size-3.5 text-muted-foreground" />
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-auto p-0" align="start">
				<Calendar
					mode="single"
					selected={date}
					onSelect={onSelect}
					captionLayout="dropdown"
				/>
			</PopoverContent>
		</Popover>
	);
}

export function CreateScheduleDialog({ open, onOpenChange, onCreated }: Props) {
	const { t } = useTranslation();
	const { create } = useSchedules();
	const { runnable: agents } = useAgents();
	const [form, setForm] = React.useState(getDefaultForm);
	const [loading, setLoading] = React.useState(false);
	const [error, setError] = React.useState('');
	const [channels, setChannels] = React.useState<ChannelRecord[]>([]);
	const [chats, setChats] = React.useState<{ chat_id: string; name: string }[]>([]);

	React.useEffect(() => {
		if (open) {
			setForm(getDefaultForm());
			setError('');
			// Results go to the area's Discord channel when it has one.
			channelApi.list().then((records) => {
				const usable = records.filter((record) => record.enabled);
				setChannels(usable);
				const discord = usable.find((record) => record.channel_type === 'discord');
				if (discord) setForm((prev) => ({ ...prev, deliverChannelId: prev.deliverChannelId || discord.id }));
			}).catch(() => setChannels([]));
		}
	}, [open]);

	React.useEffect(() => {
		if (!form.deliverChannelId) return;
		let cancelled = false;
		channelApi.listChatIds(form.deliverChannelId).then((response) => {
			if (cancelled) return;
			setChats(response.chats);
			setForm((prev) => response.chats.some((chat) => chat.chat_id === prev.deliverChatId)
				? prev : { ...prev, deliverChatId: response.chats[0]?.chat_id ?? '' });
		}).catch(() => { if (!cancelled) setChats([]); });
		return () => { cancelled = true; };
	}, [form.deliverChannelId]);

	React.useEffect(() => {
		if (agents.length > 0 && !form.agentId) {
			setForm((prev) => ({ ...prev, agentId: agents[0].id }));
		}
	}, [agents, form.agentId]);

	const set = <K extends keyof ReturnType<typeof getDefaultForm>>(
		key: K,
		value: ReturnType<typeof getDefaultForm>[K],
	) => setForm((prev) => ({ ...prev, [key]: value }));

	const isValid =
		form.name.trim() && !!form.date && !!form.time && !!form.agentId && !!form.chatModelConfig &&
		(!form.deliverChannelId || !!form.deliverChatId);

	const applyTemplate = (template: (typeof TEMPLATES)[number]) => setForm((prev) => ({
		...prev, name: template.name, description: template.description, freq: template.freq, time: template.time,
		date: template.weekday === undefined ? prev.date : nextWeekday(template.weekday),
	}));

	const handleSubmit = async () => {
		setError('');
		if (!isValid) return;
		setLoading(true);
		try {
			let cronExpression: string;

			const d = new Date(form.date!);
			const [h, m] = form.time.split(':').map(Number);
			d.setHours(h, m, 0, 0);

			if (form.freq === 'once') {
				cronExpression = `${m} ${h} ${d.getDate()} ${d.getMonth() + 1} *`;
			} else {
				cronExpression = buildCronExpr(form.freq, form.time, form.date);
			}

			await create({
				name: form.name.trim(),
				description: form.description.trim(),
				cron_expression: cronExpression,
				timezone: form.timezone,
				agent_id: form.agentId,
				chat_model_config: form.chatModelConfig!,
				enabled: true,
				stateful: form.stateful,
				permission_mode: form.permissionMode,
				once: form.freq === 'once',
				ended_at: form.freq !== 'once' && form.endDate
					? new Date(form.endDate.getFullYear(), form.endDate.getMonth(), form.endDate.getDate(), 23, 59, 59).toISOString()
					: null,
				deliver_channel_id: form.deliverChannelId,
				deliver_chat_id: form.deliverChannelId ? form.deliverChatId : '',
			});
			onCreated?.();
			onOpenChange(false);
		} catch (e) {
			setError(String(e));
		} finally {
			setLoading(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[500px] !max-w-[500px]">
				<DialogHeader>
					<DialogTitle>{t('schedule.createSchedule.title')}</DialogTitle>
					<DialogDescription>
						{t('schedule.createSchedule.description')}
					</DialogDescription>
				</DialogHeader>

				<div className="no-scrollbar -mx-6 max-h-[75vh] overflow-y-auto px-6">
					<FieldGroup className="[&>[data-orientation=horizontal]>:last-child]:w-48">
						<div className="flex flex-wrap gap-1.5" role="group" aria-label="Mẫu lịch chạy">
							{TEMPLATES.map((template) => (
								<Button key={template.name} type="button" size="sm" variant="outline"
									onClick={() => applyTemplate(template)}>
									{template.label}
								</Button>
							))}
						</div>
						<Field>
							<FieldLabel>{t('common.name')}</FieldLabel>
							<Input
								value={form.name}
								onChange={(e) => set('name', e.target.value)}
								placeholder={t('schedule.createSchedule.namePlaceholder')}
							/>
						</Field>

						<Field>
							<FieldLabel>{t('schedule.createSchedule.descriptionLabel')}</FieldLabel>
							<Textarea
								value={form.description}
								onChange={(e) => set('description', e.target.value)}
								placeholder={t('schedule.createSchedule.descriptionPlaceholder')}
								className="min-h-[150px]"
							/>
						</Field>

						<div className="flex gap-3">
							<Field className="flex-1">
								<FieldLabel>{t('common.date')}</FieldLabel>
								<DatePickerButton
									date={form.date}
									onSelect={(d) => d && set('date', d)}
									placeholder={t('schedule.pickDate')}
								/>
							</Field>
							<Field className="w-48">
								<FieldLabel>{t('common.time')}</FieldLabel>
								<Input
									type="time"
									value={form.time}
									onChange={(e) => set('time', e.target.value)}
									className="appearance-none [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
								/>
							</Field>
						</div>

						<Field orientation={'horizontal'}>
							<FieldLabel>{t('schedule.timezone')}</FieldLabel>
							<TimezoneSelect
								size="default"
								value={form.timezone}
								onChange={(v) => set('timezone', v)}
							/>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel>{t('schedule.frequency')}</FieldLabel>
							<Select
								value={form.freq}
								onValueChange={(v) => set('freq', v as FreqType)}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="once">{t('schedule.freqOnce')}</SelectItem>
									<SelectItem value="daily">{t('schedule.freqDaily')}</SelectItem>
									<SelectItem value="weekly">
										{t('schedule.freqWeekly')}
									</SelectItem>
									<SelectItem value="monthly">
										{t('schedule.freqMonthly')}
									</SelectItem>
								</SelectContent>
							</Select>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel
								className={form.freq === 'once' ? 'text-muted-foreground' : ''}
							>
								{t('schedule.endAt')}
							</FieldLabel>
							<DatePickerButton
								date={form.freq === 'once' ? undefined : form.endDate}
								onSelect={(d) => set('endDate', d)}
								placeholder={t('schedule.pickDate')}
								disabled={form.freq === 'once'}
							/>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel>{t('common.agent')}</FieldLabel>
							<AgentSelect
								size="default"
								agents={agents}
								value={form.agentId || null}
								onChange={(id) => set('agentId', id)}
								placeholder={t('common.selectAgent')}
							/>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel>{t('common.model')}</FieldLabel>
							<LlmSelect
								size="default"
								value={form.chatModelConfig}
								onChange={(v) => set('chatModelConfig', v)}
							/>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel>{t('schedule.permissionMode')}</FieldLabel>
							<PermissionModeSelect
								size="default"
								value={form.permissionMode}
								onChange={(v) => set('permissionMode', v)}
								exclude={['bypass']}
							/>
						</Field>

						<Field orientation={'horizontal'}>
							<FieldLabel>Gửi kết quả vào</FieldLabel>
							<Select
								value={form.deliverChannelId || 'none'}
								onValueChange={(v) => setForm((prev) => ({ ...prev, deliverChannelId: v === 'none' ? '' : v, deliverChatId: '' }))}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="none">Chỉ lưu trong phiên của agent</SelectItem>
									{channels.map((channel) => (
										<SelectItem key={channel.id} value={channel.id}>
											{channel.name || channel.channel_type}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</Field>

						{form.deliverChannelId && (
							<Field orientation={'horizontal'}>
								<FieldLabel>Cuộc trò chuyện</FieldLabel>
								<Select value={form.deliverChatId} onValueChange={(v) => set('deliverChatId', v)}>
									<SelectTrigger>
										<SelectValue placeholder={chats.length ? 'Chọn kênh chat' : 'Bot chưa thấy kênh chat nào'} />
									</SelectTrigger>
									<SelectContent>
										{chats.map((chat) => (
											<SelectItem key={chat.chat_id} value={chat.chat_id}>{chat.name || chat.chat_id}</SelectItem>
										))}
									</SelectContent>
								</Select>
							</Field>
						)}

						<Field>
							<div className="flex flex-row items-center justify-between">
								<div className="flex flex-col gap-y-0.5">
									<FieldLabel>{t('schedule.stateful')}</FieldLabel>
									<span className="text-xs text-muted-foreground">
										{t('schedule.statefulDesc')}
									</span>
								</div>
								<Switch
									checked={form.stateful}
									onCheckedChange={(v) => set('stateful', v)}
								/>
							</div>
						</Field>

						{error && <p className="text-sm text-destructive">{error}</p>}
					</FieldGroup>
				</div>

				<DialogFooter>
					<Button variant="ghost" onClick={() => onOpenChange(false)} disabled={loading}>
						<CircleAlert className="size-3.5" />
						{t('common.cancel')}
					</Button>
					<Button onClick={handleSubmit} disabled={loading || !isValid}>
						{loading ? (
							<Loader2 className="size-3.5 animate-spin" />
						) : (
							<PlusCircle className="size-3.5" />
						)}
						{loading ? t('common.creating') : t('common.create')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
