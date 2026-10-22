import { client } from './client';
import type {
	CreateCredentialRequest,
	CreateCredentialResponse,
	CredentialListResponse,
	CredentialView,
	CredentialSchemasResponse,
	UpdateCredentialRequest,
} from './types';

export const credentialApi = {
	list: () => client.get<CredentialListResponse>('/credential/'),

	schemas: () => client.get<CredentialSchemasResponse>('/credential/schemas'),

	create: (body: CreateCredentialRequest) =>
		client.post<CreateCredentialResponse>('/credential/', body),

	update: (credentialId: string, body: UpdateCredentialRequest) =>
		client.patch<CredentialView>(`/credential/${credentialId}`, body),

	delete: (credentialId: string) => client.delete(`/credential/${credentialId}`),

	/** The OpenRouter sign-in URL; OpenRouter then returns the browser to `/credential?oauth=…`. */
	startOpenRouterOAuth: () =>
		client.post<{ authorize_url: string }>('/credential/openrouter/oauth/start', null),
};
