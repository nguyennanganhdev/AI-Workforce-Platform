"""Risk-based consent policy shared by direct and gateway MCP tools."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

import pytest

from agentscope.permission import (
    PermissionBehavior, PermissionContext, PermissionEngine, PermissionMode, PermissionRule,
)
from agentscope.permission._mcp import (
    mcp_tool_permission,
    mcp_tool_requires_confirmation,
)


@pytest.mark.parametrize("tool_name,schema", [
    ("run_shell", {}), ("Bash", {}), ("sudo", {}), ("executeCode", {}),
    ("execute_script", {}), ("browser_evaluate", {"properties": {"function": {}}}),
    ("helper", {"properties": {"command": {"type": "string"}}}),
    ("helper", {"$defs": {"Input": {"properties": {"sourceCode": {}}}}}),
])
def test_code_execution_mcp_tools_are_denied_even_with_read_only_hint(tool_name, schema):
    hint = SimpleNamespace(readOnlyHint=True)
    assert mcp_tool_permission(tool_name, hint, schema).behavior == PermissionBehavior.DENY
    assert mcp_tool_requires_confirmation(tool_name, hint, schema)


def test_booking_confirmation_codes_are_not_execution_inputs():
    decision = mcp_tool_permission(
        "lookup_booking_code", None,
        {"properties": {"confirmation_code": {"type": "string"}}},
    )
    assert decision.behavior == PermissionBehavior.ASK


class TestExecutionBan(IsolatedAsyncioTestCase):
    async def test_all_modes_deny_before_read_only_and_saved_allow_rules(self):
        tool = SimpleNamespace(
            name="mcp__server__helper", is_mcp=True, is_read_only=True,
            input_schema={"properties": {"command": {"type": "string"}}},
            check_permissions=AsyncMock(), check_read_only=AsyncMock(return_value=True),
        )
        for mode in PermissionMode:
            with self.subTest(mode=mode):
                engine = PermissionEngine(PermissionContext(mode=mode))
                engine.add_rule(PermissionRule(
                    tool_name=tool.name, rule_content="*", behavior=PermissionBehavior.ALLOW,
                    source="userSettings",
                ))
                decision = await engine.check_permission(tool, {"command": "sudo id"})
                self.assertEqual(decision.behavior, PermissionBehavior.DENY)
        tool.check_permissions.assert_not_awaited()
        tool.check_read_only.assert_not_awaited()


@pytest.mark.parametrize(
    "tool_name",
    [
        "search_hotels",
        "check_hotel_availability",
        "calculate_trip_cost",
        "update_itinerary_draft",
    ],
)
def test_low_risk_mcp_tools_run_without_confirmation(tool_name: str) -> None:
    decision = mcp_tool_permission(tool_name, None, {"properties": {}})

    assert decision.behavior == PermissionBehavior.ALLOW


def test_restaurant_search_dates_are_not_mistaken_for_booking() -> None:
    decision = mcp_tool_permission(
        "search_restaurants",
        None,
        {
            "properties": {
                "city": {"type": "string"},
                "reservation_date": {"type": "string"},
                "reservation_time": {"type": "string"},
                "party_size": {"type": "integer"},
                "max_average_price_per_person": {"type": "integer"},
            },
        },
    )

    assert decision.behavior == PermissionBehavior.ALLOW


@pytest.mark.parametrize(
    "tool_name",
    [
        "book_hotel",
        "cancel_bus_booking",
        "pay_invoice",
        "update_customer_profile",
        "thanh_toan_don_hang",
    ],
)
def test_sensitive_mcp_tools_require_confirmation(tool_name: str) -> None:
    decision = mcp_tool_permission(tool_name, None, {"properties": {}})

    assert decision.behavior == PermissionBehavior.ASK
    assert decision.bypass_immune is True


def test_destructive_annotation_and_personal_fields_require_confirmation() -> None:
    destructive = mcp_tool_permission(
        "execute",
        SimpleNamespace(destructiveHint=True),
        {"properties": {}},
    )
    personal = mcp_tool_permission(
        "lookup",
        None,
        {"properties": {"passport_number": {"type": "string"}}},
    )

    assert destructive.behavior == PermissionBehavior.ASK
    assert personal.behavior == PermissionBehavior.ASK
    assert mcp_tool_requires_confirmation(
        "get_customer_profile",
        SimpleNamespace(readOnlyHint=True),
        {"properties": {}},
    )
