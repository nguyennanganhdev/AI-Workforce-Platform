import asyncio
from copy import deepcopy

from src.persistence import open_sqlite_checkpointer
from workflow_fixture import REQUEST, harness, turn, waiting


def run(coro):
    return asyncio.run(coro)


def test_sqlite_checkpoint_survives_runtime_restart(tmp_path):
    path = tmp_path / "reception-checkpoints.sqlite3"

    async def scenario():
        async with open_sqlite_checkpointer(path) as first_saver:
            first = harness(checkpointer=first_saver)
            waiting(await first.graph.run(REQUEST))
            expected = await first.graph.read(REQUEST["context"])
        async with open_sqlite_checkpointer(path) as second_saver:
            second = harness(checkpointer=second_saver)
            restored = await second.graph.read(REQUEST["context"])
        return expected, restored

    expected, restored = run(scenario())
    assert restored["active_ticket_id"] == expected["active_ticket_id"]
    assert restored["linked_file_ids"] == ["file-synthetic-1"]
    assert restored["phase"] == "waiting_supervisor"


def test_backend_snapshot_restores_ticket_and_pending_image_without_checkpoint():
    async def resolve_session(context, signal):
        return {
            "channel_id": "channel-synthetic",
            "reception_session_id": "session-synthetic",
            "ticket": {
                "ticket_id": "ticket-restored",
                "ticket_code": "TK-RESTORED",
                "ticket_generation": 0,
                "ticket_version": "7",
                "aggregate_version": 7,
                "created_at": "2026-09-30T00:00:00Z",
            },
            "file_references": [
                {
                    "file_id": "file-restored",
                    "source_message_id": "old-message",
                    "linked_to_ticket": False,
                }
            ],
            "handoff": {
                "route": {
                    "destination_id": "destination",
                    "workspace_id": "workspace",
                    "team_id": "team",
                    "coordination_binding_id": "coordination",
                    "building_id": "building",
                    "domain_id": "domain",
                    "ticket_version": "7",
                    "route_revision": 2,
                },
                "ack": {
                    "persisted": True,
                    "enqueued": True,
                    "correlation_id": "correlation-restored",
                    "operation_id": "handoff-restored",
                },
            },
        }

    def override(call, value):
        if call["operation"] == "append_ticket_information":
            return {
                "kind": "success",
                "value": {
                    "ticket": {
                        "ticket_id": "ticket-restored",
                        "ticket_code": "TK-RESTORED",
                        "ticket_generation": 0,
                        "ticket_version": "8",
                        "aggregate_version": 8,
                        "created_at": "2026-09-30T00:00:00Z",
                    },
                    "delivered": True,
                    "scope_changed": False,
                    "linked_file_ids": call["input"]["file_ids"],
                },
            }

    h = harness(
        resolve_session=resolve_session,
        model=[turn("information")],
        override=override,
    )
    request = deepcopy(REQUEST)
    request["message"] = {"id": "new-message", "text": "Tôi bổ sung nội dung."}
    result = waiting(run(h.graph.run(request)))
    append = next(c for c in h.calls if c["operation"] == "append_ticket_information")
    assert append["input"]["file_ids"] == ["file-restored"]
    assert result["state"]["active_ticket_id"] == "ticket-restored"
    assert "file-restored" in result["state"]["linked_file_ids"]
