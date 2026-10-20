import { client } from './client';
import type {
	BindingView,
	ChannelChatIdsResponse,
	ChannelRecord,
	ChannelSessionsResponse,
	ChannelStatus,
	ChannelTypeSchema,
	CreateChannelRequest,
	UpdateChannelRequest,
} from './types';

// DingTalk/Feishu are no longer offered for new channels. Existing ones stay
// listed so their owners can still disable or delete them.
const isOfferedChannel = ({ channel_type }: { channel_type: string }) =>
	!['dingtalk', 'feishu'].includes(channel_type);

export const channelApi = {
	listTypes: () =>
		client
			.get<ChannelTypeSchema[]>('/channels/types')
			.then((types) => types.filter(isOfferedChannel)),

	list: () => client.get<ChannelRecord[]>('/channels/'),

	get: (channelId: string) => client.get<ChannelRecord>(`/channels/${channelId}`),

	create: (body: CreateChannelRequest) => client.post<ChannelRecord>('/channels/', body),

	update: (channelId: string, body: UpdateChannelRequest) =>
		client.patch<ChannelRecord>(`/channels/${channelId}`, body),

	delete: (channelId: string) => client.delete(`/channels/${channelId}`),

	enable: (channelId: string) => client.post<{ status: string }>(`/channels/${channelId}/enable`),

	disable: (channelId: string) =>
		client.post<{ status: string }>(`/channels/${channelId}/disable`),

	status: (channelId: string) => client.get<ChannelStatus>(`/channels/${channelId}/status`),

	listSessions: (channelId: string) =>
		client.get<ChannelSessionsResponse>(`/channels/${channelId}/sessions`),

	listChatIds: (channelId: string) =>
		client.get<ChannelChatIdsResponse>(`/channels/${channelId}/chat_ids`),

	startBinding: (channelType: string) =>
		client.post<BindingView>('/channels/bindings', { channel_type: channelType }),

	/** Report the session; this call is also what advances it. */
	pollBinding: (bindingId: string) => client.get<BindingView>(`/channels/bindings/${bindingId}`),

	cancelBinding: (bindingId: string, options?: { silent?: boolean }) =>
		client.post<{ status: string }>(
			`/channels/bindings/${bindingId}/cancel`,
			undefined,
			undefined,
			options,
		),
};
