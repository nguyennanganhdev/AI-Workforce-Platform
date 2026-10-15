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

    def test_a_library_skill_stands_in_for_a_written_one(self):
        from agentscope.app._router._workforce_console import _agent_checks

        agent = _agent(needs_tools=False, skill_name="", skill_markdown="", library_skill_ids=["sk-1"])
        self.assertFalse(_agent_checks(agent, [], [], [])["skill"])
        checks = _agent_checks(agent, [], [], [], [{"skill_id": "sk-1", "name": "dieu-phoi"}], [])
        self.assertTrue(all(checks.values()), checks)

    def test_unknown_knowledge_or_skill_ids_fail(self):
        from agentscope.app._router._workforce_console import _agent_checks

        checks = _agent_checks(_agent(needs_tools=False, knowledge_ids=["kb-x"]), [], [], [], [], ["kb-x"])
        self.assertFalse(checks["registered_library"])

    def test_the_published_spec_carries_knowledge_and_library_skills(self):
        from agentscope.app._router._workforce_console import _FIXED_CONTEXT, _FIXED_REACT, _seed_spec
        from agentscope.app.storage import AgentData, AgentRecord

        record = AgentRecord(user_id="u", data=AgentData(
            name="Lễ tân", system_prompt="Bạn là lễ tân.", system_role="business",
            context_config=_FIXED_CONTEXT.model_copy(deep=True), react_config=_FIXED_REACT.model_copy(deep=True),
        ))
        _seed_spec(
            record,
            [{"scenario": "Cư dân hỏi giờ hồ bơi", "expected": "Trả lời theo nội quy"}],
            [{"kb_id": "kb-1", "name": "Nội quy"}],
            [{"skill_id": "sk-1", "name": "tiep-nhan"}],
        )
        self.assertEqual([{"kb_id": "kb-1", "name": "Nội quy", "use_for": ""}], record.data.spec["knowledge"])
        self.assertEqual("sk-1", record.data.spec["skills"][0]["skill_id"])


if __name__ == "__main__":
    unittest.main()
