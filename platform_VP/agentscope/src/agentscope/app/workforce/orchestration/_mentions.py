"""ID-based member and pending-question routing; no name guessing."""

from ._models import require


def resolve_recipient(run, conversation, *, target_agent_id=None, mention_name=None,
                      reply_to_message_id=None):
    require(run.conversation_id == conversation.conversation_id and run.scope == conversation.scope,
            "CONTEXT_BINDING_INVALID")
    members = {m["agent_id"]: m for m in run.members}
    if target_agent_id is not None:
        require(target_agent_id in members, "MEMBER_NOT_FOUND")
        return members[target_agent_id]["session_id"]
    if mention_name is not None:
        matches = [m for m in run.members if m.get("name") == mention_name]
        require(len(matches) == 1, "MENTION_AMBIGUOUS" if matches else "MEMBER_NOT_FOUND")
        return matches[0]["session_id"]
    questions = list(conversation.pending_questions.values())
    if reply_to_message_id is not None:
        messages = [m for m in conversation.messages if m["message_id"] == reply_to_message_id]
        require(len(messages) == 1, "MESSAGE_REFERENCE_INVALID")
        questions = [q for q in questions if q["message_id"] == reply_to_message_id]
        if not questions:
            agent_id = messages[0].get("agent_id")
            require(agent_id in members, "REPLY_TARGET_REQUIRED")
            return members[agent_id]["session_id"]
    if questions:
        require(len(questions) == 1, "PENDING_QUESTION_AMBIGUOUS")
        session = questions[0]["session_id"]
        require(session in {run.leader_session_id} | {m["session_id"] for m in run.members}, "QUESTION_TARGET_INVALID")
        return session
    return run.leader_session_id


def resolve_entity(conversation, entity_kind, *, explicit_ref=None):
    candidates = conversation.facts.get("candidates", {}).get(entity_kind, [])
    reference = explicit_ref or conversation.selected_refs.get(entity_kind)
    if reference is not None:
        matches = [c for c in candidates if c["id"] == reference]
    else:
        matches = candidates
    require(len(matches) == 1, "ENTITY_AMBIGUOUS" if matches else "ENTITY_NOT_FOUND")
    return matches[0]
