import type { AuthUser } from './auth';
import { client } from './client';
import { parseCapabilities } from '@/features/workforce/shell/access';

/** C01 public reader. Authority and workspace membership stay on the server. */
export const meApi = {
	capabilities: async (user: AuthUser) => parseCapabilities(
		await client.get<unknown>('/me/capabilities', undefined, { silent: true, timeoutMs: 15000 }), user,
	),
};
