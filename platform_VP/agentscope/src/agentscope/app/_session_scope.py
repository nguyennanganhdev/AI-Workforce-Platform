"""Resident-case navigation excludes personal and hidden management runs."""
from .storage import SessionRecord


def _leader_navigation_session(session: SessionRecord) -> bool:
    return (
        session.origin.type == "user"
        and session.config.personal_chat is None
        and not session.state.middle_context.get("management_case_session_id")
        and not session.state.middle_context.get("management_output_session_id")
    )


def is_leader_case_session(session: SessionRecord) -> bool:
    """A real partner case has its server-owned workflow binding."""
    return _leader_navigation_session(session) and bool(session.state.middle_context.get("workflow_id"))


def is_leader_test_session(session: SessionRecord) -> bool:
    """Includes legacy manual/empty Leader sessions, without renaming history."""
    return _leader_navigation_session(session) and not session.state.middle_context.get("workflow_id")
