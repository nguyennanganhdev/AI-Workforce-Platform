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
    for quoted in _QUOTED_RE.findall(text):
        normalized = _normalize(quoted)
        # A quoted name is a few words; a quoted sentence (a proposed reply
        # to the user) is not a name, its own words are checked below.
        if len(normalized) >= 3 and not normalized.isdigit() and len(normalized.split()) <= 6:
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
            while selected and _normalize(selected[-1]) in _CONNECTORS:
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


def _derived_amount_anchors(anchors: set[str]) -> set[str]:
    """Validate one-step total/remainder arithmetic without trusting prose.

    Only amount-sized values participate. Dates, times, ratings and counts are
    never derived. This admits auditable sums/differences such as
    ``budget - reserve`` and ``budget - verified total``.
    """

    values: set[Decimal] = set()
    for anchor in anchors:
        if not anchor.startswith("number:"):
            continue
        try:
            value = Decimal(anchor.removeprefix("number:"))
        except InvalidOperation:
            continue
        if abs(value) >= 10_000:
            values.add(value)

    originals = sorted(values)[:40]
    first_level: set[Decimal] = set()
    for left, right in combinations(originals, 2):
        first_level.add(left + right)
        first_level.add(abs(left - right))

    # A reserve margin is commonly a two-step derivation:
    # ``(budget - reserve) - verified_total``.  Permit exactly that depth,
    # bounded against the original evidence values rather than an unbounded
    # arithmetic closure.
    second_level = {
        abs(derived - original)
        for derived in first_level
        for original in originals
    }
    # Unit price x evidenced quantity: "1.200.000 per night" for "2 nights"
    # (and rooms x nights) gives 2.400.000, then plus one other evidenced
    # amount (a car) gives the trip total. Quantities are small evidenced
    # integers only, so a model cannot multiply arbitrary numbers into
    # support for an invented figure.
    counts = sorted(
        {
            int(value)
            for value in _evidenced_numbers(anchors)
            if 1 < value <= 31 and value == value.to_integral_value()
        },
    )[:8]
    factors = set(counts)
    factors.update(a * b for a, b in combinations(counts, 2) if a * b <= 200)
    factors.update(count * count for count in counts if count * count <= 200)
    products = {
        amount * factor
        for amount in originals
        for factor in sorted(factors)[:30]
    }
    with_one_more = {
        product + original for product in products for original in originals
    }
    derived = {
        _number_key(value)
        for value in (*first_level, *second_level, *products, *with_one_more)
        if value != 0
    }
    return derived


def _evidenced_numbers(anchors: set[str]) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for anchor in anchors:
        if not anchor.startswith("number:"):
            continue
        try:
            numbers.add(Decimal(anchor.removeprefix("number:")))
        except InvalidOperation:
            continue
    return numbers


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


def unsupported_claim_anchors(
    claim: str,
    supporting_texts: Iterable[str],
) -> tuple[str, ...]:
    """Return concrete claim anchors absent from all supplied evidence."""

    supports = [text for text in supporting_texts if text and text.strip()]
    normalized_support = [_normalize(text) for text in supports]
    supported_numbers: set[str] = set()
    for text in supports:
        supported_numbers.update(_numeric_anchors(text))
    supported_numbers.update(_derived_amount_anchors(supported_numbers))

    unsupported: set[str] = set()
    for anchor in _proper_name_anchors(claim):
        if not any(anchor in text for text in normalized_support):
            unsupported.add(f"name:{anchor}")
    for anchor in _numeric_anchors(claim):
        supported = anchor in supported_numbers
        if anchor.startswith("date:"):
            # A day/month mention is an abbreviation of the same fully
            # evidenced date, including an ISO-formatted source value.
            supported = supported or _date_is_supported(
                anchor,
                supported_numbers,
            )
        if not supported:
            unsupported.add(anchor)
    return tuple(sorted(unsupported))


__all__ = ["unsupported_claim_anchors"]
