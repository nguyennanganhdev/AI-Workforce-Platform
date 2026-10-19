"""The room view carries the context/compaction counters the backend keeps."""

from agentscope.app._router._workforce_console import RoomView
from agentscope.app.storage._model._team_context import SharedContextMetrics


def test_summary_exposes_compaction_and_prompt_counters_without_usage_payloads():
    metrics = SharedContextMetrics(compactions=2, compaction_failures=1, last_summary_input_tokens=900,
                                   last_summary_output_tokens=120, last_tool_schema_tokens=3000,
                                   last_model_context_size=400000, last_token_counter="tiktoken")
    summary = metrics.summary()
    assert summary["compactions"] == 2 and summary["compaction_failures"] == 1
    assert (summary["last_summary_input_tokens"], summary["last_summary_output_tokens"]) == (900, 120)
    assert summary["last_tool_schema_tokens"] == 3000 and summary["last_model_context_size"] == 400000
    assert summary["token_counter"] == "tiktoken"
    assert "provider_usage" not in summary and "provider_usage_by_model" not in summary


def test_room_view_serialises_the_summary():
    view = RoomView(participants=[], timeline=[], context=SharedContextMetrics(compactions=3).summary())
    assert view.model_dump()["context"]["compactions"] == 3
    assert RoomView(participants=[], timeline=[]).context == {}
