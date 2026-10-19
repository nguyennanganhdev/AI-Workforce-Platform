import type {
	ChannelRecord,
	ChatModelConfig,
	CreateChannelRequest,
	PermissionMode,
	UpdateChannelRequest,
} from '@/api';
import type { ChannelFormValue } from '@/pages/channel/channel-form';

export function defaultChannelForm(agentId = ''): ChannelFormValue {
	return {
		channelType: 'telegram',
		name: '',
		credentialMode: 'form',
		credentialBindingId: '',
		credentials: {},
		platformConfig: {},
		bindings: [
			{
				match_key: 'chat_id',
				match_value: '*',
				agent_id: agentId,
				session_scope: 'per_chat',
			},
		],
		chatModelConfig: null,
		fallbackChatModelConfig: null,
		permissionMode: 'default' as PermissionMode,
	};
}

export function channelFormFromRecord(record: ChannelRecord): ChannelFormValue {
	return {
		channelType: record.channel_type,
		name: record.name ?? '',
		credentialMode: 'form',
		credentialBindingId: '',
		credentials: {},
		platformConfig: record.platform_config ?? {},
		bindings: record.routing.bindings,
		chatModelConfig: record.session.chat_model_config,
		fallbackChatModelConfig: record.session.fallback_chat_model_config ?? null,
		permissionMode: record.session.permission_mode,
	};
}

function sessionSettings(v: ChannelFormValue) {
	return {
		session: {
			chat_model_config: v.chatModelConfig as ChatModelConfig,
			fallback_chat_model_config: v.fallbackChatModelConfig,
			permission_mode: v.permissionMode,
		},
	};
}

export function toCreateRequest(v: ChannelFormValue): CreateChannelRequest {
	// A completed binding replaces the fields; the server takes the
	// credentials from it so they never travel through the browser.
	const credentials =
		v.credentialMode === 'binding'
			? { credential_binding_id: v.credentialBindingId }
			: { credentials: v.credentials };
	return {
		channel_type: v.channelType,
		name: v.name.trim() || null,
		...credentials,
		platform_config: v.platformConfig,
		routing: { bindings: v.bindings },
		enabled: true,
		...sessionSettings(v),
	};
}

export function toUpdateRequest(v: ChannelFormValue): UpdateChannelRequest {
	return {
		name: v.name.trim() || null,
		platform_config: v.platformConfig,
		routing: { bindings: v.bindings },
		...sessionSettings(v),
	};
}

export function isDiscordUserId(value: unknown): value is string {
	return typeof value === 'string' && /^[0-9]{1,20}$/.test(value) && !/^0+$/.test(value);
}

export function isChannelFormValid(v: ChannelFormValue, mode: 'create' | 'edit', customer = false): boolean {
	if (!v.name.trim()) return false;
	if (!v.chatModelConfig) return false;
	if (v.bindings.length === 0) return false;
	if (v.bindings.some((b) => !b.agent_id)) return false;
	if (mode === 'create' && !v.channelType) return false;
	// An unfinished binding has no credentials to create the channel with.
	if (mode === 'create' && v.credentialMode === 'binding' && !v.credentialBindingId) return false;
	if (v.channelType === 'discord' && mode === 'create' && customer) {
		const owner = v.platformConfig.owner_user_id;
		const allowed = v.platformConfig.allowed_user_ids;
		if (!isDiscordUserId(owner) || !Array.isArray(allowed) || !allowed.includes(owner)
			|| allowed.length > 100 || !allowed.every(isDiscordUserId)) return false;
	}
	return true;
}
