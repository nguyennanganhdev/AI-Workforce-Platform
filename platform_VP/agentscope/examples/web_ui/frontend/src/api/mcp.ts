import { client } from './client';
import type {
	DirectInstallMCPRequest,
	MCPView,
	OpenAPIImportRequest,
	OpenAPIPreview,
	OpenAPISource,
	UpdateMCPRequest,
} from './types';

/**
 * The user's own library of installed MCPs, which is where a hub install
 * lands. Separate from `workspaceApi`, which manages what one session's
 * workspace actually holds.
 */
export const mcpApi = {
	list: () => client.get<MCPView[]>('/mcp'),

	installDirect: (body: DirectInstallMCPRequest) =>
		client.post<MCPView>('/mcp', body, undefined, { silent: true }),

	/** Reads a spec and lists its operations; saves nothing. */
	previewOpenAPI: (body: OpenAPISource) =>
		client.post<OpenAPIPreview>('/mcp/openapi/preview', body, undefined, { silent: true }),

	/** Imports the chosen operations as tools of a new MCP. */
	importOpenAPI: (body: OpenAPIImportRequest) =>
		client.post<MCPView>('/mcp/openapi', body, undefined, { silent: true }),

	/** Returns the provider sign-in URL to send the browser to. */
	startOAuth: (mcpId: string) =>
		client.post<{ authorize_url: string }>(
			`/mcp/${encodeURIComponent(mcpId)}/oauth/start`,
			null,
		),

	sync: (mcpId: string) =>
		client.post<MCPView>(`/mcp/${encodeURIComponent(mcpId)}/sync`, null),

	/**
	 * Renames, enables/disables, or re-keys it. Changing `values` is a
	 * re-render from the hub card, so the originating hub must still be
	 * registered and reachable.
	 */
	update: (mcpId: string, body: UpdateMCPRequest) =>
		client.patch<MCPView>(`/mcp/${encodeURIComponent(mcpId)}`, body),

	/**
	 * Removes it from the library. Workspaces that already hold this MCP keep
	 * it — the relation is derived by name, not a foreign key.
	 */
	remove: (mcpId: string) => client.delete(`/mcp/${encodeURIComponent(mcpId)}`),
};
