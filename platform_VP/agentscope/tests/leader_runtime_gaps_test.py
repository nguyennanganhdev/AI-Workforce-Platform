"""Regressions for provider wakes, repeated questions and evidence authority."""

import json

import pytest

import tests.team_collaboration_test as collaboration_fixture
from agentscope.app._evidence_claims import EvidenceSource, validate_claims
from agentscope.app._shared_context import SharedContextConfig, SharedContextService
from agentscope.app._tool._team_say import _derived_question_key
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.workforce.integrations.unified._case import check_say
from tests.team_shared_context_test import _MeasuredModel, _Storage


@pytest.mark.asyncio
async def test_provider_notification_preserves_its_current_verified_quote():
    store = _Storage()
    service = SharedContextService(store, InMemoryMessageBus())
    customer = await service.append_event(
        user_id="u",
        team_id="t",
        kind="customer_message",
        content="Check the quote for this ticket",
    )
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="external_event",
        content='{"total":50000,"currency":"VND"}',
        event_id="signed-quote",
        source_session_id="leader",
    )
    # A provider wake is a system event, not a new customer requirement.
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="external_event",
        content="(Hệ thống) Sự kiện mới: E17 job.quote_ready",
        source_session_id="leader",
    )
    claims = await service.validate_customer_reply_claims("u", "t", "Tổng 50.000đ.")
    record = await store.get_team_shared_context("u", "t")
    assert (
        record.state.tasks[customer.task_id].latest_customer_revision
        == customer.revision
    )
    assert claims.unsupported == ()


@pytest.mark.asyncio
async def test_asking_for_location_already_in_customer_input_is_rejected():
    case = collaboration_fixture.TestCollaboration(
        "test_worker_question_is_only_a_proposal_owner_approves_one"
    )
    await case.asyncSetUp()
    await case.service.append_event(
        user_id="u",
        team_id="ticket-1",
        kind="customer_message",
        content="Tôi đang ở hầm B2, Tòa OP2-A. Nước rò từ trần sát tủ điện.",
    )
    result = await case.tool("leader")(kind="ask_customer", content="Bạn đang ở đâu?")
    assert result.state == "error"


def test_equivalent_questions_share_the_same_missing_field_key():
    assert _derived_question_key("Bạn đang ở đâu?") == _derived_question_key(
        "Bạn cho biết vị trí xảy ra sự cố?"
    )


def test_known_floor_does_not_answer_a_new_location_detail_question():
    from agentscope.app._customer_questions import question_fields

    assert question_fields("Vị trí sự cố ở cột nào?") == ()


def test_closed_claim_cannot_be_supported_by_resolved_unaccepted_ticket():
    result = validate_claims(
        "Phiếu đã đóng và cư dân đã nghiệm thu.",
        [
            '{"ticket_status":"resolved","confirmation":{"resident_accepted":false,"ticket_closed":false}}'
        ],
    )
    assert result.unsupported


def test_negative_fee_policy_does_not_unlock_free_claim():
    rules = {"phrase_rules": [{"phrases": ["được miễn phí"], "unless": ["miễn phí"]}]}
    assert check_say(
        "Bạn được miễn phí.", ["E1"], rules, {"E1": "Dịch vụ này không miễn phí."}, []
    )
    assert not check_say(
        "Bạn không được miễn phí.",
        ["E1"],
        rules,
        {"E1": "Dịch vụ này không miễn phí."},
        [],
    )


def test_customer_prose_cannot_certify_domain_acceptance():
    text = "Phiếu đã đóng và cư dân đã nghiệm thu."
    source = '{"confirmation":{"resident_accepted":true,"ticket_closed":true}}'
    assert validate_claims(
        text, [EvidenceSource(source, "customer", authority="customer")]
    ).unsupported
    assert not validate_claims(
        text, [EvidenceSource(source, "signed-tool")]
    ).unsupported
    assert not validate_claims(
        "Phiếu chưa đóng.", ['{"ticket_closed":false}']
    ).unsupported


@pytest.mark.asyncio
async def test_long_partner_history_stays_retrievable_without_summary_model():
    store = _Storage()
    service = SharedContextService(
        store, InMemoryMessageBus(), SharedContextConfig(packet_max_tokens=6000)
    )
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="customer_message",
        content="Repair the leak at B2",
    )
    original = "inspection detail " * 2000
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="external_event",
        content=json.dumps(
            {
                "tool_result": {
                    "output": [{"text": "E1: " + original}],
                    "metadata": {"external_evidence": True},
                }
            }
        ),
        event_id="large-tool-source",
    )
    model = _MeasuredModel(fail_summary=True)
    packet, tokens = await service.prepare_packet(model=model, user_id="u", team_id="t")
    record = await store.get_team_shared_context("u", "t")
    assert tokens <= 6000
    assert "CaseEvidence" in packet
    assert original in record.state.events[-1].content
    assert model.summary_calls == 0


@pytest.mark.asyncio
async def test_prior_assistant_reply_does_not_override_new_authoritative_price():
    store = _Storage()
    service = SharedContextService(store, InMemoryMessageBus())
    await service.append_event(
        user_id="u", team_id="t", kind="customer_message", content="Check Hotel Alpha"
    )
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="customer_reply",
        content="Hotel Alpha costs 100 USD per night.",
        source_session_id="leader",
    )
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="customer_message",
        content="Check its current price again",
    )
    await service.append_event(
        user_id="u",
        team_id="t",
        kind="external_event",
        content='{"name":"Hotel Alpha","price_per_night_usd":200}',
        source_session_id="worker",
    )
    claims = await service.validate_customer_reply_claims(
        "u", "t", "Hotel Alpha costs 200 USD per night."
    )
    assert claims.unsupported == ()
