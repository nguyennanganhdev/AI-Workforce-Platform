# -*- coding: utf-8 -*-
"""A local workspace's directory is named by the agent id, so only plain
ids may reach the filesystem."""
import tempfile
from unittest import IsolatedAsyncioTestCase

from agentscope.app.workspace_manager import LocalWorkspaceManager


class LocalWorkspaceManagerIdTest(IsolatedAsyncioTestCase):

    async def test_path_like_agent_ids_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = LocalWorkspaceManager(basedir=tmp)
            for agent_id in ("..", "../etc", "/", "a/b", ""):
                with self.subTest(agent_id=agent_id), self.assertRaises(ValueError):
                    await manager.get_workspace("u", agent_id, "s", "ws-" + str(len(agent_id)))
            workspace = await manager.get_workspace("u", "agent_1", "s", "ws-ok")
            self.assertTrue(workspace.workdir.startswith(tmp))
