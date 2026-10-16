"""Tools and leader scripts for the approval tests (slice S4): a hotel booking that needs the resident's consent.

`hotel_search` is a look-up; `book_hotel` has a side effect (it appends to BOOKED, which a test counts) and is
declared in `wf_tools` with `requires_consent`. The scripts play the leader (and the technician) of the
trip: ask what suits, then book or ask for consent to a cost. Scripted model only.
"""
from __future__ import annotations

import re

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk
from pydantic import Field

from enginekit import evidence_of
from fake_llm import Call
from scripts import say

HOTELS = "Lotus 2 nights: 1500000 VND; Sunrise 2 nights: 1800000 VND; service fee: 90000 VND; quote quote_001"
BOOKING = "Booking confirmed: BK-77 Sunrise 2 nights 1800000 VND, status: confirmed"
BOOK = {"hotel": "Sunrise", "nights": 2, "price": "1800000"}
BOOKED: list[dict] = []  # every time book_hotel really ran
START = "Plan two nights in a hotel for me."
CHOOSE = "Sunrise please."


class _SearchP(ParamsBase):
    city: str = Field(description="City")


class _BookP(ParamsBase):
    hotel: str = Field(description="Hotel")
    nights: int = Field(description="Nights")
    price: str = Field(description="Price in VND")


class HotelSearch(ToolBase):
    name = "hotel_search"
    description = "Find hotels."
    input_schema = _SearchP.model_json_schema()
    is_read_only = True
    is_concurrency_safe = True

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="test")

    async def call(self, city: str):
        return ToolChunk(content=[TextBlock(text=HOTELS)], state=ToolResultState.SUCCESS)


class BookHotel(ToolBase):
    name = "book_hotel"
    description = "Book a hotel. The resident must agree first."
    input_schema = _BookP.model_json_schema()
    is_read_only = False
    is_concurrency_safe = False

    async def check_permissions(self, *a, **k):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="test")

    async def call(self, hotel: str, nights: int, price: str):
        BOOKED.append({"hotel": hotel, "nights": nights, "price": price})
        return ToolChunk(content=[TextBlock(text=BOOKING)], state=ToolResultState.SUCCESS)


def factory(rt, b) -> list:
    return [HotelSearch(), BookHotel()]


def declare(w, name: str = "book_hotel", consent: bool = True, summary: str = "Book {hotel} for {nights} nights at {price} VND") -> None:
    """The route's `wf_tools` row (S5 adds the API that writes it)."""
    w.sql("insert into wf_tools (route_id, name, server, mcp_tool, kind, read_only, requires_consent, tracking, "
          "consent_summary, call_timeout) values (?, ?, 'hotels', ?, 'action', ?, ?, 'none', ?, 8.0) "
          "on conflict do nothing",
          (w.flow.route["route_id"], name, name, False, bool(consent), summary))


# ---- the leader ------------------------------------------------------------------------------------------------
def asking(c: Call) -> list | None:
    """First step of every trip: look the hotels up and offer them."""
    turn = c.after_user()
    if turn.called("hotel_search") == 0:
        return [("hotel_search", {"city": "Da Nang"})]
    ev = evidence_of(" ".join(turn.results("hotel_search")))
    if turn.called("CaseSay") == 0:
        return say("Two options: Lotus 1500000 VND or Sunrise 1800000 VND. Which one?", "reply", ev[:1])
    return None


BOOK2 = {"hotel": "Lotus", "nights": 2, "price": "1500000"}
EXPIRED = "Your consent request expired. Do you still want it?"


def trip(c: Call):
    """13.1 with book_hotel as the tool that needs consent: offer, book (the gate asks), then ask to confirm."""
    if "<platform-notice" in c.last_user:
        return say(EXPIRED, "reply") if not c.after_user().called("CaseSay") else "Said."
    if CHOOSE not in c.last_user:
        return asking(c) or "Said."
    turn = c.after_user()
    if turn.called("book_hotel") == 0:
        return [("book_hotel", BOOK)]
    got = " ".join(turn.results("book_hotel"))
    if turn.called("CaseSay") == 0:
        if "BK-77" in got:
            return say("Booked: BK-77 at Sunrise. Is everything right?", "confirmation", evidence_of(got)[:1])
        return say("Understood, nothing was booked. Anything else?", "reply")
    return "Said."


def two_books(c: Call):
    """Two tools that need consent in ONE reply: the run parks on the first, then again on the second."""
    if CHOOSE not in c.last_user:
        return asking(c) or "Said."
    turn = c.after_user()
    if turn.called("book_hotel") == 0:
        return [("book_hotel", BOOK), ("book_hotel", BOOK2)]
    got = " ".join(turn.results("book_hotel"))
    if turn.called("CaseSay") == 0:
        if "BK-77" in got:
            return say("Booked: BK-77. Is everything right?", "confirmation", evidence_of(got)[:1])
        return say("Understood, nothing was booked. Anything else?", "reply")
    return "Said."


def after_booking(kind: str):
    """The leader books, then (kind="finalize") calls CaseFinalize(resolved), or (kind="closed") tells the resident
    the request is closed (the guard refuses that) and then says what is true."""
    def script(c: Call):
        if CHOOSE not in c.last_user:
            return asking(c) or "Said."
        turn = c.after_user()
        if turn.called("book_hotel") == 0:
            return [("book_hotel", BOOK)]
        ev = evidence_of(" ".join(turn.results("book_hotel")))
        if kind == "finalize" and turn.called("CaseFinalize") == 0:
            return [("CaseFinalize", {"answer": "Booked: BK-77 at Sunrise.", "outcome": "resolved", "cites": ev[:1]})]
        if kind == "closed" and turn.called("CaseSay") == 0:
            return say("Booked: BK-77 at Sunrise. Your request is closed.", "none", ev[:1])
        if kind == "closed" and turn.called("CaseSay") == 1 and turn.results("CaseSay")[-1].startswith("Not sent"):
            return say("Booked: BK-77 at Sunrise.", "none", ev[:1])
        return "Done."
    return script


def consenting(total: str = "1890000", retry: str | None = None, quote: str | None = None):
    """The leader asks for consent to a cost with CaseAskConsent. A total that is wrong is refused; `retry` is the
    total it sends then (None: it gives up and says so)."""
    def args(shown: str, cites: list[str]) -> dict:
        return {"summary": "Book Sunrise for 2 nights", "cites": cites, "total": shown,
                "items": [{"label": "Sunrise 2 nights", "amount": "1800000"}, {"label": "Service fee", "amount": "90000"}],
                **({"quote_ref": quote} if quote else {})}

    def script(c: Call):
        if "<platform-notice" in c.last_user:
            return say(EXPIRED, "reply") if not c.after_user().called("CaseSay") else "Said."
        if CHOOSE not in c.last_user:
            return asking(c) or "Said."
        turn = c.after_user()
        if turn.called("calc_sum") == 0:
            return [("calc_sum", {"label": "booking", "values": ["1800000", "90000"]})]
        cites = [evidence_of(c.blob)[0], evidence_of(" ".join(turn.results("calc_sum")))[0]]  # the look-up, then the sum
        asked, got = turn.called("CaseAskConsent"), turn.results("CaseAskConsent")
        if asked == 0:
            return [("CaseAskConsent", args(total, cites))]
        refused = got[-1].startswith("Not asked")
        if refused and asked == 1 and retry:
            return [("CaseAskConsent", args(retry, cites))]
        if turn.called("CaseSay") == 0:
            if "The resident agreed" in got[-1]:
                return say("Thank you, you agreed to 1890000 VND.", "confirmation", evidence_of(got[-1])[:1])
            if refused:
                return say("I cannot confirm the total yet; a person will follow up.", "reply")
            return say("Understood, I will not go on. Anything else?", "reply")
        return "Said."
    return script


def tech_books(c: Call):
    """The technician books the hotel itself (the gate asks the resident for it), records the fact, reports."""
    turn = c
    if turn.called("book_hotel") == 0:
        return [("book_hotel", BOOK)]
    ev = evidence_of(" ".join(turn.results("book_hotel")))
    if ev and turn.called("CaseFact") == 0:
        return [("CaseFact", {"text": "Booking BK-77 at Sunrise is confirmed", "evidence": ev[:1]})]
    if turn.called("TeamSay") == 0:
        return [("TeamSay", {"content": "Booked, see my fact.", "to": None})]
    return "Reported."


def via_tech(c: Call):
    """The leader looks the hotels up, brings in the technician, and tells the resident what the technician's fact says."""
    if "<platform-notice" in c.last_user:
        return say(EXPIRED, "reply") if not c.after_user().called("CaseSay") else "Said."
    if c.called("hotel_search") == 0:
        return [("hotel_search", {"city": "Da Nang"})]
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "trip-team", "description": "Book the hotel"})]
    if c.called("AgentCreate") == 0:
        return [("AgentCreate", {"name": "tech", "description": "Books hotels", "subagent_type": "tech",
                                 "prompt": "Book the Sunrise hotel for two nights."})]
    facts = re.findall(r"\b(F\d+) tech:", c.blob)
    if facts and not c.after_user().called("CaseSay"):
        return say("Booked: BK-77 at Sunrise. Is everything right?", "confirmation", facts[:1])
    return "Waiting for the specialists."


def both(c: Call):
    """The leader looks the hotels up, brings in the technician and books a second hotel itself: both end up parked on
    the resident. (The look-up is what grounds the prices of both bookings: the gate asks the resident about no
    figure the case file does not state.)"""
    if c.called("hotel_search") == 0:
        return [("hotel_search", {"city": "Da Nang"})]
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "trip-team", "description": "Book the hotel"})]
    if c.called("AgentCreate") == 0:
        return [("AgentCreate", {"name": "tech", "description": "Books hotels", "subagent_type": "tech",
                                 "prompt": "Book the Sunrise hotel for two nights."})]
    if c.called("book_hotel") == 0:
        return [("book_hotel", BOOK2)]
    said = c.called("CaseSay")
    if said == 0:
        ev = evidence_of(" ".join(c.results("book_hotel")))
        if ev:
            return say("One booking is done: BK-77. The other waits for your consent.", "none", ev[:1])
        return say("Understood, nothing was booked.", "none")
    facts = re.findall(r"\b(F\d+) tech:", c.blob)
    if facts and said == 1:
        return say("Both are booked: BK-77 at Sunrise. Is everything right?", "confirmation", facts[:1])
    return "Waiting for the specialists."
