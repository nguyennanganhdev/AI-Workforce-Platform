"""Resolve explicit chat consent against the exact stored pending tool call."""

import re
import unicodedata
from dataclasses import dataclass

from ..event import ConfirmResult, UserConfirmResultEvent
from ..message import Msg, ToolCallBlock, ToolCallState
from .storage import StorageBase
from .storage._utils import _ensure_team_members


@dataclass(frozen=True)
class PendingChatAction:
    agent_id: str
    session_id: str
    reply_id: str
    tool_call: ToolCallBlock


def confirmation_still_pending(state, event: UserConfirmResultEvent) -> bool:
    """A retried queue entry must not re-run an already resolved call."""
    if state.reply_id != event.reply_id or not state.context:
        return False
    message = state.context[-1]
    if message.id != event.reply_id or message.role != "assistant":
        return False
    resolved = {block.id for block in message.get_content_blocks("tool_result")}
    pending = {
        block.id
        for block in message.get_content_blocks("tool_call")
        if block.state == ToolCallState.ASKING and block.id not in resolved
    }
    return bool(
        pending.intersection(result.tool_call.id for result in event.confirm_results)
    )


def parse_chat_consent(text: str) -> tuple[bool, str | None] | None:
    """Accept whole explicit decisions, never substrings or model guesses."""
    normalized = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = " ".join(normalized.strip().rstrip(".!。").split())
    match = re.fullmatch(
        r"(toi xac nhan|xac nhan|toi dong y|dong y|confirm|i confirm|yes|"
        r"khong dong y|toi tu choi|tu choi|huy|cancel|decline|no)"
        r"(?:\s+([a-z0-9_-]+))?",
        normalized,
    )
    if match is None:
        return None
    return (
        match[1]
        in {
            "toi xac nhan",
            "xac nhan",
            "toi dong y",
            "dong y",
            "confirm",
            "i confirm",
            "yes",
        },
        match[2],
    )


async def pending_chat_actions(
    storage: StorageBase,
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[PendingChatAction]:
    """Read authoritative state; projections cannot grant consent."""
    session = await storage.get_session(user_id, agent_id, session_id)
    if session is None:
        return []
    sessions = [session]
    if session.team_id:
        team = await storage.get_team(user_id, session.team_id)
        if team is not None and team.session_id == session.id:
            for member in await _ensure_team_members(storage, user_id, team):
                worker = await storage.get_session(
                    user_id, member.agent_id, member.session_id
                )
                if worker is not None and worker.id != session.id:
                    sessions.append(worker)
    pending = []
    for owner in sessions:
        for message in owner.state.context:
            if message.role != "assistant" or message.id != owner.state.reply_id:
                continue
            resolved_ids = {
                result.id for result in message.get_content_blocks("tool_result")
            }
            for call in message.get_content_blocks("tool_call"):
                if call.state == ToolCallState.ASKING and call.id not in resolved_ids:
                    pending.append(
                        PendingChatAction(owner.agent_id, owner.id, message.id, call)
                    )
    return pending


def resolve_chat_consent(
    message: Msg,
    pending: list[PendingChatAction],
) -> tuple[PendingChatAction, UserConfirmResultEvent] | None:
    if message.role != "user" or any(block.type != "text" for block in message.content):
        return None
    decision = parse_chat_consent(message.get_text_content() or "")
    if decision is None:
        return None
    confirmed, reference = decision
    candidates = (
        pending
        if reference is None
        else [
            item
            for item in pending
            if reference
            in {item.tool_call.id.casefold(), item.tool_call.id[-8:].casefold()}
        ]
    )
    if len(candidates) != 1:
        return None
    action = candidates[0]
    return action, UserConfirmResultEvent(
        id=message.id,
        reply_id=action.reply_id,
        confirm_results=[
            ConfirmResult(
                confirmed=confirmed,
                tool_call=action.tool_call.model_copy(deep=True),
                rules=None,
            )
        ],
    )
