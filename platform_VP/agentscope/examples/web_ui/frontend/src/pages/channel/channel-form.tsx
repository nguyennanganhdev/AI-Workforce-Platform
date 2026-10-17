import * as React from 'react';

import type { AgentView, ChannelBinding, ChannelTypeSchema, ChatModelConfig, PermissionMode } from '@/api';
import { ModelParametersPopover } from '@/components/popover/ModelParametersPopover';
import { LlmSelect } from '@/components/select/LlmSelect';
import { PermissionModeSelect } from '@/components/select/PermissionModeSelect';
import {
	Field,
	FieldContent,
	FieldDescription,
	FieldGroup,
	FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { useAvailableModels } from '@/hooks/useAvailableModels';
import { useTranslation } from '@/i18n/useI18n';
import { BindingsEditor } from '@/pages/channel/bindings-editor';
import { CredentialBindingPanel } from '@/pages/channel/credential-binding-panel';

export interface ChannelFormValue {
	channelType: string;
	name: string;
	/** How the credentials are being supplied on a create. */
	credentialMode: 'form' | 'binding';
	/** Set once an interactive binding has been approved. */
	credentialBindingId: string;
	credentials: Record<string, string>;
	platformConfig: Record<string, unknown>;
	bindings: ChannelBinding[];
	chatModelConfig: ChatModelConfig | null;
	fallbackChatModelConfig: ChatModelConfig | null;
	permissionMode: PermissionMode;
}

interface Props {
	value: ChannelFormValue;
	onChange: (value: ChannelFormValue) => void;
	agents: AgentView[];
	channelTypes: ChannelTypeSchema[];
	/** Create mode exposes type + credential fields; edit mode locks them. */
	mode: 'create' | 'edit';
}

export function ChannelForm({ value, onChange, agents, channelTypes, mode }: Props) {
	const { t } = useTranslation();
	const privateDiscord = useCurrentUser()?.role === 'VIN_USER' && value.channelType === 'discord';
	const { groups } = useAvailableModels();

	const set = <K extends keyof ChannelFormValue>(key: K, v: ChannelFormValue[K]) =>
		onChange({ ...value, [key]: v });

	// Read by the platform-change effect, which must not re-run just
	// because some unrelated field moved.
	const valueRef = React.useRef(value);
	React.useEffect(() => {
		valueRef.current = value;
	});

	const typeSchema = React.useMemo(
		() => channelTypes.find((ct) => ct.channel_type === value.channelType),
		[channelTypes, value.channelType],
	);

	const bindingSupported = Boolean(typeSchema?.supports_credential_binding);

	// Switching platform invalidates whatever was collected for the old
	// one, and decides which path is even on offer.
	React.useEffect(() => {
		if (mode !== 'create') return;
		onChange({
			...valueRef.current,
			credentialMode: bindingSupported ? 'binding' : 'form',
			credentialBindingId: '',
			credentials: {},
		});
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [value.channelType, bindingSupported]);

	const credentialFields = React.useMemo(() => {
		const schema = typeSchema?.credentials_schema as
			| { properties?: Record<string, Record<string, unknown>>; required?: string[] }
			| undefined;
		if (!schema?.properties) return [];
		const required = schema.required ?? [];
		return Object.entries(schema.properties).map(([key, def]) => ({
			key,
			title: t(`channel.fields.${key}.title`, {
				defaultValue: (def.title as string) || key,
			}),
			description:
				t(`channel.fields.${key}.description`, {
					defaultValue: (def.description as string) || '',
				}) || undefined,
			format: def.format as string | undefined,
			required: required.includes(key),
		}));
	}, [t, typeSchema]);

	const configFields = React.useMemo(() => {
		const schema = typeSchema?.config_schema as
			| { properties?: Record<string, Record<string, unknown>> }
			| undefined;
		if (!schema?.properties) return [];
		return Object.entries(schema.properties).map(([key, def]) => ({
			key,
			title: t(`channel.fields.${key}.title`, {
				defaultValue: (def.title as string) || key,
			}),
			description:
				t(`channel.fields.${key}.description`, {
					defaultValue: (def.description as string) || '',
				}) || undefined,
			type: def.type as string | undefined,
			default: def.default,
		}));
	}, [t, typeSchema]);

	const selectedModelCard = React.useMemo(() => {
		if (!value.chatModelConfig) return null;
		const items = groups[value.chatModelConfig.type];
		if (!items) return null;
		for (const { models } of items) {
			const card = models.find((m) => m.name === value.chatModelConfig!.model);
			if (card) return card;
		}
		return null;
	}, [groups, value.chatModelConfig]);

	return (
		<FieldGroup className="[&>[data-orientation=horizontal]>:last-child]:w-48">
			{mode === 'edit' && (
				<Field orientation="horizontal">
					<FieldLabel>{t('channel.create.channelType')}</FieldLabel>
					<span className="text-sm">{typeSchema?.display_name ?? value.channelType}</span>
				</Field>
			)}

			<Field orientation="horizontal">
				<FieldContent>
					<FieldLabel>{t('channel.create.nameLabel')}</FieldLabel>
					<FieldDescription className="text-xs">
						{t('channel.create.nameDesc')}
					</FieldDescription>
				</FieldContent>
				<Input
					className="text-sm"
					value={value.name}
					onChange={(e) => set('name', e.target.value)}
					placeholder={t('channel.create.namePlaceholder')}
				/>
			</Field>

			{mode === 'create' && bindingSupported && (
				<Tabs
					value={value.credentialMode}
					onValueChange={(m) =>
						onChange({
							...value,
							credentialMode: m as ChannelFormValue['credentialMode'],
							credentialBindingId: '',
						})
					}
				>
					<TabsList className="w-full">
						<TabsTrigger value="binding">
							{t('channel.credentialBinding.tab')}
						</TabsTrigger>
						<TabsTrigger value="form">
							{t('channel.credentialBinding.manualTab')}
						</TabsTrigger>
					</TabsList>
				</Tabs>
			)}

			{mode === 'create' && value.credentialMode === 'binding' && bindingSupported && (
				<CredentialBindingPanel
					channelType={value.channelType}
					onAuthorized={(bindingId) => set('credentialBindingId', bindingId)}
				/>
			)}

			{mode === 'create' &&
				value.credentialMode === 'form' &&
				credentialFields.map((field) => (
					<Field key={field.key}>
						<FieldLabel>
							{field.title}
							{field.required && ' *'}
						</FieldLabel>
						<Input
							className="text-sm"
							type={field.format === 'password' ? 'password' : 'text'}
							value={value.credentials[field.key] || ''}
							onChange={(e) =>
								set('credentials', {
									...value.credentials,
									[field.key]: e.target.value,
								})
							}
							placeholder={field.description || field.title}
						/>
					</Field>
				))}

			<Separator />

			<Field orientation="horizontal">
				<FieldContent>
					<FieldLabel>{t('common.model')}</FieldLabel>
					<FieldDescription className="text-xs">
						{t('channel.create.modelDesc')}
					</FieldDescription>
				</FieldContent>
				<div className="flex w-full items-center gap-1">
					<LlmSelect
						size="default"
						className="min-w-0 flex-1"
						value={value.chatModelConfig}
						onChange={(v) => set('chatModelConfig', v)}
					/>
					<ModelParametersPopover
						selectedModel={value.chatModelConfig}
						modelCard={selectedModelCard}
						onChange={(parameters) =>
							value.chatModelConfig &&
							set('chatModelConfig', { ...value.chatModelConfig, parameters })
						}
						selectedFallbackModel={value.fallbackChatModelConfig}
						onFallbackChange={(cfg) => set('fallbackChatModelConfig', cfg)}
					/>
				</div>
			</Field>

			<Field orientation="horizontal">
				<FieldContent>
					<FieldLabel>{t('channel.create.permissionMode')}</FieldLabel>
					<FieldDescription className="text-xs">
						{t('channel.create.permissionModeDesc')}
					</FieldDescription>
				</FieldContent>
				<PermissionModeSelect
					size="default"
					className="w-full"
					value={value.permissionMode}
					onChange={(v) => set('permissionMode', v)}
				/>
			</Field>

			<Separator />

			<Field>
				<FieldLabel>{t('channel.routing')}</FieldLabel>
				<span className="mb-1 text-xs text-muted-foreground">
					{t('channel.routingDesc')}
				</span>
				<BindingsEditor
					value={value.bindings}
					onChange={(b) => set('bindings', b)}
					agents={agents}
				/>
			</Field>

			<Separator />

			{configFields.map((field) => (
				<Field key={field.key}>
					<div className="flex flex-row items-center justify-between gap-4">
						<div className="flex flex-col gap-y-0.5">
							<FieldLabel htmlFor={`channel-config-${field.key}`}>{field.key === 'owner_user_id' && privateDiscord ? 'Discord ID của chủ tài khoản (bắt buộc)' : field.title}</FieldLabel>
							{field.description && (
								<span className="text-xs text-muted-foreground">
									{field.description}
								</span>
							)}
							{field.key === 'allowed_user_ids' && <span id="discord-allowlist-help" className="text-xs text-muted-foreground">Danh sách rỗng = chặn tất cả người dùng. Khi tạo bot cá nhân, danh sách phải có Discord ID của chủ tài khoản. Bot cá nhân chỉ trả lời qua tin nhắn riêng (DM).</span>}
							{field.key === 'owner_user_id' && privateDiscord && <span className="text-xs text-muted-foreground">Trong Discord, bật Developer Mode rồi chọn Copy User ID ở hồ sơ của bạn. ID nhập ở đây chưa thay thế bước xác minh danh tính.</span>}
						</div>
						{field.type === 'boolean' ? (
							<Switch
								id={`channel-config-${field.key}`}
								checked={
									(value.platformConfig[field.key] as boolean) ??
									(field.default as boolean) ??
									false
								}
								onCheckedChange={(v) =>
									set('platformConfig', {
										...value.platformConfig,
										[field.key]: v,
									})
								}
							/>
						) : field.type === 'array' ? (
							<Input
								id={`channel-config-${field.key}`}
								aria-describedby={field.key === 'allowed_user_ids' ? 'discord-allowlist-help' : undefined}
								className="h-8 w-48 text-sm"
								placeholder="ID, cách nhau bằng dấu phẩy"
								value={((value.platformConfig[field.key] ?? field.default ?? []) as string[]).join(', ')}
								onChange={(e) =>
									set('platformConfig', {
										...value.platformConfig,
										[field.key]: e.target.value.split(/[\s,]+/).filter(Boolean),
									})
								}
							/>
						) : (
							<Input
								id={`channel-config-${field.key}`}
								required={privateDiscord && field.key === 'owner_user_id' && mode === 'create'}
								className="h-8 w-48 text-sm"
								value={String(
									value.platformConfig[field.key] ?? field.default ?? '',
								)}
								onChange={(e) =>
									set('platformConfig', {
										...value.platformConfig,
										[field.key]: e.target.value,
										...(privateDiscord && field.key === 'owner_user_id' && mode === 'create'
											&& (!Array.isArray(value.platformConfig.allowed_user_ids)
												|| (value.platformConfig.allowed_user_ids.length === 1 && value.platformConfig.allowed_user_ids[0] === value.platformConfig.owner_user_id))
											? { allowed_user_ids: e.target.value ? [e.target.value] : [] } : {}),
									})
								}
							/>
						)}
					</div>
				</Field>
			))}
		</FieldGroup>
	);
}
