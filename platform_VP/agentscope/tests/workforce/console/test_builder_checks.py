import unittest


def _agent(**overrides):
    from agentscope.app._router._workforce_console import GeneratedAgent

    values = {
        "name": "Điều phối trưởng dịch vụ",
        "objective": "Tiếp nhận yêu cầu và điều phối sang agent chuyên trách.",
        "system_prompt": "Bạn là điều phối viên. " * 6,
        "skill_name": "dieu-phoi",
        "skill_markdown": "# Điều phối\nChia việc cho đúng chuyên viên qua TeamSay.",
    }
    return GeneratedAgent(**{**values, **overrides})


class BuilderChecksTest(unittest.TestCase):
    def test_a_coordinator_without_tools_passes(self):
        from agentscope.app._router._workforce_console import _agent_checks

        checks = _agent_checks(_agent(needs_tools=False), [], [], [])
        self.assertTrue(all(checks.values()), checks)

    def test_an_agent_that_needs_tools_but_has_none_fails(self):
        from agentscope.app._router._workforce_console import _agent_checks

        checks = _agent_checks(_agent(), [], [], [])
        self.assertFalse(checks["capability_has_tools"])

    def test_an_agent_with_its_tool_passes(self):
        from agentscope.app._router._workforce_console import BuilderTool, _agent_checks

        tool = BuilderTool(id="t1", mcp_id="m1", mcp_name="vinhomes", tool_name="vh_ticket_get")
        self.assertTrue(all(_agent_checks(_agent(), [tool], [], []).values()))


if __name__ == "__main__":
    unittest.main()
