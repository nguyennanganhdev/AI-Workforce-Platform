"""The intake rules alone: what is recorded for a report and when it may be handed over."""

from vinhomes_api.reception_intake import assess, found


def said(*texts, files=()):
    return [{"id": f"m{index}", "text": text, "file_ids": list(files) if index == 1 else []}
            for index, text in enumerate(texts, 1)]


def claims(**details):
    return [{"key": key, "value": value} for key, value in details.items()]


def test_a_room_and_a_symptom_are_not_enough_and_the_photo_is_kept():
    result = assess(said("Nhà tắm của tôi bị rò nước", files=["f1"]), claims(symptom="bị rò nước", area="Nhà tắm"),
                    source_message_id="m1")
    assert not result["ready"] and result["missing"] == "item"
    assert result["question"].startswith("Bạn thấy nước rò ở đâu trong nhà tắm")
    assert result["file_ids"] == ["f1"]


def test_invented_details_are_not_recorded_and_do_not_open_the_gate():
    result = assess(said("Nhà tắm của tôi bị rò nước"),
                    claims(symptom="bị rò nước", item="ống âm tường bị vỡ", since="từ sáng"), source_message_id="m1")
    assert not result["ready"]
    assert sorted(result["rejected"]) == ["item", "since"]
    assert result["description"] == "Nhà tắm của tôi bị rò nước"
    assert [fact["key"] for fact in result["facts"]] == ["symptom"]


def test_the_room_or_the_symptom_cannot_stand_in_for_the_thing_affected():
    for item in ("Nhà tắm", "rò nước", "nước"):
        result = assess(said("Nhà tắm của tôi bị rò nước"), claims(symptom="bị rò nước", item=item), source_message_id="m1")
        assert not result["ready"], item


def test_a_complete_first_message_is_not_questioned():
    result = assess(said("Vòi lavabo nhà tắm rò ở chân vòi"), claims(symptom="rò ở chân vòi", area="nhà tắm", item="Vòi lavabo"),
                    source_message_id="m1")
    assert result["ready"] and result["question"] is None
    assert result["title"] == result["description"] == "Vòi lavabo nhà tắm rò ở chân vòi"


def test_the_answer_joins_the_first_message_and_its_photo():
    messages = said("Nhà tắm của tôi bị rò nước", "Rò ở chân vòi lavabo, chảy nhỏ giọt", files=["f1"])
    result = assess(messages, claims(symptom="bị rò nước", area="Nhà tắm", item="chân vòi lavabo"), source_message_id="m2")
    assert result["ready"]
    assert result["description"] == "Nhà tắm của tôi bị rò nước\nRò ở chân vòi lavabo, chảy nhỏ giọt"
    assert result["title"] == "Nhà tắm của tôi bị rò nước" and result["file_ids"] == ["f1"]


def test_not_knowing_is_an_answer_but_ok_is_not():
    messages = said("Nhà tắm của tôi bị rò nước", "Tôi không biết nguồn rò")
    unknown = assess(messages, claims(symptom="bị rò nước", item_unknown="không biết nguồn rò"), source_message_id="m2")
    assert unknown["ready"] and not unknown["review"]
    for key in ("item_unknown", "item"):
        # However the model labels it, an acknowledgement names nothing.
        ok = assess(said("Nhà tắm của tôi bị rò nước", "ok"), claims(symptom="bị rò nước", **{key: "ok"}), source_message_id="m2")
        assert not ok["ready"] and ok["rejected"] == [key] and ok["description"] == "Nhà tắm của tôi bị rò nước"


def test_after_two_questions_the_report_goes_to_a_person_as_it_is():
    messages = said("Nhà tắm của tôi bị rò nước", "ok", "ok")
    result = assess(messages, claims(symptom="bị rò nước"), source_message_id="m3", asked=2)
    assert result["ready"] and result["review"]
    assert result["description"] == "Nhà tắm của tôi bị rò nước"


def test_a_denied_cause_is_not_a_reported_one():
    messages = said("Không phải ống vỡ, nước rò ở chân vòi")
    result = assess(messages, claims(symptom="nước rò", item="ống vỡ"), source_message_id="m1")
    assert "item" in result["rejected"] and not result["ready"]
    right = assess(messages, claims(symptom="nước rò", item="chân vòi"), source_message_id="m1")
    assert right["ready"] and right["description"] == "Không phải ống vỡ, nước rò ở chân vòi"
    assert not found("mùi khét", "Máy nước nóng không nóng, không có mùi khét")
    assert found("mùi khét", "Bếp có mùi khét")


def test_a_correction_replaces_what_it_corrects():
    messages = said("Nhà tắm rò ở vòi sen", "À nhầm, rò ở bồn cầu chứ không phải vòi sen")
    result = assess(messages, claims(symptom="rò", item="bồn cầu"), source_message_id="m2")
    assert result["ready"] and result["description"] == "À nhầm, rò ở bồn cầu chứ không phải vòi sen"


def test_a_fact_must_be_in_the_message_it_cites():
    messages = said("Nhà tắm của tôi bị rò nước", "Rò ở chân vòi lavabo")
    cited = [{"key": "symptom", "value": "bị rò nước", "source_message_id": "m1"},
             {"key": "item", "value": "chân vòi lavabo", "source_message_id": "m1"},
             {"key": "area", "value": "Nhà tắm", "source_message_id": "another-chat"}]
    result = assess(messages, cited, source_message_id="m2")
    assert sorted(result["rejected"]) == ["area", "item"] and not result["ready"]


def test_an_emergency_is_not_held_back_and_gains_no_detail():
    result = assess(said("Bếp nhà tôi đang cháy"), claims(item="bình gas phát nổ"), source_message_id="m1", emergency=True)
    assert result["ready"] and result["description"] == "Bếp nhà tôi đang cháy" and result["facts"] == []


def test_a_service_need_asks_for_no_item_unless_it_reads_like_a_fault():
    need = assess(said("Tôi muốn đăng ký thẻ gửi xe máy"), claims(symptom="đăng ký thẻ gửi xe máy"), source_message_id="m1",
                  kind="service_request")
    assert need["ready"]
    fault = assess(said("Nhà tắm của tôi bị rò nước"), claims(symptom="bị rò nước"), source_message_id="m1", kind="service_request")
    assert not fault["ready"] and fault["missing"] == "item"


def test_nothing_reported_is_nothing_to_hand_over():
    result = assess(said("Báo sự cố"), [], source_message_id="m1")
    assert not result["ready"] and result["missing"] == "symptom" and result["facts"] == []


def test_a_denial_covers_the_list_it_opens_and_nothing_after_it():
    from vinhomes_api.v3_reception_runtime import emergency_kind

    calm = ("Chỉ ổ cắm đó mất điện; không có mùi khét, tia lửa, không nóng, không ai bị giật, không có nước gần đó.",
            "Không có khói, mùi khét hay tia lửa gì cả", "Chưa thấy bốc khói hoặc mùi gas",
            "Máy nước nóng không nóng, đèn vẫn sáng, không có mùi khét.")
    for text in calm:
        assert emergency_kind(text) is None, text
    danger = {"Không có mùi khét, nhưng có tia lửa ở ổ cắm": "fire", "Không biết vì sao bếp có mùi khét, tia lửa": "fire",
              "Không, đang bốc khói": "fire", "Không có nước nhưng có mùi gas": "gas",
              "Ổ cắm không có điện và có mùi khét": "fire", "Nhà không ai ở mà có mùi gas": "gas",
              "Không phải chập điện, bếp đang cháy": "fire"}
    for text, kind in danger.items():
        assert emergency_kind(text) == kind, text
