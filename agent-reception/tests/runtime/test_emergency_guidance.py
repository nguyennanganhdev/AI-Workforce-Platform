"""Safety guidance in an emergency reply: only what the backend marks approved, word for word."""

import asyncio

from src.agent.loop import EMERGENCY_FAILED_REPLY, EMERGENCY_REPLY
from src.graph.assessment import parse_request_policy
from src.runtime.backend import OperationRejected
from src.runtime.service import agent_turn, safety_line

ANSWER = "Anh chị không bật công tắc điện, mở cửa nếu an toàn, rồi gọi an ninh và đơn vị gas."
# The shape the backend's request policy returns for an approved candidate (v3_learning.approved_guidance).
GUIDE = {"approved": True, "answer": ANSWER, "retrievalRunId": "guidance:7f0c",
         "citations": [{"documentId": "7f0c", "version": "1", "chunkId": "9a1e"}]}
POLICY = {"policy_version": "p1", "emergency": True, "staff_required": True, "self_help_allowed": False,
          "missing_information": [], "handoff_reason": "emergency"}
CONTEXT = {"channelId": "chat-1"}
MESSAGE = {"id": "m1", "text": "Bếp nhà tôi có mùi gas rất nặng"}
HOME = {"domain_id": "d1", "building_id": "b1", "unit_id": "u1", "unit_code": "1201"}


class Backend:
    """Answers what one emergency turn asks of the backend, and records the operations it ran."""

    def __init__(self, policy, homes=(HOME,), refuse=None):
        self.policy, self.operations, self.homes, self.refuse, self.sent = policy, [], list(homes), refuse, {}

    async def call(self, method, path, context, body=None):
        if "/context" in path:
            return {"history": [{"role": "resident", "text": MESSAGE["text"]}], "open_request": None, "past_requests": []}
        if path.endswith("/catalog"):
            return {"categories": [{"id": "c1", "code": "technical", "name": "Kỹ thuật"}]}
        if path.endswith("/intake"):
            # An emergency is not questioned: the backend returns the resident's message as the report.
            assert body == {"message_id": "m1", "details": {}, "kind": "incident", "emergency": True}
            return {"ready": True, "review": False, "missing": None, "question": None, "title": MESSAGE["text"],
                    "description": MESSAGE["text"], "facts": [], "rejected": [], "file_ids": []}
        assert path.endswith("/policy/evaluate")
        return self.policy

    async def execute(self, context, operation, value, key):
        self.operations.append(operation)
        self.sent[operation] = value
        if operation == self.refuse:
            raise OperationRejected("BACKEND_HTTP_409")
        return {"get_verified_resident_context": {"resident": {"name": "Cư dân"}, "residences": self.homes},
                "create_ticket_draft": {"draftId": "draft-1"},
                "resolve_management_destination": {"managementUnitId": "unit-1"},
                "handoff_ticket": {"accepted": True, "ticket": {"id": "t1", "code": "VH-1"}}}.get(operation, {})


def turn(policy):
    backend = Backend(policy)
    reply, asked = asyncio.run(agent_turn(backend, None, None, None, CONTEXT, MESSAGE))
    assert asked is None and backend.operations[-1] == "escalate_emergency"
    # The request carries no wording of the runtime: the backend records the resident's message.
    assert "title" not in backend.sent["update_ticket_incident"]["fields"]
    assert "description" not in backend.sent["update_ticket_incident"]["fields"]
    return reply


def test_the_resident_is_told_to_call_when_the_emergency_could_not_be_filed():
    for refused in ("handoff_ticket", "escalate_emergency"):
        backend = Backend(POLICY, refuse=refused)
        reply, _ = asyncio.run(agent_turn(backend, None, None, None, CONTEXT, MESSAGE))
        assert reply == EMERGENCY_FAILED_REPLY, refused
    nowhere = Backend(POLICY, homes=())
    assert asyncio.run(agent_turn(nowhere, None, None, None, CONTEXT, MESSAGE))[0] == EMERGENCY_FAILED_REPLY


def test_a_resident_with_two_homes_still_reports_an_emergency():
    backend = Backend(POLICY, homes=(HOME, {**HOME, "unit_id": "u2", "unit_code": "1502"}))
    reply, _ = asyncio.run(agent_turn(backend, None, None, None, CONTEXT, MESSAGE))
    assert reply == EMERGENCY_REPLY and backend.sent["update_ticket_incident"]["fields"]["unit_id"] == "u1"
    assert "nhiều căn hộ" in backend.sent["submit_ticket_assessment"]["assessment"]["reason"]


def test_the_graph_accepts_the_backends_guidance_shape():
    assert parse_request_policy({**POLICY, "safety_guidance": GUIDE})["safety_guidance"]["answer"] == ANSWER
    unapproved = parse_request_policy({**POLICY, "safety_guidance": {**GUIDE, "approved": False}})
    assert "safety_guidance" not in unapproved


def test_approved_guidance_follows_the_fixed_emergency_sentence():
    assert turn({**POLICY, "safety_guidance": GUIDE}) == EMERGENCY_REPLY + "\n" + ANSWER


def test_without_approved_guidance_the_reply_is_the_fixed_sentence_alone():
    assert turn(POLICY) == EMERGENCY_REPLY
    assert turn({**POLICY, "safety_guidance": {**GUIDE, "approved": False}}) == EMERGENCY_REPLY
    assert safety_line({"safety_guidance": {"approved": True, "answer": "  "}}) == ""
