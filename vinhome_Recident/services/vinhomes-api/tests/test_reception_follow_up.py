"""What Reception's runtime is told and may do in a conversation, against migrated, seeded PostgreSQL."""



from uuid import UUID, uuid4

from test_resident_contract import sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_domain_database import app, delegate, operation


def say(c, channel, text):
    sent = c.post(f"/resident/chats/{channel}/messages", json={"text": text, "client_message_id": str(uuid4())})
    assert sent.status_code == 201, sent.text
    return sent.json()["id"]


def test_reception_is_told_what_is_missing_and_the_question_is_counted(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "2c" * 32)
    with app(database) as c:
        channel = c.post("/resident/chats", json={"title": "Rò nước"}).json()["id"]
        first = say(c, channel, "Nhà tắm của tôi bị rò nước")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, first)["token"]}
        check = f"/internal/reception/chats/{channel}/intake"
        vague = {"message_id": first, "details": {"symptom": "bị rò nước", "area": "Nhà tắm", "item": "ống âm tường bị vỡ"}}
        assert c.post(check, json=vague).status_code == 401
        told = c.post(check, headers=bearer, json=vague).json()
        assert told["ready"] is False and told["missing"] == "item" and told["rejected"] == ["item"]
        assert told["description"] == "Nhà tắm của tôi bị rò nước"
        asked = c.post(f"/internal/reception/chats/{channel}/replies", headers=bearer, json={
            "text": told["question"], "reply_to_id": first, "clarification": "item"})
        assert asked.status_code == 201, asked.text
        assert sql(database, "select body->>'clarification' as c from messages where id=$1", UUID(asked.json()["id"])) == [{"c": "item"}]

        second = say(c, channel, "ok")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, second)["token"]}
        again = c.post(check, headers=bearer, json={"message_id": second, "details": {"symptom": "bị rò nước"}}).json()
        assert again["ready"] is False
        c.post(f"/internal/reception/chats/{channel}/replies", headers=bearer, json={
            "text": again["question"], "reply_to_id": second, "clarification": "item"})
        third = say(c, channel, "Rò ở chân vòi lavabo")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, third)["token"]}
        done = c.post(check, headers=bearer, json={"message_id": third, "details": {
            "symptom": "bị rò nước", "item": "chân vòi lavabo"}}).json()
        assert done["ready"] and not done["review"]
        assert done["description"] == "Nhà tắm của tôi bị rò nước\nRò ở chân vòi lavabo"
        # Asked twice already: without the detail the report would now go to a person as it is.
        unfinished = c.post(check, headers=bearer, json={"message_id": third, "details": {"symptom": "bị rò nước"}}).json()
        assert unfinished["ready"] and unfinished["review"]

        # The turn of one message does not read what was sent after it.
        seen = c.get(f"/internal/reception/chats/{channel}/context?message_id={second}", headers=bearer).json()
        assert [m["text"] for m in seen["history"] if m["role"] == "resident"] == ["Nhà tắm của tôi bị rò nước", "ok"]
        assert seen["open_request"] is None


def test_a_denied_danger_is_no_emergency_and_a_born_emergency_still_alerts_management(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "4e" * 32)
    with app(database) as c:
        place = operation(c, "get_verified_resident_context")[0]["residences"][0]
        channel = c.post("/resident/chats", json={"title": "Khẩn"}).json()["id"]
        calm = say(c, channel, "Máy nước nóng không nóng từ sáng, đèn báo vẫn sáng, không có mùi khét.")
        bearer = {"Authorization": "Bearer " + delegate(c, channel, calm)["token"]}
        policy = "/internal/reception/policy/evaluate"
        heater = c.post(policy, headers=bearer, json={
            "message_text": "Máy nước nóng không nóng từ sáng, đèn báo vẫn sáng, không có mùi khét.", "assessment": None}).json()
        assert heater["emergency"] is False
        for text in ("Chưa thấy khói nhưng ổ điện rất nóng", "Không phải cháy đâu, chỉ là bóng đèn hỏng"):
            assert c.post(policy, headers=bearer, json={"message_text": text, "assessment": None}).json()["emergency"] is False
        for text in ("Nhà không ai ở mà có mùi gas", "Bếp có mùi khét, không biết từ đâu"):
            assert c.post(policy, headers=bearer, json={"message_text": text, "assessment": None}).json()["emergency"] is True

        fire = say(c, channel, "Bếp nhà tôi đang cháy")
        draft, _ = operation(c, "create_ticket_draft", {
            "channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
            "unit_id": place["unit_id"], "category_id": "33333333-3333-5333-a333-333333333333"})
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(c, "update_ticket_incident", {**target, "fields": {
            "title": "Cháy lớn do nổ bình gas", "description": "Bình gas phát nổ, lửa lan sang phòng khách", "source_message_id": fire}})
        operation(c, "submit_ticket_assessment", {**target, "assessment": {
            "priority": "critical", "severity": "critical", "is_emergency": True, "reason": "Policy xác nhận cần chuyển khẩn cấp."}})
        # No detail is asked of an emergency, and it carries only what the resident wrote.
        handoff, _ = operation(c, "handoff_ticket", {**target, "handoff_reason": "emergency", "plan_required": False})
        assert handoff["accepted"], handoff
        ticket = handoff["ticket"]["id"]
        assert sql(database, "select title,description,is_emergency from tickets where id=$1", UUID(ticket)) == [
            {"title": "Bếp nhà tôi đang cháy", "description": "Bếp nhà tôi đang cháy", "is_emergency": True}]
        version = sql(database, "select version from tickets where id=$1", UUID(ticket))[0]["version"]
        raised, _ = operation(c, "escalate_emergency", {"ticket_id": ticket, "reason": "Bếp nhà tôi đang cháy", "source_message_id": fire})
        assert raised["notificationQueued"] is True
        alerts = sql(database, "select count(*) as n from notification_deliveries where payload->>'type'='ticket.emergency_escalated' "
                               "and payload->>'ticketId'=$1", ticket)[0]["n"]
        assert alerts >= 1
        # Told once, and the version the Supervisor was handed did not move.
        again, _ = operation(c, "escalate_emergency", {"ticket_id": ticket, "reason": "Bếp nhà tôi đang cháy", "source_message_id": fire})
        assert again["notificationQueued"] is False
        assert sql(database, "select count(*) as n from notification_deliveries where payload->>'type'='ticket.emergency_escalated' "
                             "and payload->>'ticketId'=$1", ticket)[0]["n"] == alerts
        assert sql(database, "select version from tickets where id=$1", UUID(ticket))[0]["version"] == version


def test_a_message_whose_turn_was_lost_is_answered_when_the_next_one_arrives(database, monkeypatch):
    monkeypatch.setenv("RECEPTION_DELEGATION_KEY", "5f" * 32)
    from vinhomes_api.v3_reception_runtime import UNAVAILABLE_REPLY, dispatch_turn

    with app(database) as c:
        channel = c.post("/resident/chats", json={"title": "Mất lượt"}).json()["id"]
        lost = say(c, channel, "Điều hòa phòng khách bị chảy nước")
        recent = say(c, channel, "Còn đó không?")
        # The first message is older than any turn can still be running; the second was sent just now.
        sql(database, "update messages set created_at=now()-interval '10 minutes' where id=$1 returning id", UUID(lost))
        now = say(c, channel, "Alo")
        # No runtime answers in this test: the turn of the newest message ends in the fallback reply.
        c.portal.call(dispatch_turn, c.app, "local-v3-resident", channel, {"id": now, "text": "Alo", "fileIds": []})
        replied = sql(database, "select reply_to_id,body->>'text' as text from messages where channel_id=$1 and sender_kind='agent'", channel)
        assert {(str(r["reply_to_id"]), r["text"]) for r in replied} == {(lost, UNAVAILABLE_REPLY), (now, UNAVAILABLE_REPLY)}
        assert recent not in {str(r["reply_to_id"]) for r in replied}
