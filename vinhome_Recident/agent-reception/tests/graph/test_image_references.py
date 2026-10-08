import json
from copy import deepcopy

from workflow_fixture import (
    REQUEST,
    async_test,
    harness,
    resident_resume,
    turn,
    waiting,
)


def incident_turn(message_ids):
    return json.dumps(
        {
            "intent": "information",
            "title": "Rò nước tại bếp",
            "description": "Vòi nước tại bếp bị rò.",
            "facts": [
                {
                    "key": "location",
                    "value": "bếp",
                    "source": "customer_report",
                    "source_message_id": message_ids[0],
                }
            ],
            "answers": {},
        }
    )


@async_test
async def test_image_survives_profile_clarification_and_is_linked_once():
    first_profile = True

    def override(call, value):
        nonlocal first_profile
        if call["operation"] == "get_verified_resident_context" and first_profile:
            first_profile = False
            return {
                "kind": "success",
                "value": {"kind": "selection_required", "questions": ["Căn hộ nào?"]},
            }

    h = harness(model=[incident_turn(["message-1", "message-2"])], override=override)
    first = waiting(await h.graph.run(REQUEST))
    second_message = {
        "id": "message-2",
        "text": "Căn 1205",
        "fileIds": ["file-synthetic-2", "file-synthetic-1"],
    }
    result = waiting(await h.graph.resume(resident_resume(first, second_message)))
    update = next(c for c in h.calls if c["operation"] == "update_ticket_incident")
    assert update["input"]["incident"]["file_ids"] == [
        "file-synthetic-1",
        "file-synthetic-2",
    ]
    assert update["input"]["incident"]["description"] == "Vòi nước tại bếp bị rò."
    assert result["state"]["pending_file_refs"] == []
    assert result["state"]["linked_file_ids"] == [
        "file-synthetic-1",
        "file-synthetic-2",
    ]


@async_test
async def test_the_photo_of_an_image_only_message_is_carried_to_the_backend():
    # Only the graph's side: this fixture's backend accepts whatever it is given. The real backend
    # records no words for a message without any and asks what happened before a request is handed
    # over (services/vinhomes-api tests/test_reception_intake.py, tests/graph/test_intake_question.py).
    request = deepcopy(REQUEST)
    request["message"] = {
        "id": "message-image-only",
        "text": "",
        "fileIds": ["file-image-only"],
    }
    h = harness(model=[incident_turn(["message-image-only"])])
    result = waiting(await h.graph.run(request))
    handoff = next(c for c in h.calls if c["operation"] == "handoff_ticket")
    assert handoff["input"]["message"]["file_ids"] == ["file-image-only"]
    assert result["state"]["linked_file_ids"] == ["file-image-only"]


@async_test
async def test_image_after_handoff_is_appended_to_same_ticket():
    h = harness(model=[incident_turn(["message-1"]), turn("information")])
    first = waiting(await h.graph.run(REQUEST))
    follow_up = {
        "id": "message-2",
        "text": "Tôi bổ sung ảnh mới.",
        "fileIds": ["file-after-handoff"],
    }
    result = waiting(await h.graph.resume(resident_resume(first, follow_up)))
    append = next(c for c in h.calls if c["operation"] == "append_ticket_information")
    assert append["input"]["file_ids"] == ["file-after-handoff"]
    assert result["state"]["active_ticket_id"] == first["state"]["active_ticket_id"]
    assert "file-after-handoff" in result["state"]["linked_file_ids"]
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) == 1


@async_test
async def test_new_incident_image_is_not_attached_to_existing_ticket():
    h = harness(model=[incident_turn(["message-1"]), turn("new_incident")])
    first = waiting(await h.graph.run(REQUEST))
    result = await h.graph.resume(
        resident_resume(
            first,
            {
                "id": "message-2",
                "text": "Ổ điện phòng ngủ cũng hỏng.",
                "fileIds": ["unrelated-image"],
            },
        )
    )
    assert result["status"] == "completed"
    assert result["state"]["pending_file_refs"] == []
    assert "unrelated-image" not in result["state"]["linked_file_ids"]
    assert not any(
        c["operation"] == "append_ticket_information"
        and "unrelated-image" in c["input"].get("file_ids", [])
        for c in h.calls
    )
