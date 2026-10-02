"""AgentScope public Agent.reply wrapper delegating one invocation to Openbot.

Stateless interface subclass: no Agent local model/react/tool loop is initialized
or run. Remote specialist/tool execution belongs to OpenbotAdapter exclusively.
RoomService continues to own scheduling, tasks, mailbox and ACL projections.
"""
import importlib.metadata
from agentscope.agent import Agent
from agentscope.message import AssistantMsg, TextBlock
from groupchat.models import AgentOutput


def require_sdk():
    if importlib.metadata.version('agentscope') != '2.0.9':
        raise ValueError('Coordination requires tested AgentScope 2.0.9')


class RemoteOpenbotAgent(Agent):
    def __init__(self, remote, invocation):
        require_sdk()
        self.remote,self.invocation = remote,invocation
        self.name = invocation.participant.framework_agent_id

    async def reply(self, inputs=None):
        # Inputs cannot widen context: immutable Invocation is built under Room ACL.
        output = await self.remote.invoke(self.invocation)
        return AssistantMsg(name=self.name,content=[TextBlock(text=output.model_dump_json())])


class AgentScopeRemoteAdapter:
    def __init__(self, remote):
        require_sdk()
        self.remote=remote

    async def prepare(self, invocation): await self.remote.prepare(invocation)

    async def invoke(self, invocation):
        agent=RemoteOpenbotAgent(self.remote,invocation)
        reply=await agent.reply()
        return AgentOutput.model_validate_json(reply.get_text_content())

    async def cancel(self, invocation): return await self.remote.cancel(invocation)
