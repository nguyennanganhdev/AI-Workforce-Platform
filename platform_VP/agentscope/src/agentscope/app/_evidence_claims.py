"""Deterministic claim anchors for Workforce evidence checks.

The model remains responsible for natural prose. The runtime checks the parts
that are most dangerous to invent: concrete names, dates, times and numbers.
The checks are domain-neutral and keep original evidence in durable storage.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import combinations

_WORD_RE = re.compile(r"[^\W\d_]+(?:[.'’-][^\W\d_]+)*|&", re.UNICODE)
_QUOTED_RE = re.compile(r'["“”\'‘’]([^"“”\'‘’]{3,100})["“”\'‘’]')
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):[0-5]\d(?!\d)")
_DATE_RE = re.compile(
    r"(?<![\d.])(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?!\d)",
)
_SCALED_RE = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(triệu|tr|million|nghìn|ngàn|k|thousand)\b",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(
    r"(?<![\w/:])(\d{1,3}(?:[\s.,]\d{3})+|\d+(?:[.,]\d+)?)"
    r"\s*(?:đồng|đ|₫|vnd|usd|eur)(?!\w)",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(
    r"(?<![\d/:])(\d+(?:[.,]\d+)?)\s*(?:người|khách|phòng|đêm|ngày|chỗ|ghế|giường|sao|review|reviews|people|guests|rooms|nights|days|seats|beds|stars)\b",
    re.IGNORECASE,
)
_LARGE_NUMBER_RE = re.compile(
    r"(?<![\w/:])(?<!\d[.,])\d{2,}(?![\w/:])(?![.,]\d)",
)
_ITINERARY_CODE_RE = re.compile(
    r"(?<!\w)\d+\s*[Nn]\s*\d+\s*[\u0110\u0111Dd](?!\w)",
)
# Evidence citations ("E1, E2, E3") name events; they are not amounts.
_EVIDENCE_CODE_RE = re.compile(r"(?<!\w)E\d+(?!\w)")
# Identifiers (a ticket "cleaning--3cb7ea0", a unit "S1.01-1201", a job
# "WO-1001"): letters and digits joined by - . _ . Their digits are not
# amounts; the identifier as a whole must be in the evidence.
_IDENTIFIER_RE = re.compile(r"(?<![\w.-])[A-Za-z0-9]+(?:(?:--?|[._])[A-Za-z0-9]+)+(?![\w-])")

_CONNECTORS = {
    "&",
    "and",
    "at",
    "bến",
    "cà",
    "chợ",
    "de",
    "express",
    "hoa",
    "hotel",
    "hồ",
    "lửa",
    "miền",
    "of",
    "park",
    "phê",
    "phố",
    "quận",
    "sạn",
    "the",
    "và",
    "view",
    "vườn",
    "xe",
}
_ENTITY_PREFIXES = {
    "bến",
    "café",
    "cafe",
    "chợ",
    "hồ",
    "nhà",
    "phố",
    "vườn",
}
_LEADING_GENERIC = {
    "ăn",
    "bữa",
    "chọn",
    "choose",
    "đến",
    "ghé",
    "khách",
    "lựa",
    "loại",
    "limousine",
    "ngày",
    "phòng",
    "sạn",
    "select",
    "tại",
    "tối",
    "vé",
    "xe",
}
_TRAILING_GENERIC = {
    "limousine",
    "gi\u01b0\u1eddng",
}

# Title-cased headings and action phrases are not named entities. Without this
# filter, headings such as "Đánh Giá Ngân Sách" become fake business names.
_NON_ENTITY_PREFIXES = (
    # Internal agent role labels (including abbreviated Vietnamese roles)
    # are routing language, not names of staff dispatched in the real world.
    "agent",
    "các phương án",
    "chi phí dự kiến",
    "đánh giá ngân sách",
    "đã xác minh",
    "đi xe",
    "kết quả xác minh",
    "lịch trình dự kiến",
    "phương án tiết kiệm",
    "phương án tối ưu",
    "tổng chi phí",
    "verified result",
    "budget assessment",
    "estimated cost",
    "source event",
    "proposed action plan",
)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w&]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _is_title_word(word: str) -> bool:
    letters = [char for char in word if char.isalpha()]
    return bool(letters) and (letters[0].isupper() or all(c.isupper() for c in letters))


def _is_generic_name(anchor: str) -> bool:
    return any(
        anchor == prefix or anchor.startswith(prefix + " ")
        for prefix in _NON_ENTITY_PREFIXES
    )


def _proper_name_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    text = _ITINERARY_CODE_RE.sub(" ", text)
    text = _IDENTIFIER_RE.sub(lambda match: " " if _identifier(match.group(0)) else match.group(0), text)
    for quoted in _QUOTED_RE.findall(text):
        normalized = _normalize(quoted)
        # A quoted name is a few words; a quoted sentence (a proposed reply
        # to the user) is not a name, its own words are checked below.
        words = _WORD_RE.findall(quoted)
        looks_named = sum(_is_title_word(word) for word in words) >= 2 or (
            bool(words) and _normalize(words[0]) in _ENTITY_PREFIXES
        )
        if looks_named and len(normalized.split()) <= 6:
            anchors.add(normalized)

    # A number ends a name: "Hotel A 1200000 VND" must not become the name
    # "hotel a vnd" (word extraction drops digits and would join both sides).
    for segment in re.split(r"[\n,.!?;:()\[\]{}*]+|\s[-–—]\s|\d+", text):
        words = _WORD_RE.findall(segment)
        for start, word in enumerate(words):
            first = _normalize(word)
            if not (_is_title_word(word) or first in _ENTITY_PREFIXES):
                continue
            if start:
                previous = words[start - 1]
                if _is_title_word(previous) or _normalize(previous) in _CONNECTORS:
                    continue
            selected = [word]
            title_count = int(_is_title_word(word))
            for candidate in words[start + 1 : start + 7]:
                normalized = _normalize(candidate)
                if _is_title_word(candidate):
                    selected.append(candidate)
                    title_count += 1
                elif normalized in _CONNECTORS:
                    selected.append(candidate)
                else:
                    break
            if title_count < 2:
                continue
            while selected and _normalize(selected[0]) in _LEADING_GENERIC:
                selected.pop(0)
            while selected and _normalize(selected[-1]) in _CONNECTORS and not _is_title_word(selected[-1]):
                selected.pop()
            while selected and _normalize(selected[-1]) in _TRAILING_GENERIC:
                selected.pop()
            if sum(_is_title_word(part) for part in selected) >= 2:
                anchor = _normalize(" ".join(selected))
                if not _is_generic_name(anchor):
                    anchors.add(anchor)
    return anchors


def _decimal_number(value: str) -> Decimal | None:
    value = value.strip().replace(" ", "")
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif value.count(".") > 1 or value.count(",") > 1:
        value = value.replace(".", "").replace(",", "")
    elif "." in value or "," in value:
        separator = "." if "." in value else ","
        tail = value.rsplit(separator, 1)[1]
        if len(tail) == 3:
            value = value.replace(separator, "")
        else:
            value = value.replace(separator, ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _number_key(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "number:" + normalized


def _json_number_anchors(text: str) -> set[str]:
    """Read numeric scalars from nested runtime JSON envelopes."""

    anchors: set[str] = set()

    def visit(value: object, depth: int = 0) -> None:
        if depth > 10 or isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            anchors.add(_number_key(Decimal(str(value))))
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child, depth + 1)
            return
        if isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    visit(json.loads(stripped), depth + 1)
                except (TypeError, ValueError):
                    pass

    try:
        visit(json.loads(text))
    except (TypeError, ValueError):
        pass
    return anchors


def _identifier(token: str) -> bool:
    return any(char.isalpha() for char in token) and any(char.isdigit() for char in token)


def _numeric_anchors(text: str) -> set[str]:
    text = _EVIDENCE_CODE_RE.sub(" ", _ITINERARY_CODE_RE.sub(" ", text))
    identifiers = {token for token in _IDENTIFIER_RE.findall(text) if _identifier(token)}
    text = _IDENTIFIER_RE.sub(lambda match: " " if _identifier(match.group(0)) else match.group(0), text)
    anchors = {f"id:{token.casefold()}" for token in identifiers}
    anchors |= {
        f"time:{int(match.group(1))}:{match.group(0).rsplit(':', 1)[1]}"
        for match in _TIME_RE.finditer(text)
    }
    anchors.update(f"date:{match.group(0)}" for match in _DATE_RE.finditer(text))
    anchors.update(_json_number_anchors(text))
    for raw, scale in _SCALED_RE.findall(text):
        value = _decimal_number(raw)
        if value is None:
            continue
        multiplier = (
            Decimal(1_000_000)
            if scale.casefold() in {"triệu", "tr", "million"}
            else Decimal(1_000)
        )
        anchors.add(_number_key(value * multiplier))
    for pattern in (_CURRENCY_RE, _COUNT_RE):
        for match in pattern.finditer(text):
            value = _decimal_number(match.group(1))
            if value is not None:
                anchors.add(_number_key(value))
    for raw in _LARGE_NUMBER_RE.findall(text):
        value = _decimal_number(raw)
        if value is not None:
            anchors.add(_number_key(value))
    return anchors


def _date_parts(anchor: str) -> tuple[int | None, int, int] | None:
    """Parse supported date anchors without assuming one display format."""

    if not anchor.startswith("date:"):
        return None
    raw = anchor.removeprefix("date:")
    parts = re.split(r"[-/]", raw)
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return None
    if len(values) == 2:
        day, month = values
        return None, month, day
    if len(values) != 3:
        return None
    if len(parts[0]) == 4:
        year, month, day = values
    else:
        day, month, year = values
        if year < 100:
            year += 2000
    return year, month, day


def _date_is_supported(anchor: str, candidates: set[str]) -> bool:
    """Match ``DD/MM`` against the same evidenced full or ISO date."""

    claim = _date_parts(anchor)
    if claim is None:
        return False
    claim_year, claim_month, claim_day = claim
    for candidate in candidates:
        evidence = _date_parts(candidate)
        if evidence is None:
            continue
        year, month, day = evidence
        if (month, day) != (claim_month, claim_day):
            continue
        if claim_year is None or claim_year == year:
            return True
    return False


@dataclass(frozen=True)
class EvidenceSource:
    """One trusted source; facts from separate records are never combined."""

    content: str
    source_id: str
    authority: str = "tool"


@dataclass(frozen=True)
class ClaimValidation:
    unsupported: tuple[str, ...]
    supported_text: str
    rejected_texts: tuple[str, ...]
    has_concrete_claims: bool = False


@dataclass(frozen=True)
class _Fact:
    entity: str
    field: str
    value: str
    currency: str = ""
    unit: str = ""
    source_id: str = ""


_AMOUNT = r"(?:\d{1,3}(?:[ .,]\d{3})+|\d+(?:[.,]\d+)?)"
_CURRENCIES = r"USD|EUR|VND|GBP|JPY|CNY|AUD|CAD|SGD|KRW|THB"
_MONEY_RE = re.compile(
    rf"(?<![\w/:])(?:(?P<prefix>{_CURRENCIES}|\$|€|₫)\s*)?"
    rf"(?P<amount>{_AMOUNT})\s*"
    r"(?P<scale>triệu|million|nghìn|ngàn|thousand|tr|k)?\s*"
    rf"(?P<currency>đồng|{_CURRENCIES}|đ|₫|\$|€)?(?!\w)",
    re.IGNORECASE,
)
_UNIT_RE = re.compile(
    r"\s*(?:/|\bper\b|\bmỗi\b|\btrên\b)\s*"
    r"(?:(?P<count>\d+)\s*)?"
    r"(?P<unit>đêm|night|người|person|guest|khách|phòng|room|ngày|day|tuần|week|tháng|month|giờ|hour|năm|year|[^\W\d_]+)s?\b",
    re.IGNORECASE,
)
_UNIT_NAMES = {
    "đêm": "night",
    "người": "person",
    "guest": "person",
    "khách": "person",
    "phòng": "room",
    "ngày": "day",
    "tuần": "week",
    "tháng": "month",
    "giờ": "hour",
    "năm": "year",
}
_FIELD_RE = re.compile(
    r"\b(?P<price>price|costs?|giá|phí|ngân sách|budget|reserve|dự phòng|tổng|total)\b"
    r"|\b(?P<rating>rating|rated|đánh giá|sao|stars?)\b"
    r"|\b(?P<departure>khởi hành|có chuyến|depart(?:ure|s)?|travel[ _]date)\b"
    r"|\b(?P<checkin>check[ _-]?in|nhận phòng)\b"
    r"|\b(?P<checkout>check[ _-]?out|trả phòng)\b"
    r"|\b(?P<arrival>arrival|arrives?|đến lúc|eta)\b",
    re.IGNORECASE,
)
_RATING_RE = re.compile(
    r"(?:\b(?:rating|rated|đánh giá)\s*[:=]?\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:sao|stars?)\b)",
    re.IGNORECASE,
)
_COUNT_FACT_RE = re.compile(
    r"(?<![\d/:])(\d+)\s*(người|khách|phòng|đêm|ngày|tháng|mét|people|guests|rooms|nights|days|months|meters|metres)\b",
    re.IGNORECASE,
)


def _currency(value: str) -> str:
    value = value.casefold()
    return {"đồng": "vnd", "đ": "vnd", "₫": "vnd", "$": "usd", "€": "eur"}.get(
        value, value
    )


def _unit_key(text: str, start: int = 0) -> str:
    dimensions: list[str] = []
    while match := _UNIT_RE.match(text, start):
        unit = match.group("unit").casefold().removesuffix("s")
        dimensions.append(
            _UNIT_NAMES.get(unit, unit) + ":" + (match.group("count") or "1")
        )
        start = match.end()
    return ";".join(sorted(dimensions))


def _claim_units(text: str) -> list[str]:
    """Keep clauses together: removing half a sentence can change its meaning."""

    units: list[str] = []
    for line in text.splitlines():
        # Decimal points, dates and sentence punctuation inside quoted prose
        # must not create a supported fragment of a contradictory statement.
        if '"' in line or "“" in line or "'" in line:
            parts = [line]
        else:
            parts = re.split(r"(?<!\d\.)(?<=[.!?])\s+(?=[A-ZÀ-Ỹ])", line)
        units.extend(part.strip() for part in parts if part.strip())
    return units


def _plain_unit(text: str) -> str:
    text = re.sub(r"^\s*(?:>\s*)+", "", text)
    text = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", text)
    return text.replace("**", "").replace("__", "").replace("`", "")


def _field_before(text: str, start: int, default: str) -> str:
    # A label does not carry across a sentence/semicolon or another numeric
    # value: 'price 100 USD, rating 5' binds each field independently.
    prefix = re.split(r"[;\n!?]", text[:start])[-1]
    labels = list(_FIELD_RE.finditer(prefix))
    if labels:
        field = labels[-1].lastgroup or default
        if default in {"date", "time"} and field in {
            "checkin",
            "checkout",
            "departure",
            "arrival",
        }:
            return f"{field}_{default}"
        if default == "number" and field in {"price", "rating"}:
            if re.search(r"\d", prefix[labels[-1].end() :]):
                return default
            return field
    return default


def _entity_at(text: str, start: int, names: set[str]) -> str:
    prefix = _normalize(text[:start])
    hits = [
        (prefix.rfind(name), name)
        for name in names
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", prefix)
    ]
    if hits:
        position, name = max(hits, key=lambda hit: (hit[0], len(hit[1])))
        # Two entities joined without an intervening value are ambiguous.
        preceding = prefix[:position].rstrip()
        if preceding.endswith((" and", " và", " or", " hoặc")):
            return "?"
        return name
    suffix = _normalize(text[start:])
    after = [
        (suffix.find(name), name)
        for name in names
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", suffix)
    ]
    return min(after)[1] if after else ""


def _prose_facts(text: str, source_id: str, names: set[str]) -> list[_Fact]:
    facts: list[_Fact] = []
    for original in _claim_units(text):
        unit = _plain_unit(original)
        occupied = [
            match.span()
            for match in _IDENTIFIER_RE.finditer(unit)
            if _identifier(match.group(0))
        ]
        for pattern, field in ((_DATE_RE, "date"), (_TIME_RE, "time")):
            for match in pattern.finditer(unit):
                value = match.group(0)
                if field == "time":
                    hour, minute = value.split(":")
                    value = f"{int(hour)}:{minute}"
                facts.append(
                    _Fact(
                        _entity_at(unit, match.start(), names),
                        _field_before(unit, match.start(), field),
                        value,
                        source_id=source_id,
                    )
                )
                occupied.append(match.span())
        for match in _RATING_RE.finditer(unit):
            value = _decimal_number(match.group(1) or match.group(2))
            if value is not None:
                facts.append(
                    _Fact(
                        _entity_at(unit, match.start(), names),
                        "rating",
                        _number_key(value)[7:],
                        source_id=source_id,
                    )
                )
                occupied.append(match.span())
        # A material quantity or warranty duration is not money merely because
        # an earlier label in the sentence says "báo giá".
        for match in _COUNT_FACT_RE.finditer(unit):
            if any(left <= match.start() < right for left, right in occupied):
                continue
            dimension = match.group(2).casefold().removesuffix("s")
            dimension = {"people": "person", "guest": "person", "mét": "meter",
                         "metre": "meter", **_UNIT_NAMES}.get(dimension, dimension)
            facts.append(_Fact(_entity_at(unit, match.start(), names), "count",
                               match.group(1), unit=dimension, source_id=source_id))
            occupied.append(match.span())
        for match in _MONEY_RE.finditer(unit):
            if any(left <= match.start() < right for left, right in occupied):
                continue
            value = _decimal_number(match.group("amount"))
            currency = _currency(match.group("currency") or match.group("prefix") or "")
            scale = (match.group("scale") or "").casefold()
            field = _field_before(unit, match.start(), "number")
            if not currency and not scale and field != "price":
                if (
                    field == "number"
                    and value is not None
                    and value >= 10
                    and _entity_at(unit, match.start(), names)
                ):
                    facts.append(
                        _Fact(
                            _entity_at(unit, match.start(), names),
                            "number",
                            _number_key(value)[7:],
                            source_id=source_id,
                        )
                    )
                continue
            # Explicit currency/scale identifies money, never ratings/counts.
            if value is None or (field == "rating" and not currency and not scale):
                continue
            if scale:
                value *= 1_000_000 if scale in {"triệu", "tr", "million"} else 1_000
                if not currency and scale in {"triệu", "tr", "nghìn", "ngàn"}:
                    currency = "vnd"
            denominator = _unit_key(unit, match.end())
            facts.append(
                _Fact(
                    _entity_at(unit, match.start(), names),
                    "price",
                    _number_key(value)[7:],
                    currency,
                    denominator,
                    source_id,
                )
            )
    return facts


def _json_facts(text: str, source_id: str) -> tuple[list[_Fact], set[str]]:
    facts: list[_Fact] = []
    names: set[str] = set()

    def visit(value: object, entity: str = "", depth: int = 0, currency: str = "") -> None:
        if depth > 10:
            return
        if isinstance(value, str):
            nested = _read_json(value)
            if nested is not None:
                visit(nested, entity, depth + 1, currency)
            else:
                text_names = _proper_name_anchors(value)
                names.update(text_names)
                for fact in _prose_facts(value, source_id, names):
                    facts.append(
                        _Fact(
                            fact.entity or entity,
                            fact.field,
                            fact.value,
                            fact.currency,
                            fact.unit,
                            source_id,
                        )
                    )
            return
        if isinstance(value, list):
            for child in value:
                visit(child, entity, depth + 1, currency)
            return
        if not isinstance(value, dict):
            return
        # Runtime envelope names identify tools, never the business entity
        # that owns every amount in their output. Inputs are not results.
        if "tool_call" in value and isinstance(value.get("tool_result"), dict):
            visit(value["tool_result"], depth=depth + 1)
            return
        if value.get("type") == "tool_result":
            visit(value.get("output"), depth=depth + 1)
            return
        identity = next(
            (
                value[key]
                for key in (
                    "name",
                    "hotel",
                    "hotel_name",
                    "entity",
                    "label",
                    "staff_name",
                )
                if isinstance(value.get(key), str)
            ),
            entity,
        )
        entity = _normalize(identity)
        if entity:
            names.add(entity)
        currency = _currency(str(value.get("currency", currency)))
        for key, child in value.items():
            normalized = re.sub(r"[_-]", " ", key).casefold()
            number = (
                _decimal_number(str(child))
                if isinstance(child, (int, float, str)) and not isinstance(child, bool)
                else None
            )
            money_field = any(
                word in normalized.split()
                for word in ("price", "cost", "amount", "budget", "reserve", "total")
            )
            if money_field and (number is not None or isinstance(child, str)):
                own_currency = next(
                    (
                        part.casefold()
                        for part in _CURRENCIES.split("|")
                        if part.casefold() in normalized.split()
                    ),
                    currency,
                )
                measure = _UNIT_RE.search(normalized)
                denominator = ""
                if measure:
                    denominator = _unit_key(normalized, measure.start())
                elif isinstance(value.get("unit", value.get("per")), str):
                    measure_text = re.sub(
                        r"[_-]", " ", value.get("unit", value.get("per"))
                    )
                    denominator = _unit_key(
                        measure_text
                        if re.match(r"(?:per|mỗi|/)", measure_text)
                        else "/" + measure_text
                    )
                if number is not None:
                    facts.append(
                        _Fact(
                            entity,
                            "price",
                            _number_key(number)[7:],
                            own_currency,
                            denominator,
                            source_id,
                        )
                    )
                else:
                    for fact in _prose_facts(f"{normalized} {child}", source_id, set()):
                        if fact.field == "price":
                            facts.append(
                                _Fact(
                                    entity,
                                    "price",
                                    fact.value,
                                    fact.currency or own_currency,
                                    fact.unit or denominator,
                                    source_id,
                                )
                            )
            elif (
                normalized in {"rating", "stars", "star rating"} and number is not None
            ):
                facts.append(
                    _Fact(
                        entity, "rating", _number_key(number)[7:], source_id=source_id
                    )
                )
            elif (
                normalized
                in {"people", "guests", "rooms", "nights", "days", "quantity", "warranty months"}
                and number is not None
            ):
                dimension = {"people": "person", "guests": "person", "warranty months": "month"}.get(
                    normalized, normalized.removesuffix("s")
                )
                facts.append(
                    _Fact(
                        entity,
                        "count",
                        _number_key(number)[7:],
                        unit=dimension,
                        source_id=source_id,
                    )
                )
            elif isinstance(child, str) and (
                _DATE_RE.search(child) or _TIME_RE.search(child)
            ):
                for fact in _prose_facts(f"{normalized} {child}", source_id, names):
                    facts.append(
                        _Fact(
                            entity,
                            fact.field,
                            fact.value,
                            fact.currency,
                            fact.unit,
                            source_id,
                        )
                    )
            if isinstance(child, (dict, list, str)):
                visit(child, entity, depth + 1, currency)

    value = _read_json(text)
    if value is not None:
        visit(value)
    return facts, names


def _read_json(text: str) -> object:
    # Runtime prefixes such as 'E3: {...}' retain record boundaries.
    stripped = text.strip()
    match = re.match(r"(?:E\d+\s*:\s*)?([\[{].*)", stripped, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (TypeError, ValueError):
        return None


def business_records(text: str) -> list[dict]:
    """Decode business output, including labelled CaseEvidence documents.

    Tool inputs, tool names and transport metadata are not business facts.
    Keep records separate so booleans cannot be borrowed across objects.
    """
    records: list[dict] = []

    def visit(value, depth=0):
        if depth > 12:
            return
        if isinstance(value, str):
            parsed = _read_json(value)
            if parsed is not None:
                visit(parsed, depth + 1)
            else:
                for match in re.finditer(r"(?:^|\n)(?:E\d+:\s*)?[^\n{]*([\[{])", value):
                    try:
                        parsed, _ = json.JSONDecoder().raw_decode(value[match.start(1):])
                        visit(parsed, depth + 1)
                    except ValueError:
                        pass
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif isinstance(value, dict):
            if isinstance(value.get("tool_result"), dict):
                visit(value["tool_result"].get("output"), depth + 1)
            elif value.get("type") == "tool_result":
                visit(value.get("output"), depth + 1)
            else:
                records.append(value)
                for child in value.values():
                    if isinstance(child, (dict, list, str)):
                        visit(child, depth + 1)

    visit(text)
    return records


def _business_state_failures(text: str, sources: list[EvidenceSource]) -> set[str]:
    """Guard critical transitions independently of name/number matching."""
    records = [record for source in sources if source.authority == "tool"
               for record in business_records(source.content)]
    checks = (
        ("ticket_closed", r"(?:phiếu|ticket|yêu cầu)\s+(?:này\s+)?(?:đã\s+)?đóng|ticket\s+(?:is\s+)?closed",
         lambda r: r.get("ticket_closed") is True or r.get("ticket_status") == "closed"),
        ("resident_accepted", r"cư dân\s+đã\s+(?:nghiệm thu|xác nhận|chấp nhận)|resident\s+(?:has\s+)?accepted",
         lambda r: r.get("resident_accepted") is True),
    )
    failures = set()
    for key, pattern, supported in checks:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        affirmative = [m for m in matches if not re.search(
            r"(?:không|chưa|not|never)(?:\s+\w+){0,5}\s*$",
            text[max(0, m.start()-55):m.start()], re.IGNORECASE)]
        if affirmative and not any(supported(record) for record in records):
            failures.add("state:" + key)
    return failures


def _entity_key(value: str) -> str:
    return re.sub(r"^(?:nhà xe|xe|limousine)\s+", "", value)


def _matching_fact(claim: _Fact, evidence: _Fact) -> bool:
    # A general party/room/night constraint (often customer supplied) applies
    # to a selected option too. A count explicitly tied to another entity does
    # not. Monetary values and unit prices always retain entity binding.
    general_count = claim.field == evidence.field == "count" and not evidence.entity
    if (
        claim.entity
        and _entity_key(claim.entity) != _entity_key(evidence.entity)
        and not general_count
    ):
        return False
    # An unlabeled date/time may abbreviate a typed source, never vice versa.
    if claim.field != evidence.field and (
        claim.field not in {"date", "time"}
        or not evidence.field.endswith("_" + claim.field)
    ):
        return False
    if claim.currency and claim.currency != evidence.currency:
        return False
    if claim.unit and claim.unit != evidence.unit:
        return False
    # An omitted denominator can summarize a price, but an explicitly claimed
    # denominator must be present in the same evidence record.
    if claim.field.endswith("date"):
        return _date_is_supported("date:" + claim.value, {"date:" + evidence.value})
    return claim.value == evidence.value


def _conflicting_fact(candidate: _Fact, facts: list[_Fact]) -> bool:
    """Do not choose among contradictory scalar prices/ratings.

    Dates, departure times and counts can describe valid sets of options. The
    anchor check binds them to their entity/field without assuming uniqueness.
    """

    if (
        candidate.field not in {"price", "rating"}
        or not candidate.entity
        or candidate.entity == "?"
    ):
        return False
    for other in facts:
        if (
            _entity_key(candidate.entity) != _entity_key(other.entity)
            or candidate.field != other.field
            or candidate.currency != other.currency
            or candidate.unit != other.unit
        ):
            continue
        if candidate.value != other.value:
            return True
    return False


def _derived_money(facts: list[_Fact]) -> dict[str, set[str]]:
    """Bounded arithmetic uses monetary operands of one currency only."""

    result: dict[str, set[str]] = {}
    currencies = {
        fact.currency for fact in facts if fact.field == "price" and fact.currency
    }
    counts: dict[str, set[Decimal]] = {}
    for fact in facts:
        if (
            fact.field == "count"
            and fact.unit in {"person", "room", "night", "day"}
            and 1 <= Decimal(fact.value) <= 31
            and not _conflicting_fact(fact, facts)
        ):
            counts.setdefault(fact.unit, set()).add(Decimal(fact.value))
    for currency in currencies:
        monetary = [
            fact
            for fact in facts
            if fact.field == "price"
            and fact.currency == currency
            and not _conflicting_fact(fact, facts)
        ]
        products: set[Decimal] = set()
        for fact in monetary:
            if not fact.unit:
                continue
            factors = {Decimal(1)}
            for dimension in fact.unit.split(";"):
                name, denominator = dimension.split(":")
                factors = {
                    left * right / Decimal(denominator)
                    for left in factors
                    for right in counts.get(name, set())
                    if left * right <= 200
                }
            products.update(Decimal(fact.value) * factor for factor in factors)
        values = sorted(
            {Decimal(fact.value) for fact in monetary if not fact.unit} | products
        )[:40]
        first = {
            value
            for left, right in combinations(values, 2)
            for value in (left + right, abs(left - right))
        }
        derived = first | {abs(left - right) for left in first for right in values}
        derived |= products
        result[currency] = {_number_key(value)[7:] for value in derived if value > 0}
    return result


def validate_claims(
    claim: str,
    supporting_texts: Iterable[str | EvidenceSource],
) -> ClaimValidation:
    """Validate bounded, deterministic anchors, retaining whole valid units.

    This checks explicit names/numbers and common typed fields, not arbitrary
    semantics or whether a trusted source is true. Unknown associations do not
    gain support by borrowing another entity's number or another record's unit.
    """

    sources = [
        source
        if isinstance(source, EvidenceSource)
        else EvidenceSource(source, f"source:{index}")
        for index, source in enumerate(supporting_texts)
        if source
        and (source.content if isinstance(source, EvidenceSource) else source).strip()
    ]
    normalized_support = [_normalize(source.content) for source in sources]
    supported_numbers: set[str] = set()
    facts: list[_Fact] = []
    names: set[str] = set()
    for source in sources:
        supported_numbers.update(_numeric_anchors(source.content))
        structured, structured_names = _json_facts(source.content, source.source_id)
        names.update(structured_names)
        names.update(_proper_name_anchors(source.content))
        facts.extend(structured)
    for source in sources:
        if _read_json(source.content) is None:
            facts.extend(_prose_facts(source.content, source.source_id, names))
    derived = _derived_money(facts)
    unsupported: set[str] = set()
    supported: list[str] = []
    rejected: list[str] = []
    has_concrete_claims = False
    for original in _claim_units(claim):
        text = _plain_unit(original)
        failures: set[str] = _business_state_failures(text, sources)
        own_names = _proper_name_anchors(text)
        for anchor in own_names:
            if not any(
                re.search(rf"(?<!\w){re.escape(anchor)}(?!\w)", source)
                for source in normalized_support
            ):
                failures.add(f"name:{anchor}")
        claim_facts = _prose_facts(text, "claim", names | own_names)
        has_concrete_claims |= bool(own_names or claim_facts or _numeric_anchors(text))
        typed_anchors = {_fact_anchor(fact) for fact in claim_facts}
        for fact in claim_facts:
            matching = [
                candidate for candidate in facts if _matching_fact(fact, candidate)
            ]
            if matching and not any(
                _conflicting_fact(candidate, facts) for candidate in matching
            ):
                continue
            # Arithmetic support is for generic totals/remainders, never a
            # named entity's stated price, rating, unit price or individual ID.
            calculating = re.search(
                r"\b(?:total|tổng|còn|budget|ngân sách|reserve|dự phòng|trần chi)\b",
                text,
                re.IGNORECASE,
            ) or any(candidate.field == "count" for candidate in claim_facts)
            if (
                calculating
                and fact.field == "price"
                and not fact.entity
                and not fact.unit
                and fact.value in derived.get(fact.currency, set())
            ):
                continue
            failures.add(_fact_anchor(fact))
        for anchor in _numeric_anchors(text) - typed_anchors:
            if anchor not in supported_numbers and not (
                anchor.startswith("date:")
                and _date_is_supported(anchor, supported_numbers)
            ):
                failures.add(anchor)
        unsupported.update(failures)
        (rejected if failures else supported).append(original)
    return ClaimValidation(
        tuple(sorted(unsupported)),
        "\n".join(supported),
        tuple(rejected),
        has_concrete_claims,
    )


def _fact_anchor(fact: _Fact) -> str:
    if fact.field.endswith("date"):
        return "date:" + fact.value
    if fact.field.endswith("time"):
        return "time:" + fact.value
    return "number:" + fact.value


def unsupported_claim_anchors(
    claim: str,
    supporting_texts: Iterable[str | EvidenceSource],
) -> tuple[str, ...]:
    """Compatibility facade for callers that only need rejected anchors."""

    return validate_claims(claim, supporting_texts).unsupported


__all__ = [
    "ClaimValidation",
    "EvidenceSource",
    "unsupported_claim_anchors",
    "validate_claims",
]
