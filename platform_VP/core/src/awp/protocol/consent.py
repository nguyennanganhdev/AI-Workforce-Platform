"""CaseAskConsent: the leader asks the resident to agree to a cost before it commits them to it (decision D6).

The tool never decides anything itself. The approval gate (workforce/approvals.py) stops every call to it with
an ASK, after `review` has checked the numbers, so a wrong total creates no approval and the resident is
never asked. When the resident agrees the agent resumes and `call` records what they agreed to as evidence;
when they refuse the agent is told DENIED.
"""
from __future__ import annotations

import re
from decimal import Decimal

from agentscope.tool import ToolChunk

from ..guard import figures_text
from ..workforce.lookup import workflow_of_case
from ..workforce.speak import BadText, checked, problems
from .calc import NotANumber, to_decimal, total_of
from .tools import _CaseTool, _ok

MAX_SUMMARY = 300
MAX_ITEMS = 30
MAX_LABEL = 120
MAX_QUOTE = 80
# Digits with optional separators and one decimal part. Decimal() alone also takes NaN, Infinity and
# exponents, none of which is an amount a resident can read (and some break the comparison below).
_AMOUNT = re.compile(r"^\d[\d, ]{0,23}(?:\.\d{1,4})?$")
_NUMBER = {"type": ["string", "integer"]}


class CaseAskConsent(_CaseTool):
    name = "CaseAskConsent"
    description = ("Leader only. Ask the resident to agree to a cost. summary says what they agree to, items list "
                   "each cost line (label, amount), total must be exactly the sum of the amounts: compute it with "
                   "calc_sum. Every amount and the total must appear in the items you cite. The resident is asked "
                   "and you are woken with their answer: agreed (the tool returns) or declined (it is DENIED; "
                   "tell the resident and do not charge them).")
    input_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "What the resident agrees to, in a sentence."},
            "items": {"type": "array", "minItems": 1, "maxItems": MAX_ITEMS, "items": {
                "type": "object", "required": ["label", "amount"],
                "properties": {"label": {"type": "string"}, "amount": {**_NUMBER, "description": "Digits, as the cited item states it."}}}},
            "total": {**_NUMBER, "description": "The sum of the amounts, from calc_sum."},
            "quote_ref": {"type": "string", "description": "The partner's quote id, when there is one."},
            "cites": {"type": "array", "items": {"type": "string"}, "description": "Evidence/fact ids (E.., F..) that state the amounts."},
        },
        "required": ["summary", "items", "total", "cites"],
    }

    async def review(self, summary: str = "", items: list | None = None, total: str | int = "",
                     cites: list[str] | None = None, quote_ref: str | None = None, **_: object) -> tuple[str | None, dict]:
        """(why the resident must not be asked, what they will be shown). One of the two is empty."""
        refusal = self._leader_only() or await self._closed()
        if refusal:
            return refusal.content[0].text, {}
        wf = await workflow_of_case(self.rt.db, self.b.case_id)
        if wf is None:
            return "CaseAskConsent works only inside a workflow.", {}
        try:
            summary = checked(summary, MAX_SUMMARY)
        except BadText as e:
            return f"Not asked: the summary is wrong. {e}", {}
        lines = [x for x in items or [] if isinstance(x, dict)]
        if not lines or len(lines) != len(items or []):
            return "Not asked: items must be a list of {label, amount}.", {}
        if quote_ref is not None and not (isinstance(quote_ref, str) and 0 < len(quote_ref) <= MAX_QUOTE):
            return "Not asked: quote_ref must be a short string.", {}
        try:
            amounts = [_amount(x.get("amount")) for x in lines]
            stated = _amount(total)
        except NotANumber as e:
            return f"Not asked: {e}.", {}
        if any(not str(x.get("label") or "").strip() for x in lines):
            return "Not asked: every item needs a label.", {}
        if any(len(str(x.get("label"))) > MAX_LABEL for x in lines):
            return f"Not asked: a label is at most {MAX_LABEL} characters.", {}
        if any(a <= 0 for a in amounts) or stated <= 0:
            return "Not asked: amounts must be above zero.", {}
        right = total_of([x["amount"] for x in lines])
        if stated != right:
            return (f"Not asked, the resident has seen nothing: the total {total} is not the sum of the items "
                    f"({_shown(right)}). Add them with calc_sum and give that total."), {}
        if not cites:
            return "Not asked: cite the evidence that states the amounts (cites).", {}
        sources, trusted, bad = self._sources(await self._view(), cites)
        if bad:
            return f"Not asked: cannot cite {', '.join(bad)}.", {}
        rules = await self._rules(wf)
        shown = {"summary": summary, "items": [{"label": str(x["label"]), "amount": str(x["amount"])} for x in lines],
                 "total": str(total)}
        refused = problems(figures_text(shown), sources, rules, trusted)
        if refused:
            return ("Not asked, the resident has seen nothing: " + "; ".join(refused)
                    + ". Cite the item that states each amount, or leave it out."), {}
        if quote_ref is not None and quote_ref not in " ".join(sources):
            return (f"Not asked: the quote {quote_ref} is in none of the items you cite. Cite the item that states "
                    "the partner's quote id, or leave quote_ref out."), {}
        return None, {"text": summary, "items": shown["items"], "total": shown["total"]}

    async def call(self, summary: str = "", items: list | None = None, total: str | int = "",
                   cites: list[str] | None = None, quote_ref: str | None = None) -> ToolChunk:
        """Runs only after the resident agreed (the gate lets nothing else through): record it as evidence."""
        if (closed := await self._closed()):
            return closed
        # Our words, not the model's: the record says that the resident agreed and to what total, nothing a
        # model could phrase as "booked" or "done". It is never trusted evidence (tools._sources).
        item = await self.rt.cases.add(self.b.case_id, "evidence", self.b.agent_name, {
            "tool": self.name, "input": f"quote {quote_ref}" if quote_ref else "consent",
            "text": f"resident approved the consent request, total {str(total).strip()}"})
        return _ok(f"The resident agreed: {summary.strip()} (total {total}). [evidence {item.ref}]")


def _amount(value: object) -> Decimal:
    """A finite amount of a plausible size, or a NotANumber the model can read."""
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not _AMOUNT.match(str(value).strip()):
        raise NotANumber(f"{str(value)[:30]!r} is not an amount: write digits only, as the cited item does")
    return to_decimal(value)


def _shown(value: Decimal) -> str:
    return str(int(value)) if value == value.to_integral() else str(value.normalize())
