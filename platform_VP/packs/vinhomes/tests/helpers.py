"""Small builders shared by the tests."""
from awp.intake.models import CaseResult
from awp_vinhomes import mapping
from fake_vinhomes import TEAM, TICKET, submitted

ATTRS = mapping.intake_from_message(submitted()).attributes


def current(status="open", version=7, generation=0):
    """What GET /cases/{ticket_id} returns, reduced to what the mapping reads."""
    return {"case_id": TEAM, "status": "open", "ticket_generation": generation,
            "ticket": {"code": "VH-0001", "status": status, "version": version}}


def result(outcome="resolved", answer="Đã gửi phương án tới Ban quản lý.", unknowns=()):
    return CaseResult(case_id="case_abc", external_ref=TICKET, outcome=outcome, answer=answer, unknowns=list(unknowns))
