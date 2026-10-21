import { toast } from 'sonner';

import i18n from '../i18n';

const DEFAULT_API_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const AUTH_EXPIRED_EVENT = 'agentscope:auth-expired';
export const getBaseUrl = () => localStorage.getItem('server_url') ?? DEFAULT_API_URL;

/**
 * Join an API path onto the base URL, keeping any base path ("/api" or
 * "https://host/api"). `new URL('/x', base)` would drop that path, and a
 * relative base like "/api" is not a valid URL base on its own.
 */
export function apiUrl(path: string, baseUrl: string = getBaseUrl()): URL {
	const base = new URL(baseUrl, globalThis.location?.origin ?? 'http://localhost');
	if (!base.pathname.endsWith('/')) base.pathname += '/';
	// "./" keeps a first segment containing ":" from being read as a scheme.
	return new URL(`./${path.replace(/^\/+/, '')}`, base);
}

let accessToken: string | null = null;
/** ``unavailable`` means the server could not answer, not that the session ended. */
type RefreshOutcome = 'refreshed' | 'expired' | 'unavailable';
let refreshPromise: Promise<RefreshOutcome> | null = null;

export const getAccessToken = () => accessToken;
export const setAccessToken = (token: string | null) => {
	accessToken = token;
};

/** Structured error returned by the AgentScope API. */
export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

interface RequestOptions {
	method?: string;
	body?: unknown;
	params?: Record<string, string>;
	silent?: boolean;
	signal?: AbortSignal;
	baseUrl?: string;
	timeoutMs?: number;
}

export const TIMEOUT_STATUS = 408;

function buildHeaders(hasBody: boolean): Record<string, string> {
	const headers: Record<string, string> = {};
	if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
	if (hasBody) headers['Content-Type'] = 'application/json';
	return headers;
}

async function extractErrorDetail(res: Response): Promise<string> {
	const responseText = await res.text();
	try {
		const json = JSON.parse(responseText) as { detail?: unknown };
		if (typeof json.detail === 'string') return json.detail;
		if (json.detail !== undefined) return JSON.stringify(json.detail);
	} catch {
		// The backend may return a plain-text error.
	}
	// A proxy error page (e.g. nginx's HTML 502) is not a message for people.
	if (!responseText || responseText.trimStart().startsWith('<') || responseText.length > 300) {
		return `${res.status} ${res.statusText || 'Server error'}`.trim();
	}
	return responseText;
}

function canRefresh(path: string): boolean {
	return !['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'].includes(path);
}

/** Rotate the HttpOnly refresh cookie once, even for concurrent 401 responses. */
async function refreshAccessToken(baseUrl: string): Promise<RefreshOutcome> {
	if (!refreshPromise) {
		refreshPromise = (async (): Promise<RefreshOutcome> => {
			try {
				const response = await fetch(apiUrl('/auth/refresh', baseUrl), {
					method: 'POST',
					credentials: 'include',
				});
				if (response.status === 401 || response.status === 403) {
					setAccessToken(null);
					return 'expired';
				}
				// A 5xx (e.g. during a deploy) says nothing about the session.
				if (!response.ok) return 'unavailable';
				const body = (await response.json()) as { access_token?: unknown };
				if (typeof body.access_token !== 'string') {
					setAccessToken(null);
					return 'expired';
				}
				setAccessToken(body.access_token);
				return 'refreshed';
			} catch {
				return 'unavailable';
			} finally {
				refreshPromise = null;
			}
		})();
	}
	return refreshPromise;
}

async function streamRequest(path: string, options: RequestOptions = {}): Promise<Response> {
	const { method = 'GET', body, params, signal, silent = false, baseUrl, timeoutMs } = options;
	const requestBaseUrl = baseUrl ?? getBaseUrl();
	const url = apiUrl(path, requestBaseUrl);
	if (params) {
		Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
	}

	const deadline = timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined;
	const combined =
		deadline && signal ? AbortSignal.any([signal, deadline]) : (deadline ?? signal);
	let sentToken: string | null = null;
	const send = () => {
		sentToken = accessToken;
		return fetch(url.toString(), {
			method,
			headers: buildHeaders(body !== undefined),
			body: body !== undefined ? JSON.stringify(body) : undefined,
			signal: combined,
			credentials: 'include',
		});
	};

	let response: Response;
	try {
		response = await send();
		if (response.status === 401 && canRefresh(path)) {
			// A delayed 401 may belong to the token another request already
			// replaced. Reuse the new token rather than rotate the cookie again.
			const outcome =
				accessToken && accessToken !== sentToken
					? 'refreshed'
					: await refreshAccessToken(requestBaseUrl);
			if (outcome === 'refreshed') {
				response = await send();
			}
			// Only a refused refresh ends the session; an unreachable server
			// fails this request but keeps the user signed in.
			if (
				outcome !== 'unavailable' &&
				response.status === 401 &&
				(!accessToken || accessToken === sentToken)
			) {
				setAccessToken(null);
				window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
			}
		}
	} catch (error) {
		if (error instanceof DOMException && error.name === 'AbortError') throw error;
		const timedOut = error instanceof DOMException && error.name === 'TimeoutError';
		const apiError = timedOut
			? new ApiError(TIMEOUT_STATUS, 'The server took too long to respond.')
			: new ApiError(
					0,
					'Cannot reach the server. Check the server address and your network.',
				);
		if (!silent) toast.error(apiError.detail);
		throw apiError;
	}

	if (!response.ok) {
		const rawDetail = await extractErrorDetail(response);
		const detail = response.status === 404 && /^Credential '[^']+' not found\.$/.test(rawDetail)
			? i18n.t('error.credentialNotFound')
			: rawDetail;
		const error = new ApiError(response.status, detail);
		if (!silent) toast.error(detail);
		throw error;
	}
	return response;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const response = await streamRequest(path, options);
	if (response.status === 204) return undefined as T;
	return response.json() as Promise<T>;
}

export const client = {
	get: <T>(
		path: string,
		params?: Record<string, string>,
		options?: { silent?: boolean; baseUrl?: string; timeoutMs?: number; signal?: AbortSignal },
	) => request<T>(path, { method: 'GET', params, ...options }),
	post: <T>(
		path: string,
		body?: unknown,
		params?: Record<string, string>,
		options?: { silent?: boolean },
	) => request<T>(path, { method: 'POST', body, params, silent: options?.silent }),
	patch: <T>(
		path: string,
		body?: unknown,
		params?: Record<string, string>,
		options?: { silent?: boolean },
	) => request<T>(path, { method: 'PATCH', body, params, silent: options?.silent }),
	delete: <T = void>(path: string, params?: Record<string, string>) =>
		request<T>(path, { method: 'DELETE', params }),
	stream: (path: string, options?: RequestOptions) => streamRequest(path, options),
};
