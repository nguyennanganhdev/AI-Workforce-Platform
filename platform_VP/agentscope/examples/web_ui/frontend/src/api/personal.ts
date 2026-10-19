import { client } from './client';

export interface UsageView {
	timezone: string;
	buckets: { window: string; used: number; reserved: number }[];
	pending_reconciliation: number;
	effective_limits?: { subject: string; window: string; limit: number; used: number; reserved: number; remaining: number }[];
	policy_revision?: number;
}
export interface DomainLink {
	id: string;
	provider_id: string;
	status: string;
	scopes: string[];
	revision: number;
}

function object(value: unknown): Record<string, unknown> {
	if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('INVALID_CONTRACT');
	return value as Record<string, unknown>;
}
function string(value: unknown): string {
	if (typeof value !== 'string' || !value) throw new Error('INVALID_CONTRACT');
	return value;
}
function count(value: unknown): number {
	if (!Number.isSafeInteger(value) || Number(value) < 0) throw new Error('INVALID_CONTRACT');
	return Number(value);
}

export function parseUsage(value: unknown): UsageView {
	const raw = object(value);
	if (!Array.isArray(raw.buckets)) throw new Error('INVALID_CONTRACT');
	return {
		timezone: string(raw.timezone), pending_reconciliation: count(raw.pending_reconciliation),
		...(raw.effective_limits !== undefined ? {
			policy_revision: count(raw.policy_revision),
			effective_limits: (() => {
				if (!Array.isArray(raw.effective_limits)) throw new Error('INVALID_CONTRACT');
				return raw.effective_limits.map((entry) => {
					const item = object(entry);
					const limit = count(item.limit), used = count(item.used), reserved = count(item.reserved), remaining = count(item.remaining);
					if (remaining !== Math.max(0, limit - used - reserved)) throw new Error('INVALID_CONTRACT');
					return { subject: string(item.subject), window: string(item.window), limit, used, reserved, remaining };
				});
			})(),
		} : {}),
		buckets: raw.buckets.map((entry) => {
			const bucket = object(entry);
			return { window: string(bucket.window), used: count(bucket.used), reserved: count(bucket.reserved) };
		}),
	};
}

export function parseLinks(value: unknown): DomainLink[] {
	const raw = object(value);
	if (!Array.isArray(raw.items)) throw new Error('INVALID_CONTRACT');
	return raw.items.map((entry) => {
		const link = object(entry);
		if (!Array.isArray(link.scopes) || count(link.revision) < 1) throw new Error('INVALID_CONTRACT');
		return { id: string(link.id), provider_id: string(link.provider_id), status: string(link.status),
			scopes: link.scopes.map(string), revision: count(link.revision) };
	});
}

export function parseLinkStart(value: unknown, origin: string) {
	const raw = object(value);
	const url = new URL(string(raw.authorization_url), origin);
	if (url.username || url.password || url.hash || (url.protocol !== 'https:'
		&& !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)))) {
		throw new Error('INVALID_AUTHORIZATION_URL');
	}
	const state = string(url.searchParams.get('state'));
	if (state.length < 32) throw new Error('INVALID_CONTRACT');
	return { transaction_id: string(raw.transaction_id), authorization_url: url.href, state };
}

export const personalApi = {
	usage: async () => parseUsage(await client.get<unknown>('/me/usage', undefined, { silent: true, timeoutMs: 15000 })),
	links: async () => parseLinks(await client.get<unknown>('/me/domain-links', undefined, { silent: true, timeoutMs: 15000 })),
	startLink: async (providerId: string) => parseLinkStart(await client.post<unknown>(
		`/me/domain-links/${encodeURIComponent(providerId)}/start`, undefined, undefined, { silent: true },
	), window.location.origin),
	completeLink: (providerId: string, body: { transaction_id: string; state: string; code: string }) =>
		client.post(`/me/domain-links/${encodeURIComponent(providerId)}/complete`, body, undefined, { silent: true }),
	unlink: (id: string) => client.delete(`/me/domain-links/${encodeURIComponent(id)}`),
};
