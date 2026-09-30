"""Vietnamese text normalization & slang/abbreviation resolver for tickets.

Handles common resident shorthand, real estate domain abbreviations (BQL, PCCC, TM, CH...),
and Vietnamese teencode/slang to ensure both ML feature extractors and LLMs
receive clean, unambiguous semantic input.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Domain-specific abbreviation dictionary (Real estate & Resident management)
# ---------------------------------------------------------------------------
DOMAIN_ABBREVIATIONS: dict[str, str] = {
    # Management, Security & Operations
    "bql": "ban quản lý",
    "bqt": "ban quản trị",
    "bv": "bảo vệ",
    "kt": "kỹ thuật",
    "lc": "lao công",
    "vs": "vệ sinh",
    "lt": "lễ tân",
    "letan": "lễ tân",
    "cskh": "chăm sóc khách hàng",
    "nv": "nhân viên",
    "admin": "quản trị viên",
    "ad": "quản trị viên",

    # Equipment & Utilities
    "tm": "thang máy",
    "tmay": "thang máy",
    "tbo": "thang bộ",
    "tthoat": "thang thoát hiểm",
    "pccc": "phòng cháy chữa cháy",
    "bc": "báo cháy",
    "đh": "điều hòa",
    "dh": "điều hòa",
    "dhoa": "điều hòa",
    "nl": "nóng lạnh",
    "nlanh": "nóng lạnh",
    "cb": "cầu dao điện",
    "at": "cầu dao điện",
    "aptomat": "cầu dao điện",
    "camera": "camera an ninh",
    "cam": "camera",
    "cctv": "camera an ninh",
    "wifi": "mạng wifi",
    "rac": "rác thải",
    "pr": "phòng rác",

    # Locations & Property Units
    "ch": "căn hộ",
    "can": "căn hộ",
    "p": "phòng",
    "phg": "phòng",
    "t": "tầng",
    "tg": "tầng",
    "sh": "shophouse",
    "shop": "shophouse",
    "kđt": "khu đô thị",
    "kdt": "khu đô thị",
    "pk": "phân khu",
    "bt": "biệt thự",
    "cc": "chung cư",
    "ham": "tầng hầm",
    "sanh": "sảnh",
    "hl": "hành lang",
    "st": "sân thượng",
    "bbq": "khu tiệc nướng",
    "beboi": "bể bơi",

    # Documents, Fees & Vehicle Management
    "cccd": "căn cước công dân",
    "cmnd": "chứng minh nhân dân",
    "tt": "thường trú",
    "kt3": "tạm trú",
    "bgt": "bàn giao thẻ",
    "pdv": "phí dịch vụ",
    "pql": "phí quản lý",
    "thexe": "thẻ xe",
    "oto": "ô tô",
    "4b": "ô tô",
    "xm": "xe máy",
    "2b": "xe máy",
    "sdt": "số điện thoại",
    "sđt": "số điện thoại",
}

# ---------------------------------------------------------------------------
# Common Vietnamese teencode & conversational slang dictionary
# ---------------------------------------------------------------------------
SLANG_TEENCODE: dict[str, str] = {
    # Negation & Affirmation
    "k": "không",
    "ko": "không",
    "kh": "không",
    "khong": "không",
    "hong": "không",
    "hông": "không",
    "hok": "không",
    "hem": "không",
    "k0": "không",
    "kô": "không",
    "dc": "được",
    "đc": "được",
    "dk": "được",
    "đk": "được",
    "uk": "ừ",
    "uh": "ừ",
    "uhm": "ừ",
    "um": "ừ",
    "okie": "đồng ý",
    "ok": "đồng ý",
    "oke": "đồng ý",
    "oki": "đồng ý",
    "yes": "đồng ý",

    # Pronouns & Conjunctions
    "m": "mình",
    "mk": "mình",
    "mik": "mình",
    "t": "tôi",
    "tui": "tôi",
    "e": "em",
    "a": "anh",
    "c": "chị",
    "mn": "mọi người",
    "mng": "mọi người",
    "ng": "người",
    "nguoi": "người",
    "vs": "với",
    "cx": "cũng",
    "cg": "cũng",
    "bt": "bình thường",
    "ntn": "như thế nào",
    "s": "sao",
    "sao": "sao",
    "nhug": "nhưng",
    "nhg": "nhưng",
    "ib": "nhắn tin",
    "inbox": "nhắn tin",
    "rep": "trả lời",
    "tl": "trả lời",
    "trloi": "trả lời",
    "check": "kiểm tra",
    "ktra": "kiểm tra",
    "fix": "sửa chữa",
    "help": "cứu giúp",
    "cuu": "cứu giúp",

    # Incident States, Severity & Urgency
    "hỏng": "bị hỏng",
    "hong roi": "bị hỏng rồi",
    "chay": "cháy",
    "chay khet": "cháy khét",
    "khet": "khét lẹt",
    "chap": "chập điện",
    "chap dien": "chập điện",
    "no": "phát nổ",
    "gap": "gấp",
    "khẩn": "khẩn cấp",
    "nhanh": "nhanh chóng",
    "luon": "ngay lập tức",
    "ngay": "ngay lập tức",
    "vl": "rất nhiều",
    "vcl": "rất nhiều",
    "vch": "rất nhiều",
    "vcc": "rất nhiều",
    "qua": "quá",
    "vai": "rất nhiều",
    "toang": "hỏng nặng",
    "toang roi": "hỏng nặng rồi",
    "chet": "hỏng hoàn toàn",
    "die": "hỏng hoàn toàn",
    "ngom": "hỏng hoàn toàn",
    "sap": "sập hỏng",
    "ngap": "ngập nước",
    "tran": "tràn nước",
    "buc ong": "bục đường ống nước",
}


def normalize_vietnamese_text(text: str) -> str:
    """Normalize raw ticket text:
    1. Unicode NFC normalization (fix decomposed tone marks).
    2. Lowercase and whitespace cleanup.
    3. Normalize apartment / building identifiers (e.g., s2.01, s201 -> S2.01).
    4. Replace domain abbreviations & slang words.
    5. Clean special punctuation while preserving sentence boundaries.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode NFC normalization
    text = unicodedata.normalize("NFC", text.strip())

    # 2. Tokenize words while keeping punctuation and building codes
    # \w in Python 3 natively matches Unicode characters (accents, tone marks)
    tokens = re.findall(r"[\w.]+|[^\w\s]", text, flags=re.UNICODE)
    normalized_tokens: list[str] = []

    for token in tokens:
        lower_token = token.lower()
        
        # Standardize building format like s201 -> tòa S2.01
        building_match = re.match(r"^([sS][1-3])(\d{2})$", token)
        if building_match:
            b_prefix, b_num = building_match.groups()
            normalized_tokens.append(f"tòa {b_prefix.upper()}.{b_num}")
            continue

        # Check domain dictionary first, then slang dictionary
        if lower_token in DOMAIN_ABBREVIATIONS:
            normalized_tokens.append(DOMAIN_ABBREVIATIONS[lower_token])
        elif lower_token in SLANG_TEENCODE:
            normalized_tokens.append(SLANG_TEENCODE[lower_token])
        else:
            normalized_tokens.append(token)

    result = " ".join(normalized_tokens)
    # Fix whitespace before punctuation marks (except dots in numbers/codes)
    result = re.sub(r'\s+([,;:?!])', r'\1', result)
    return result
