"""Audience and minimal-tool contracts for direct and partner conversations."""

from agentscope.app._workforce_policy import conversation_policy


def test_direct_conversation_is_not_an_external_ticket():
    policy = conversation_policy("platform_chat", "session-a")
    assert '"source": "platform_chat"' in policy
    assert '"external_ticket_id": null' in policy
    assert "person typing here IS the user" in policy
    assert "session-b" not in policy


def test_partner_conversations_keep_distinct_ticket_bindings():
    first = conversation_policy(
        "partner_api", "conversation-a", external_ticket_id="ticket-a"
    )
    second = conversation_policy(
        "partner_api", "conversation-b", external_ticket_id="ticket-b"
    )
    assert '"source": "partner_api"' in first
    assert "ticket-a" in first and "ticket-b" not in first
    assert "ticket-b" in second and "conversation-a" not in second
