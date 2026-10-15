import { ArrowRight, BookText, KeyRound, LibraryBig } from 'lucide-react';
import type { ComponentType } from 'react';
import { useNavigate } from 'react-router-dom';

import MCPSvg from '@/assets/images/mcp.svg?react';
import { useTranslation } from '@/i18n/useI18n';

const SHELVES: {
	key: 'mcp' | 'skill' | 'knowledge' | 'credential';
	icon: ComponentType<{ className?: string }>;
	path: string;
}[] = [
	{ key: 'mcp', icon: MCPSvg, path: '/mcp' },
	{ key: 'skill', icon: BookText, path: '/skill' },
	{ key: 'knowledge', icon: LibraryBig, path: '/knowledge' },
	{ key: 'credential', icon: KeyRound, path: '/credential' },
];

/**
 * What the agents can be given. Each shelf already has a page of its own in
 * this shell; this view is the way to them from the agents' side.
 */
export function AgentLibrary() {
	const { t } = useTranslation();
	const navigate = useNavigate();

	return (
		<div className="h-full overflow-y-auto p-6">
			<p className="mb-4 max-w-prose text-sm text-muted-foreground">
				{t('agents.library.intro')}
			</p>
			<ul className="grid gap-3 sm:grid-cols-2">
				{SHELVES.map(({ key, icon: Icon, path }) => (
					<li key={key}>
						<button
							type="button"
							onClick={() => navigate(path)}
							className="group flex w-full items-center gap-3 rounded-[var(--r-tile)] border border-[var(--line)] bg-[var(--raised)] p-4 text-left shadow-[var(--clay-bubble)] hover:bg-[var(--action-soft)]"
						>
							<span className="flex size-9 shrink-0 items-center justify-center rounded-[13px] bg-[var(--sunken)] text-[var(--ink-2)]">
								<Icon className="size-4" />
							</span>
							<span className="min-w-0 flex-1">
								<span className="block text-[14px]/[20px] font-semibold">
									{t(`agents.library.${key}.title`)}
								</span>
								<span className="block text-[12px]/[16px] text-muted-foreground">
									{t(`agents.library.${key}.description`)}
								</span>
							</span>
							<ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
						</button>
					</li>
				))}
			</ul>
		</div>
	);
}
