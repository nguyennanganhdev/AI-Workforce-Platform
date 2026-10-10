// Component view model only; shared wire DTOs remain Foundation-owned.
export interface EventChannelView {
	tool_version_id: string;
	name: string;
	protocol_version: string;
	capabilities: readonly string[];
	status: 'configured' | 'disabled' | 'drifted' | 'unconfigured' | 'error';
	create_ready: boolean;
	provider_events_ready: boolean;
	status_query_ready: boolean;
	correlation_ready: boolean;
	blockers: readonly (
		| 'CONNECTION_DISABLED'
		| 'SCHEMA_DRIFT'
		| 'PROTOCOL_NOT_CONFIGURED'
		| 'CORRELATION_NOT_READY'
		| 'PROVIDER_AUTH_NOT_READY'
		| 'QUERY_BINDING_UNAVAILABLE'
	)[];
}

export type Readiness = 'ready' | 'blocked' | 'unsupported' | 'not_required';

export function channelReadiness(channel: EventChannelView): Record<
	'create' | 'providerEvent' | 'statusQuery' | 'correlation', Readiness
> {
	const has = (capability: string) => channel.capabilities.includes(capability);
	const pending = has('create');
	const noTracking: Readiness = has('terminal') ? 'not_required' : 'blocked';
	const availability = (supported: boolean, ready: boolean): Readiness =>
		!supported ? 'unsupported' : ready ? 'ready' : 'blocked';
	return {
		create: availability(pending, channel.status === 'configured'
			&& channel.create_ready && channel.correlation_ready),
		// Disabling new calls must not hide valid event reception for pinned jobs.
		providerEvent: pending ? availability(has('receive_status'),
			channel.provider_events_ready && channel.correlation_ready) : noTracking,
		statusQuery: pending ? availability(has('status_query'),
			channel.status === 'configured' && channel.status_query_ready
			&& channel.correlation_ready) : noTracking,
		correlation: pending ? availability(true, channel.correlation_ready) : noTracking,
	};
}
