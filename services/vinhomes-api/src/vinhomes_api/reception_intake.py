"""What Reception may record and hand over for a resident's report.

The model proposes details; this module decides from the stored conversation. A request holds
the resident's own words, a detail counts only when it is found in the resident message it
cites, and an ordinary incident is handed over once the affected thing or exact spot is known
or the resident said they cannot tell. An emergency is never held back for a question.
"""

import re
import unicodedata
from typing import Any

from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
# How many times a resident is asked for the same missing detail before a person takes over.
MAX_QUESTIONS = 2
# "không có mùi khét", "chưa thấy khói": the words right before a phrase that deny it.
NEGATOR = r"(?:không|chưa|chẳng|chả|ko|hổng|đâu)\s+"
NEGATION = re.compile(NEGATOR + r"(?:(?:hề|có|thấy|ngửi thấy|nghe|phải là|phải|bị|còn)\s+){0,2}$")
# Saying something is absent covers the whole list that follows ("không có mùi khét, tia lửa hay khói")
# and stops at anything that is not another short item of it ("không có mùi khét, nhưng có tia lửa").
# A correction does not open such a list: "không phải ống vỡ, nước rò ở chân vòi" reports the leak.
ABSENT = re.compile(
    NEGATOR + r"(?:hề\s+)?(?:có|thấy|ngửi thấy|nghe|bị|còn|ai bị)\s+"
    r"(?:(?!(?:nhưng|mà|song|tuy)\b)[^\s,.;:!?]+(?:\s+(?!(?:hay|hoặc|và|nhưng|mà)\b)[^\s,.;:!?]+){0,4}\s*(?:,|\s(?:hay|hoặc|và))\s+)+$")
# A room or the home itself, and filler around it: where something is, not what is affected.
AREAS = ("nhà vệ sinh", "nhà tắm", "phòng tắm", "phòng bếp", "nhà bếp", "phòng ngủ", "phòng khách", "ban công", "lô gia",
         "logia", "hành lang", "căn hộ", "căn nhà", "toilet", "wc", "bếp", "nhà", "phòng", "trong", "của", "tôi", "mình",
         "em", "ở", "tại", "chỗ", "khu")
UNKNOWN = ("không biết", "chưa biết", "không rõ", "chưa rõ", "không xác định", "chưa xác định", "không chắc", "chưa chắc",
           "không tìm ra", "chưa tìm ra", "ko biết", "ko rõ", "khong biet", "khong ro", "chua biet", "chua ro")
LEAK = ("rò", "rỉ", "thấm", "dột", "nhỏ giọt", "chảy nước", "nhỏ nước")
# A report worded like a fault is an incident, whatever kind the model gave it.
FAULT = LEAK + ("hỏng", "hư", "vỡ", "nứt", "tắc", "nghẹt", "kẹt", "mất điện", "mất nước", "không hoạt động", "không lên",
                "không chạy", "không mát", "không nóng", "chập", "bị ")
# What went wrong rather than what it happened to.
GENERIC = ("nước", "điện", "sự cố", "vấn đề", "có", "đang")
# An acknowledgement says nothing about the incident: "ok" answers no question.
FILLER = ("ok", "oke", "okay", "okie", "ừ", "ừm", "uh", "vâng", "dạ", "được", "rồi", "nhé", "ạ", "yes", "no", "không", "thế",
          "vậy", "đấy", "đó", "bạn", "cảm ơn", "xin chào", "chào", "hi", "hello")


def fold(value: str) -> str:
    """Text as it is compared: one case, one Unicode form, single spaces."""
    return " ".join(unicodedata.normalize("NFC", value).lower().split())


def negated(folded: str, start: int) -> bool:
    before = folded[:start]
    return NEGATION.search(before) is not None or ABSENT.search(before) is not None


def found(quote: str, message: str) -> bool:
    """The resident wrote this, and did not deny it."""
    needle, haystack = fold(quote).strip(" .,;:!?\"'“”"), fold(message)
    start = haystack.find(needle) if needle else -1
    return start >= 0 and not negated(haystack, start)


def _beyond(value: str, phrases: tuple[str, ...]) -> bool:
    """The value says something once these phrases are taken out of it."""
    rest = fold(value)
    for phrase in sorted(phrases, key=len, reverse=True):
        rest = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", " ", rest)
    return bool(re.sub(r"[\W_]+", "", rest))


def _specific(value: str) -> bool:
    """Names a thing or a spot: "trần nhà tắm" and "ổ điện" do, "nhà tắm", "rò nước" and "ok" do not."""
    return _beyond(value, AREAS + GENERIC + FILLER + tuple(word.strip() for word in FAULT))


def _question(missing: str, symptom: str, area: str) -> str:
    if missing == "symptom":
        return "Bạn đang gặp sự cố gì, và ở đâu trong nhà? Bạn mô tả giúp mình nhé."
    place = f" trong {area}" if area else ""
    if any(word in symptom for word in LEAK):
        return (f"Bạn thấy nước rò ở đâu{place}: vòi, ống, bồn cầu, tường hay trần? "
                "Nếu chưa xác định được, bạn cứ nói chưa rõ nhé.")
    return f"Sự cố ở thiết bị hay vị trí cụ thể nào{place}? Nếu chưa xác định được, bạn cứ nói chưa rõ nhé."


def assess(messages: list[dict[str, Any]], claims: list[dict[str, Any]], *, source_message_id: str | None,
           kind: str = "incident", emergency: bool = False, asked: int = 0) -> dict[str, Any]:
    """Decide what is recorded and whether it may be handed over.

    `messages` are the resident's messages of the conversation, oldest first, as
    {"id", "text", "file_ids"}. A claim is {"key", "value"} with an optional "source_message_id":
    without one the latest message holding the words is cited, so a correction wins over what it
    corrects.
    """
    by_id = {str(message["id"]): message for message in messages}
    facts: list[dict[str, Any]] = []
    rejected: list[str] = []
    for claim in claims:
        key, value, cited = claim.get("key"), claim.get("value"), claim.get("source_message_id")
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            rejected.append(str(key))
            continue
        if not _beyond(value, FILLER):
            rejected.append(key)
            continue
        candidates = [by_id[str(cited)]] if cited is not None and str(cited) in by_id else [] if cited is not None else messages[::-1]
        source = next((message for message in candidates if found(value, message["text"])), None)
        if source is None:
            rejected.append(key)
            continue
        facts.append({"key": key, "value": value.strip(), "source": "customer_report", "source_message_id": str(source["id"])})

    def held(key: str) -> str:
        return next((fold(fact["value"]) for fact in facts if fact["key"] == key), "")

    symptom, area = held("symptom"), held("area")
    for fact in list(facts):
        value = fold(fact["value"])
        vague = fact["key"] == "item" and not _specific(value)
        unsure = fact["key"] == "item_unknown" and not any(word in value for word in UNKNOWN)
        if vague or unsure:
            facts.remove(fact)
            rejected.append(fact["key"])
    cited_ids = {fact["source_message_id"] for fact in facts} or {str(source_message_id)}
    cited = [message for message in messages if str(message["id"]) in cited_ids and message["text"].strip()]
    # The resident's words, never a rewording: the messages the details came from, or the message itself.
    description = "\n".join(message["text"].strip() for message in cited)[:10000]
    title = cited[0]["text"].strip().splitlines()[0][:120].strip() if cited else ""
    fault = kind != "service_request" or any(word in fold(description) for word in FAULT)
    missing = None
    if not emergency:
        if not symptom:
            missing = "symptom"
        elif fault and not held("item") and not held("item_unknown"):
            missing = "item"
    # Asked enough: the report goes to a person as it is, marked as incomplete.
    review = missing == "item" and asked >= MAX_QUESTIONS
    ready = bool(description) and (missing is None or review)
    return {
        "ready": ready, "review": review, "missing": None if ready else missing or "report",
        "question": None if ready else _question(missing or "symptom", symptom, area),
        "title": title, "description": description, "facts": facts, "rejected": rejected,
        "file_ids": list(dict.fromkeys(str(file_id) for message in messages for file_id in message["file_ids"])),
    }


async def conversation(db, channel_id: str, actor: str) -> tuple[list[dict[str, Any]], int]:
    """The resident's own messages of this conversation, and how often Reception already asked for a detail."""
    rows = await db.execute(text(f"""
        select id,sender_kind,sender_user_id,coalesce(body->>'text','') as text,
               coalesce(body->'fileIds','[]'::jsonb) as file_ids,body->>'clarification' as clarification
        from messages
        where channel_id=:channel and tenant_id={TENANT} and visibility in ('room','customer')
          and coalesce(body->>'type','')<>'ticket_draft'
        order by seq
    """), {"channel": channel_id})
    messages, asked = [], 0
    for row in rows.mappings():
        if row["sender_kind"] == "user" and row["sender_user_id"] == actor:
            messages.append({"id": str(row["id"]), "text": row["text"], "file_ids": list(row["file_ids"] or [])})
        elif row["clarification"] == "item":
            asked += 1
    return messages, asked
