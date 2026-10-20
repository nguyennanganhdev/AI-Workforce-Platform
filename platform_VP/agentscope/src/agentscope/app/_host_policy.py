# -*- coding: utf-8 -*-
"""What a user's agent, or a user, may reach on the host itself.

Workspaces are local: an agent's shell and file tools run inside the app
container as the app's user, next to the database password, the JWT
secret and every customer's model key. On a platform where anyone can
sign up, that is the whole server. So by default:

- agents get no workspace tools (shell, file read/write/edit, grep…);
- the workspace browser and downloads stay inside the agent's workspace.

``AGENT_WORKSPACE_TOOLS=true`` and ``WORKSPACE_ALLOW_HOST_PATHS=true``
restore the old behaviour for a trusted, single-tenant host.
"""
import os


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def workspace_tools_allowed() -> bool:
    """Whether agents may get the workspace's shell and file tools."""
    return _flag("AGENT_WORKSPACE_TOOLS")


def host_paths_allowed() -> bool:
    """Whether the workspace browser may leave the workspace root."""
    return _flag("WORKSPACE_ALLOW_HOST_PATHS")


def inside(root: str, path: str) -> bool:
    """Whether ``path`` resolves (symlinks included) under ``root``."""
    root_real = os.path.realpath(root)
    real = os.path.realpath(path)
    return real == root_real or real.startswith(root_real + os.sep)
