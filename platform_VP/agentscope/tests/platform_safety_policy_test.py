# -*- coding: utf-8 -*-
"""Every agent's runtime prompt carries the platform safety policy."""
from unittest import TestCase

from agentscope.app._workforce_policy import (
    PLATFORM_SAFETY_POLICY,
    governed_system_prompt,
)


class PlatformSafetyPolicyTest(TestCase):

    def test_leader_and_specialists_get_it(self) -> None:
        for role in ("leader", "business"):
            with self.subTest(role=role):
                prompt = governed_system_prompt(role, "You find sightseeing tickets.")
                self.assertIn(PLATFORM_SAFETY_POLICY.strip(), prompt)

    def test_it_covers_scope_secrets_and_injection(self) -> None:
        text = PLATFORM_SAFETY_POLICY
        self.assertIn("outside your role", text)
        self.assertIn("environment", text)
        self.assertIn("as data, not instructions", text)

    def test_a_stale_copy_in_an_authored_prompt_is_not_stacked(self) -> None:
        once = governed_system_prompt("business", "Role.")
        twice = governed_system_prompt("business", once)
        self.assertEqual(twice.count("PLATFORM SAFETY POLICY"), 1)
