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

interface TokenResponse {
	access_token: string;
	token_type: string;
	expires_in: number;
}

export interface RegisterRequest {
	email: string;
	username: string;
	password: string;
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
				// A server that is restarting (5xx, network error) does not mean
				// the refresh cookie is invalid: retry a few times before showing
				// the signed-out screen. Only 401/403 sign the user out at once.
				for (let attempt = 0; ; attempt++) {
					try {
						const tokens = await client.post<TokenResponse>(
							'/auth/refresh',
							undefined,
							undefined,
							{ silent: true },
						);
						return await acceptTokens(tokens);
					} catch (error) {
						const refused =
							error instanceof ApiError && [401, 403].includes(error.status);
						if (refused || attempt >= 3) {
							setAccessToken(null);
							return null;
						}
						await new Promise((resolve) => setTimeout(resolve, 1_000 * 2 ** attempt));
					}
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
