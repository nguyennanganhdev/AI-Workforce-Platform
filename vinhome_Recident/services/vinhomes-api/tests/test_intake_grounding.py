"""Explicit resident details must not depend on the model repeating every field."""
from vinhomes_api.reception_intake import assess


def message(identifier, text, **extra):
    return {"id": identifier, "text": text, "file_ids": [], **extra}


def test_a_complete_multi_item_report_is_not_asked_to_name_its_devices_again():
    text = "Ở bếp vòi lavabo bị rò nước từ sáng; đèn LED trên trần nhấp nháy liên tục. Kiểm tra cả hai giúp tôi."
    result = assess([message("first", text, file_ids=["photo-a", "photo-b"])],
                    [{"key": "symptom", "value": "bị rò nước"}, {"key": "area", "value": "bếp"}], source_message_id="first")
    assert result["ready"] and result["question"] is None
    assert result["description"] == text
    assert result["file_ids"] == ["photo-a", "photo-b"]
    item = next(f for f in result["facts"] if f["key"] == "item")
    assert item["value"] in text and item["source_message_id"] == "first"


def test_a_short_answer_completes_the_existing_report_even_if_the_model_omits_item():
    first = message("first", "Nhà tắm bị rò nước", intake_facts=[{"key": "symptom", "value": "bị rò nước", "source_message_id": "first"}])
    last = message("last", "Chân vòi lavabo", file_ids=["photo"])
    result = assess([first, last], [{"key": "symptom", "value": "bị rò nước"}], source_message_id="last", asked=1)
    assert result["ready"] and result["missing"] is None
    assert "Chân vòi lavabo" in result["description"] and result["file_ids"] == ["photo"]


def test_a_device_explicitly_reported_as_not_broken_is_not_the_affected_item():
    text = "Đèn không hỏng, phòng tắm bị rò nước, chưa xác định chỗ nào."
    result = assess([message("first", text)], [{"key": "symptom", "value": "bị rò nước"}], source_message_id="first")
    assert not result["ready"] and result["missing"] == "item"


def test_a_stale_model_claim_does_not_erase_the_residents_device_correction():
    first = message("first", "Vòi bị rò nước", intake_facts=[{"key": "symptom", "value": "bị rò nước", "source_message_id": "first"}, {"key": "item", "value": "Vòi", "source_message_id": "first"}])
    last = message("last", "Không phải vòi, nước từ trần nhà tắm")
    result = assess([first, last], [{"key": "item", "value": "Vòi", "source_message_id": "first"}], source_message_id="last", asked=1)
    assert result["ready"]
    item = next(f for f in result["facts"] if f["key"] == "item")
    assert "trần" in item["value"] and item["source_message_id"] == "last"


def test_a_hypothetical_device_or_a_question_does_not_become_a_reported_item():
    for follow_up in ("Có phải vòi bị rò không?", "Nếu vòi bị rò thì sao?"):
        first = message("first", "Nhà tắm bị rò nước", intake_facts=[{"key": "symptom", "value": "bị rò nước", "source_message_id": "first"}])
        result = assess([first, message("last", follow_up)], [], source_message_id="last", asked=1)
        assert not result["ready"] and result["missing"] == "item"


def test_an_unrelated_old_device_does_not_replace_the_current_emergency_report():
    messages = [message("first", "Máy nước nóng không nóng"), message("last", "Bếp nhà tôi đang cháy")]
    result = assess(messages, [], source_message_id="last", emergency=True)
    assert result["ready"] and result["description"] == "Bếp nhà tôi đang cháy"
    pending = assess(messages, [], source_message_id="last")
    assert pending["description"] == "Bếp nhà tôi đang cháy"
