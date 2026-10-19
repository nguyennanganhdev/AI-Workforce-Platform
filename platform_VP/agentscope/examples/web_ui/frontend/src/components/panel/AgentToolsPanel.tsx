import { Search, SearchX, Wrench } from 'lucide-react';
import { useState } from 'react';

import type { AgentData, MCPClientStatus } from '@/api';
import { PanelEmpty } from '@/components/panel/PanelEmpty';
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group';
import { Item, ItemContent, ItemDescription, ItemTitle } from '@/components/ui/item';
import { useTranslation } from '@/i18n/useI18n';

interface AgentToolsPanelProps {
	bindings: NonNullable<AgentData['tool_bindings']>;
	mcps: MCPClientStatus[];
	loading: boolean;
}

export function AgentToolsPanel({ bindings, mcps, loading }: AgentToolsPanelProps) {
	const { t } = useTranslation();
	const [search, setSearch] = useState('');
	const query = search.toLowerCase();
	const filtered = bindings.filter((binding) =>
		`${binding.tool_name} ${binding.mcp_name} ${binding.description ?? ''}`
			.toLowerCase().includes(query),
	);

	return (
		<div className="flex flex-col flex-1 min-h-0 gap-y-2">
			<p className="text-muted-foreground text-sm">{t('panel.agentTools.description')}</p>
			<InputGroup>
				<InputGroupInput
					aria-label={t('panel.agentTools.searchPlaceholder')}
					placeholder={t('panel.agentTools.searchPlaceholder')}
					value={search}
					onChange={(event) => setSearch(event.target.value)}
				/>
				<InputGroupAddon align="inline-end"><Search /></InputGroupAddon>
			</InputGroup>
			{loading ? (
				<p className="m-auto text-muted-foreground text-sm">{t('panel.loading')}</p>
			) : filtered.length === 0 ? (
				<PanelEmpty
					icon={search ? SearchX : Wrench}
					title={t(search ? 'panel.search.emptyTitle' : 'panel.agentTools.emptyTitle')}
					description={search
						? t('panel.search.emptyDescription', { query: search })
						: t('panel.agentTools.emptyDescription')}
				/>
			) : (
				<div className="flex flex-col flex-1 min-h-0 gap-y-2 overflow-y-auto scroll-fade-y">
					{filtered.map((binding) => {
						const mcp = mcps.find((client) => client.name === binding.mcp_name);
						const tool = mcp?.tools.find((item) => item.name === binding.tool_name);
						const available = !!mcp?.is_healthy && !!tool;
						const description = tool?.description || binding.description;
						const status = t(available ? 'panel.mcp.healthy' : 'panel.agentTools.unavailable');
						return (
							<Item key={`${binding.mcp_id}:${binding.tool_name}`} variant="outline">
								<ItemContent>
									<ItemTitle>
										<span className="min-w-0 truncate font-mono text-xs" title={binding.tool_name}>
											{binding.tool_name}
										</span>
										<span role="img" aria-label={status} title={status}
											className={`size-2 shrink-0 rounded-full ${available ? 'bg-green-500' : 'bg-red-500'}`} />
									</ItemTitle>
									<ItemDescription className="text-xs">{binding.mcp_name}</ItemDescription>
									{description && <ItemDescription className="line-clamp-2">{description}</ItemDescription>}
									{!available && (
										<p className="break-words text-xs text-destructive">{mcp?.error || status}</p>
									)}
								</ItemContent>
							</Item>
						);
					})}
				</div>
			)}
		</div>
	);
}
