import { ApiError, client, setAccessToken } from './client';

export interface AuthUser {
	id: string;
	tenant_id: string;
	email: string;
	username: string;
	status: string;
	role: string;
	domain_id: string;
	area_id: string;
}

export interface DomainOption {
	id: string;
	name: string;
}

export interface AreaOption {
	id: string;
	name: string;
	domain_id: string;
}

interface TokenResponse {
	access_token: string;
	token_type: string;
	expires_in: number;
}

export interface RegisterRequest {
	email: string;
	username: string;
	password: string;
	domain_id: string;
	area_id: string;
}

export interface LoginRequest {
	identity: string;
	password: string;
}

let restorePromise: Promise<AuthUser | null> | null = null;

async function acceptTokens(tokens: TokenResponse): Promise<AuthUser> {
	setAccessToken(tokens.access_token);
	return client.get<AuthUser>('/auth/me', undefined, { silent: true });
}

export const authApi = {
	listDomains: () =>
		client.get<DomainOption[]>('/directory/domains', undefined, { silent: true }),

	listAreas: (domainId: string) =>
		client.get<AreaOption[]>(
			`/directory/domains/${encodeURIComponent(domainId)}/areas`,
			undefined,
			{
				silent: true,
			},
		),

	register: (body: RegisterRequest) =>
		client.post<AuthUser>('/auth/register', body, undefined, { silent: true }),

	login: async (body: LoginRequest) => {
		const tokens = await client.post<TokenResponse>(
			'/auth/login',
			{ tenant_id: 'default', ...body },
			undefined,
			{ silent: true },
		);
		return acceptTokens(tokens);
	},

	registerAndLogin: async (body: RegisterRequest) => {
		await authApi.register(body);
		return authApi.login({ identity: body.username, password: body.password });
	},

	restoreSession: () => {
		if (!restorePromise) {
			restorePromise = (async () => {
				try {
					const tokens = await client.post<TokenResponse>(
						'/auth/refresh',
						undefined,
						undefined,
						{ silent: true },
					);
					return await acceptTokens(tokens);
				} catch (error) {
					setAccessToken(null);
					if (error instanceof ApiError && [401, 503].includes(error.status)) return null;
					return null;
				}
			})();
		}
		return restorePromise;
	},

	logout: async () => {
		try {
			await client.post<void>('/auth/logout', undefined, undefined, { silent: true });
		} finally {
			setAccessToken(null);
			restorePromise = null;
		}
	},
};
