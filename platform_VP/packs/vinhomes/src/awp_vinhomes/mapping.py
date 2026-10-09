"""Pure functions between Vinhomes' schema_v2 wire and the core's neutral contract.

Inbound  (domain -> platform): ReceptionToSupervisorMessage -> CaseIntake / FollowUp.
Outbound (platform -> domain): CaseResult + the ticket as it is now -> SupervisorToReceptionResult.
The wire models live in vinhome_Recident/.../v3_reception_supervisor.py; this file only reads
and writes their JSON, so it has no import from the domain.

Privacy: the inbound message carries the resident's name and phone number. They are never copied
into anything a model reads. Only `resident_id` is kept, and a name or number typed into free
text is masked.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from awp.intake.models import CaseIntake, CaseResult, FollowUp, IntakeFact

SCHEMA = "2.0"
FINAL = {"resolved", "closed", "cancelled"}  # ticket statuses (HOP_DONG / backend)
# schema_v2 fact sources -> the core's words
SOURCES = {"customer_report": "reported", "staff_verified": "verified", "agent_inference": "inferred"}
FOLLOW_UP_TEXT = {
    "information_provided": "Cư dân bổ sung thông tin: {t}",
    "plan_approved": "Cư dân đã đồng ý phương án. Ghi chú của cư dân: {t}",
    "plan_rejected": "Cư dân đã từ chối phương án. Ghi chú của cư dân: {t}",
    "plan_change_requested": "Cư dân yêu cầu thay đổi phương án: {t}",
    "cancel_requested": "Cư dân yêu cầu hủy yêu cầu: {t}",
}
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){8,9}(?!\d)")


class BadMessage(ValueError):
    """An inbox message that cannot be mapped. Reading it again will not help."""


def external_ref(ticket_id: str, generation: int) -> str:
    """The core's case key. A reopened ticket (generation > 0) is a new case: the core keeps
    one case per external_ref, so the same ticket id would hide the second round."""
    return str(ticket_id) if not generation else f"{ticket_id}#g{generation}"


def _need(msg: dict, *path: str):
    cur = msg
    try:
        for p in path:
            cur = cur[p]
    except (KeyError, TypeError) as e:
        raise BadMessage(f"missing {'.'.join(path)}") from e
    return cur


def _mask(text: str, msg: dict) -> str:
    """Remove the resident's own name and phone number from free text."""
    who = msg.get("resident") or {}
    name, phone = (who.get("resident_name") or "").strip(), (who.get("phone_number") or "").strip()
    if name:
        text = re.sub(re.escape(name), "[tên cư dân]", text, flags=re.IGNORECASE)
    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits:
            text = re.sub(r"\+?" + r"[ .-]?".join(digits), "[số điện thoại]", text)
    return _PHONE.sub("[số điện thoại]", text)


def _attributes(msg: dict) -> dict:
    req, loc = _need(msg, "request"), _need(msg, "location")
    return {
        "ticket_id": str(_need(msg, "ticket_id")), "ticket_code": _need(msg, "ticket_code"),
        "ticket_generation": int(_need(msg, "ticket_generation")),
        "ticket_version": str(_need(msg, "ticket_version")),
        "tenant_id": str(_need(msg, "tenant_id")), "workspace_id": str(_need(msg, "workspace_id")),
        "team_id": str(_need(msg, "team_id")), "correlation_id": _need(msg, "correlation_id"),
        "is_emergency": bool(req.get("is_emergency")), "category_id": req.get("category_id"),
        "request_kind": req.get("request_kind"), "severity": req.get("severity"),
        "handoff_reason": req.get("handoff_reason"),
        "location": {k: str(loc[k]) for k in
                     ("unit_id", "unit_number", "building_id", "building_code", "building_name") if k in loc},
    }


# ---- domain -> platform ------------------------------------------------------
def intake_from_message(msg: dict) -> CaseIntake:
    """A `ticket_submitted` message as a new case."""
    if msg.get("message_type") != "ticket_submitted":
        raise BadMessage(f"not a ticket_submitted message: {msg.get('message_type')}")
    attrs = _attributes(msg)
    req = _need(msg, "request")
    facts = [
        IntakeFact(key=str(f["key"]), value="" if f.get("value") is None else _mask(str(f["value"]), msg),
                   source=SOURCES.get(f.get("source"), "reported"))
        for f in msg.get("facts") or []]
    loc = attrs["location"]
    # Where the work is: the system's own record of the ticket, so it counts as verified.
    for key, label in (("building_name", "tòa nhà"), ("unit_number", "căn hộ")):
        if loc.get(key):
            facts.append(IntakeFact(key=label, value=loc[key], source="verified"))
    # What Reception concluded about the request: its own assessment, not a measurement.
    for key, label in (("severity", "mức độ"), ("request_kind", "loại yêu cầu")):
        if attrs.get(key):
            facts.append(IntakeFact(key=label, value=str(attrs[key]), source="inferred"))
    if attrs["is_emergency"]:
        facts.append(IntakeFact(key="khẩn cấp", value="có", source="inferred"))
    return CaseIntake(
        message_id=_need(msg, "message_id"),
        external_ref=external_ref(attrs["ticket_id"], attrs["ticket_generation"]),
        summary=_mask(_need(msg, "request", "title"), msg),
        description=_mask(req.get("description", ""), msg),
        facts=facts, requester_ref=str(_need(msg, "resident", "resident_id")),
        priority=req.get("priority") or "normal", attributes=attrs)


def follow_up_from_message(msg: dict) -> tuple[str, FollowUp]:
    """Any other message as (external_ref of its case, follow-up)."""
    kind = msg.get("message_type")
    if kind not in FOLLOW_UP_TEXT:
        raise BadMessage(f"unknown message_type: {kind}")
    attrs = _attributes(msg)
    text = FOLLOW_UP_TEXT[kind].format(t=_mask(msg.get("message", ""), msg)).strip()
    ref = external_ref(attrs["ticket_id"], attrs["ticket_generation"])
    return ref, FollowUp(message_id=_need(msg, "message_id"), kind=kind, text=text,
                         attributes={"ticket_version": attrs["ticket_version"],
                                     "source_message_id": msg.get("source_message_id")})


# ---- platform -> domain ------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wire(attrs: dict, *, version: str, generation: int, mtype: str, message: str,
          run_id: str, sent_at: str | None, result: dict | None = None, error: dict | None = None) -> dict:
    message = (message or "").strip()[:10000] or "Đã cập nhật hồ sơ."
    # Same content -> same id (the domain replays it); a new ticket version or wording -> a new id.
    fingerprint = hashlib.sha256(f"{mtype}|{version}|{message}|{(error or {}).get('code', '')}".encode()).hexdigest()[:12]
    body = {
        "schema_version": SCHEMA, "message_id": f"awp-{run_id}-{mtype}-{fingerprint}",
        "correlation_id": attrs["correlation_id"], "sent_at": sent_at or _now(),
        "message_type": mtype, "message": message,
        "tenant_id": attrs["tenant_id"], "workspace_id": attrs["workspace_id"], "team_id": attrs["team_id"],
        "ticket_id": attrs["ticket_id"], "ticket_code": attrs["ticket_code"],
        "ticket_generation": generation, "ticket_version": version, "supervisor_run_id": run_id,
    }
    if result is not None:
        body["result"] = result
    if error is not None:
        body["error"] = error
    return body


def accepted_message(msg: dict, sent_at: str | None = None) -> dict:
    """Receipt for a new ticket, built from the inbox message itself."""
    attrs = _attributes(msg)
    return _wire(attrs, version=attrs["ticket_version"], generation=attrs["ticket_generation"],
                 mtype="accepted", message="Hồ sơ đã được hệ thống xử lý tự động tiếp nhận.",
                 run_id="intake-" + hashlib.sha256(msg["message_id"].encode()).hexdigest()[:16], sent_at=sent_at)


def result_message(attrs: dict, result: CaseResult, current: dict, sent_at: str | None = None) -> dict:
    """The body for POST /cases/{ticket_id}/results.

    `current` is GET /cases/{ticket_id} read just now: the domain refuses a result that names an
    older ticket version (409), so the version always comes from there, never from the intake.

    How the core's outcome becomes a message_type:
      * ticket already cancelled          -> cancelled (the domain accepts it only then)
      * resolved, ticket resolved/closed   -> completed (the domain checks work orders itself)
      * resolved, ticket still open        -> in_progress: the platform answered or proposed a plan,
                                              but only the domain's own staff close a ticket
      * needs_human / cannot_resolve       -> failed, not retryable: a person takes over
      * failed (platform error)            -> failed, retryable
    """
    ticket = current["ticket"]
    status, version = ticket["status"], str(ticket["version"])
    generation = int(current["ticket_generation"])
    answer = (result.answer or "").strip()
    kw = dict(attrs=attrs, version=version, generation=generation, run_id=result.case_id, sent_at=sent_at)
    unknown = "; ".join(result.unknowns)[:1900]

    if status == "cancelled":
        return _wire(mtype="cancelled", message="Yêu cầu đã được hủy.", **kw)
    if result.outcome == "resolved":
        if status in FINAL:
            data = {"outcome": "work_completed", "summary": answer[:5000] or "Hồ sơ đã hoàn tất.",
                    "work_order_ids": [], "evidence_ids": []}
            return _wire(mtype="completed", message=answer, result=data, **kw)
        return _wire(mtype="in_progress", message=answer, **kw)
    if result.outcome == "needs_human":
        code, review = "NEEDS_HUMAN_REVIEW", "needs_human_review"
        message = answer or "Hồ sơ cần nhân viên Ban quản lý xem xét."
        error = {"code": code, "retryable": False, "message": unknown or message[:1900]}
    elif result.outcome == "cannot_resolve":
        code, review = "CANNOT_RESOLVE", "unable_to_resolve"
        message = answer or "Hệ thống tự động chưa giải quyết được hồ sơ này."
        error = {"code": code, "retryable": False, "message": unknown or message[:1900]}
    else:  # the platform itself failed (budget, model, crash)
        message = answer or "Hệ thống tự động gặp sự cố; Ban quản lý sẽ xử lý hồ sơ này."
        error = {"code": "PLATFORM_ERROR", "retryable": True, "message": unknown or "platform error"}
        return _wire(mtype="failed", message=message, error=error, **kw)
    data = {"outcome": review, "summary": message[:5000], "work_order_ids": [], "evidence_ids": []}
    return _wire(mtype="failed", message=message, error=error, result=data, **kw)
