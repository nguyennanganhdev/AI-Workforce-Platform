"""Known customer inputs and stable keys for clarification requests.

Models identify missing fields; the runtime checks fields already supplied.
This does not infer identity or turn customer prose into verified business state.
"""

import hashlib
import re

_QUESTIONS = {
    "location": r"ở đâu|vị trí (?:ở đâu|xảy ra|sự cố)|địa điểm (?:nào|xảy ra)|where (?:are|is)|what (?:is the )?location",
    "unit": r"căn hộ nào|số căn|which unit|unit number",
    "building": r"tòa nào|tòa nhà nào|which building",
    "date": r"ngày nào|ngày mấy|which date|what date",
    "time": r"mấy giờ|giờ nào|what time",
}
_INPUTS = {
    "location": r"\b(?:hầm|tầng|phòng|khu vực)\s+[\w.-]+|\b(?:location|vị trí|địa điểm)\s*:\s*[^\n]+",
    "unit": r"\b(?:căn hộ|căn|unit)\s*:?\s*[A-Z0-9][A-Z0-9.-]*\d[A-Z0-9.-]*",
    "building": r"\b(?:tòa|building)\s*:?\s*[A-Z0-9][A-Z0-9.-]*",
    "date": r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{4})?)\b",
    "time": r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b|\b\d{1,2}\s*giờ\b",
}


def question_fields(content: str) -> tuple[str, ...]:
    fields = tuple(
        key
        for key, pattern in _QUESTIONS.items()
        if re.search(pattern, content, re.IGNORECASE)
    )
    # A known floor does not answer a new question about distance or a column.
    if re.search(
        r"bao xa|khoảng cách|cột nào|số cột|bên nào|phía nào", content, re.IGNORECASE
    ):
        fields = tuple(field for field in fields if field != "location")
    return fields


def question_key(content: str, fields: tuple[str, ...] = ()) -> str:
    fields = fields or question_fields(content)
    if fields:
        return "fields:" + ",".join(sorted(set(fields)))
    normalized = " ".join(content.casefold().split())
    return "auto:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def known_inputs(events) -> dict[str, dict]:
    return known_text_inputs(
        (event.id, event.content)
        for event in events
        if event.kind == "customer_message" and not event.stale
    )


def known_text_inputs(texts) -> dict[str, dict]:
    known = {}
    for source_id, content in texts:
        for key, pattern in _INPUTS.items():
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                match = matches[-1]
                # Do not claim an explicitly unknown location as supplied.
                prefix = content[max(0, match.start() - 20) : match.start()]
                if re.search(
                    r"(?:không biết|chưa rõ|unknown)\s*$", prefix, re.IGNORECASE
                ):
                    continue
                known[key] = {"value": match.group(0), "source_event_id": source_id}
    return known
