"""Multi-turn golden fixtures for all three lifecycle patterns."""

from .._suites import EvaluationSuite


def lifecycle_suite() -> EvaluationSuite:
    return EvaluationSuite(
        "lifecycle-patterns-v1",
        [
            {
                "case_id": "response-only",
                "pattern": "response_only",
                ("input"): (
                    "Read the available information and answer the"
                    " question."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "closed",
                        "next_action": "none",
                        "operation_pending": False,
                    }
                ],
                "mock_tools_only": True,
                "allowed_tools": [],
            },
            {
                "case_id": "interactive",
                "pattern": "interactive",
                ("input"): (
                    "Plan a trip, keep the approved budget, book "
                    "only after consent."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "awaiting_user",
                        "next_action": "submit_reply",
                        "operation_pending": False,
                    },
                    {
                        "trigger": "selection",
                        "workflow_state": "awaiting_approval",
                        "next_action": "submit_approval",
                        "operation_pending": False,
                    },
                    {
                        "trigger": "approval",
                        "workflow_state": "awaiting_confirmation",
                        "next_action": "confirm_close",
                        "operation_pending": False,
                    },
                    {
                        "trigger": "close",
                        "workflow_state": "closed",
                        "next_action": "none",
                        "operation_pending": False,
                    },
                ],
                "user_replies": [
                    "Select option A",
                    "Approve the quoted amount",
                    "Close",
                ],
                "mock_tools_only": True,
            },
            {
                "case_id": "external-tracking",
                "pattern": "external_tracking",
                ("input"): (
                    "Create one external job and wait for verified"
                    " provider updates."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "waiting_external_event",
                        "next_action": "watch_events",
                        "operation_pending": True,
                    },
                    {
                        "trigger": "none",
                        "workflow_state": "waiting_external_event",
                        "next_action": "watch_events",
                        "operation_pending": True,
                    },
                    {
                        "trigger": "duplicate",
                        "workflow_state": "waiting_external_event",
                        "next_action": "watch_events",
                        "operation_pending": True,
                    },
                    {
                        "trigger": "out_of_order",
                        "workflow_state": "waiting_external_event",
                        "next_action": "watch_events",
                        "operation_pending": True,
                    },
                    {
                        "trigger": "completed",
                        "workflow_state": "awaiting_confirmation",
                        "next_action": "confirm_close",
                        "operation_pending": False,
                    },
                    {
                        "trigger": "close",
                        "workflow_state": "closed",
                        "next_action": "none",
                        "operation_pending": False,
                    },
                ],
                "mock_tools_only": True,
                "max_create_calls": 1,
            },
            {
                "case_id": "creation-unknown",
                "pattern": "external_tracking",
                ("input"): (
                    "Provider creation times out. Reconcile "
                    "instead of retrying create."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "needs_attention",
                        "next_action": "resolve_attention",
                        "operation_pending": True,
                    }
                ],
                "mock_tools_only": True,
                "max_create_calls": 1,
            },
            {
                "case_id": "two-ticket-isolation",
                "pattern": "external_tracking",
                ("input"): (
                    "Interleave two tickets from the same user "
                    "with separate contexts."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "waiting_external_event",
                        "next_action": "watch_events",
                        "operation_pending": True,
                    }
                ],
                "mock_tools_only": True,
                "assert_ticket_isolation": True,
            },
        ],
    )
