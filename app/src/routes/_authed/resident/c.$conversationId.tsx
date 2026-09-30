import { createFileRoute } from '@tanstack/react-router';
import { ChatView } from '@/features/vinhomes-resident';

function ConversationRoute() {
  const { conversationId } = Route.useParams();
  return <ChatView key={conversationId} conversationId={conversationId} />;
}

export const Route = createFileRoute('/_authed/resident/c/$conversationId')({
  component: ConversationRoute,
});
