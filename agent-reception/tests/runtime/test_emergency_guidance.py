"""Safety guidance in an emergency reply: only what the backend marks approved, word for word."""

import asyncio

from src.agent.loop import EMERGENCY_REPLY
from src.graph.assessment import parse_request_policy
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

    def __init__(self, policy):
        self.policy, self.operations = policy, []

    async def call(self, method, path, context, body=None):
        if path.endswith("/context"):
            return {"history": [{"role": "resident", "text": MESSAGE["text"]}], "open_request": None, "past_requests": []}
        if path.endswith("/catalog"):
            return {"categories": [{"id": "c1", "code": "technical", "name": "Kỹ thuật"}]}
        assert path.endswith("/policy/evaluate")
        return self.policy

    async def execute(self, context, operation, value, key):
        self.operations.append(operation)
        return {"get_verified_resident_context": {"resident": {"name": "Cư dân"}, "residences": [HOME]},
                "create_ticket_draft": {"draftId": "draft-1"},
                "resolve_management_destination": {"managementUnitId": "unit-1"},
                "handoff_ticket": {"accepted": True, "ticket": {"id": "t1", "code": "VH-1"}}}.get(operation, {})


def turn(policy):
    backend = Backend(policy)
    reply, code = asyncio.run(agent_turn(backend, None, None, None, CONTEXT, MESSAGE))
    assert code == "VH-1" and backend.operations[-1] == "escalate_emergency"
    return reply


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
