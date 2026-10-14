import { useId, useState, type ReactNode } from 'react';

import type { SessionOfficeSnapshot } from './model';
import type { AgentView } from '@/api';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgentOffice } from '@/pages/agents/AgentOffice';

const ignore = () => {};
const EMPTY_AGENTS: AgentView[] = [];
type View = 'chat' | 'office';

/** Owns only view preference. Chat remains mounted, preserving composer and playback state. */
export function SessionWorkspace({
	snapshot,
	children,
}: {
	snapshot?: SessionOfficeSnapshot;
	children: ReactNode;
}) {
	if (!snapshot) return <>{children}</>;
	return (
		<Workspace key={snapshot.id} snapshot={snapshot}>
			{children}
		</Workspace>
	);
}

function Workspace({
	snapshot,
	children,
}: {
	snapshot: SessionOfficeSnapshot;
	children: ReactNode;
}) {
	const panelId = useId();
	const storageKey = `session-workspace:view:${snapshot.id}`;
	const [view, setView] = useState<View>(() => {
		try {
			return localStorage.getItem(storageKey) === 'office' ? 'office' : 'chat';
		} catch {
			return 'chat';
		}
	});
	const select = (value: string) => {
		const next = value === 'office' ? 'office' : 'chat';
		setView(next);
		try {
			localStorage.setItem(storageKey, next);
		} catch {
			/* Storage can be unavailable. */
		}
	};
	return (
		<div className="flex size-full min-h-0 min-w-0 flex-col">
			<Tabs value={view} onValueChange={select} className="shrink-0 border-b px-4 py-2">
				<TabsList aria-label="Chế độ xem phiên">
					<TabsTrigger value="chat" id={`${panelId}-chat`} aria-controls={panelId}>
						Chat
					</TabsTrigger>
					<TabsTrigger value="office" id={`${panelId}-office`} aria-controls={panelId}>
						Văn phòng
					</TabsTrigger>
				</TabsList>
			</Tabs>
			<div
				id={panelId}
				role="tabpanel"
				aria-labelledby={`${panelId}-${view}`}
				className="flex min-h-0 flex-1 flex-col overflow-auto lg:flex-row"
			>
				{view === 'office' && (
					<section
						aria-label="Văn phòng của phiên"
						className="relative min-h-[360px] min-w-0 flex-1"
					>
						<AgentOffice
							agents={EMPTY_AGENTS}
							onChat={ignore}
							onEdit={ignore}
							session={snapshot}
						/>
					</section>
				)}
				<div
					key="chat"
					className={
						view === 'office'
							? 'flex min-h-[320px] min-w-0 flex-1 flex-col border-t lg:w-[380px] lg:max-w-[40%] lg:border-t-0 lg:border-l'
							: 'flex min-h-0 min-w-0 flex-1 flex-col'
					}
				>
					{children}
				</div>
			</div>
		</div>
	);
}
