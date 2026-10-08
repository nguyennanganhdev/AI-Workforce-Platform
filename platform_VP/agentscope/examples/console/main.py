# -*- coding: utf-8 -*-
"""Try a full-featured agent in the terminal via ``launch_console``.

The agent is backed by the chat model of the chosen provider (``--provider``
/ ``MODEL_PROVIDER``, ``--model`` / ``MODEL_NAME``) and assembled from a
``LocalWorkspace``: the builtin filesystem tools and the agent skills
both come from the workspace, and the filesystem-backed long-term
memory (``AgenticMemoryMiddleware``) persists durable facts under the
workspace directory across runs. The whole terminal interaction —
rendering, tool-call confirmation, Ctrl+C interruption — is handled
by ``launch_console``. Run with::

    export DASHSCOPE_API_KEY=sk-...
    python main.py [--model qwen3.7-max] [--verbosity default] \
        [--workdir ./workspace]
"""
import argparse
import asyncio
import os

from agentscope.agent import Agent
from agentscope.console import launch_console
from agentscope.credential import (
    AnthropicCredential,
    DashScopeCredential,
    GeminiCredential,
    OpenAICredential,
)
from agentscope.middleware import AgenticMemoryMiddleware
from agentscope.model import (
    AnthropicChatModel,
    DashScopeChatModel,
    GeminiChatModel,
    OpenAIChatModel,
)
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

# provider -> (API key env var, credential class, model class, default model)
PROVIDERS = {
    "dashscope": (
        "DASHSCOPE_API_KEY",
        DashScopeCredential,
        DashScopeChatModel,
        "qwen3.7-max",
    ),
    "anthropic": (
        "ANTHROPIC_API_KEY",
        AnthropicCredential,
        AnthropicChatModel,
        "claude-sonnet-5",
    ),
    "openai": (
        "OPENAI_API_KEY",
        OpenAICredential,
        OpenAIChatModel,
        "gpt-5.5",
    ),
    "gemini": (
        "GEMINI_API_KEY",
        GeminiCredential,
        GeminiChatModel,
        "gemini-3.5-flash",
    ),
}


async def main() -> None:
    """The main entry point of the demo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        default=os.environ.get("MODEL_PROVIDER") or "dashscope",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MODEL_NAME") or None,
        help="The model name; defaults to the provider's default model.",
    )
    parser.add_argument(
        "--verbosity",
        choices=["quiet", "default", "debug"],
        default="default",
    )
    parser.add_argument(
        "--workdir",
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "workspace",
        ),
        help="The workspace root directory.",
    )
    args = parser.parse_args()

    key_env, credential_cls, model_cls, default_model = PROVIDERS[
        args.provider
    ]
    api_key = os.environ.get(key_env)
    if not api_key:
        raise RuntimeError(
            f"Set the {key_env} environment variable before "
            "running this demo.",
        )
    # Optional endpoint override, e.g. the DashScope international region
    credential_kwargs = {"api_key": api_key}
    if os.environ.get("MODEL_BASE_URL"):
        credential_kwargs["base_url"] = os.environ["MODEL_BASE_URL"]

    async with LocalWorkspace(workdir=args.workdir) as workspace:
        agent = Agent(
            name="Friday",
            system_prompt=(
                "You are a helpful assistant named Friday. Use the "
                "provided tools whenever they help answering the "
                "question.\n\n" + await workspace.get_instructions()
            ),
            model=model_cls(
                credential=credential_cls(**credential_kwargs),
                model=args.model or default_model,
                stream=True,
            ),
            toolkit=Toolkit(
                # Filesystem tools and skills both come from the
                # workspace, bound to its backend and skill partition
                tools=await workspace.list_tools(),
                skills_or_loaders=await workspace.list_skills(),
            ),
            middlewares=[
                AgenticMemoryMiddleware(
                    workdir=workspace.workdir,
                    backend=workspace.get_backend(),
                ),
            ],
            # Offload compressed context and oversized tool results
            # into the workspace
            offloader=workspace,
        )
        await launch_console(agent, verbosity=args.verbosity)


if __name__ == "__main__":
    asyncio.run(main())
