"""Risk-based consent policy shared by direct and gateway MCP tools."""

from types import SimpleNamespace

import pytest

from agentscope.permission import PermissionBehavior
from agentscope.permission._mcp import (
    mcp_tool_permission,
    mcp_tool_requires_confirmation,
)


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
