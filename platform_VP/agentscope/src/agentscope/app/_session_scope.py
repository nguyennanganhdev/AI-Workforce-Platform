"""Resident-case navigation excludes personal and hidden management runs."""
from .storage import SessionRecord


def is_leader_case_session(session: SessionRecord) -> bool:
    return (
        session.origin.type == "user"
        and session.config.personal_chat is None
        and not session.state.middle_context.get("management_case_session_id")
        and not session.state.middle_context.get("management_output_session_id")
    )
