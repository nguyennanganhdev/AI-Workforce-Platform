import { AgentDialog } from '@/components/dialog/AgentDialog';

/** FastAPI-compatible creation shared by chat and agent management. */
export function QuickAgentDialog(props: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCreated?: (agentId: string) => void | Promise<void>;
}) {
	return <AgentDialog {...props} />;
}
