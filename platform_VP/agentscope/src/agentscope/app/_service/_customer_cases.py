"""Customer Leader consumer of C05/C07. No partner routing or ticket grants."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from ..vin_platform import enabled
from ..vin_platform._contracts import PlatformError, ServiceRequest
from ..vin_platform._domain import DomainAdapter


async def customer_scope(storage, user_id, agent_id, session_id):
    """Resolve identity on the server and recheck ownership for every operation."""
    if not enabled():
        raise PlatformError("VIN_PLATFORM_DISABLED", 503)
    authority = getattr(storage, "vin_platform_service", None)
    if authority is None:
        raise PlatformError("RESOURCE_AUTHORITY_UNAVAILABLE", 503)
    context = await authority.context(user_id)
    if context.role != "VIN_USER" or context.workspace_id != "personal:" + user_id:
        raise PlatformError("PERSONAL_WORKSPACE_REQUIRED", 403)
    agent = await storage.get_agent(user_id, agent_id)
    session = await storage.get_session(user_id, agent_id, session_id)
    if agent is None or agent.user_id != user_id or agent.data.system_role != "leader" or session is None:
        raise PlatformError("CUSTOMER_LEADER_NOT_FOUND", 404)
    return authority, context


def _binding_key(context, agent_id, session_id, command):
    fingerprint = hashlib.sha256(json.dumps(command, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return str(uuid5(NAMESPACE_URL, ":".join(("customer-case", context.tenant_id,
        context.initiator_user_id, agent_id, session_id, fingerprint))))


async def create_request(storage, user_id, agent_id, session_id, *, link_id, apartment_id,
                         description, location, category_id=None):
    authority, context = await customer_scope(storage, user_id, agent_id, session_id)
    adapter = DomainAdapter(authority)
    command = {"link_id": link_id, "request": {"apartmentId": apartment_id, "description": description,
        "location": {"description": location}, "photoIds": []}}
    key = _binding_key(context, agent_id, session_id, command)
    data = {"type": "customer-case", "agent_id": agent_id, "session_id": session_id, "command": command}
    try:
        revision = await authority.automation_put(context, key, "derived", data)
    except PlatformError as exc:
        if exc.code != "REVISION_CONFLICT":
            raise
        existing = next(row for row in await authority.automation_list(context, "derived") if row["id"] == key)
        data, revision = existing["data"], existing["revision"]
    # The command is durably bound before IO. Retry after a crash reuses C05's
    # idempotency key even if the reply never reached the Leader/session.
    case = await adapter.create_case(context, ServiceRequest(**command, idempotency_key=key))
    if not data.get("case_id"):
        try:
            await authority.automation_put(context, key, "derived", {**data, "case_id": case["id"]}, revision)
        except PlatformError as exc:
            if exc.code != "REVISION_CONFLICT":
                raise
    if category_id:
        binding = next(row for row in await authority.automation_list(context, "derived") if row["id"] == key)
        ticket = binding["data"].get("ticket_command")
        if ticket is None:
            snapshot = await adapter.get_case(context, case["id"], refresh=True)
            ticket = {"category_id": category_id, "expected_version": snapshot["data"]["domain"]["canonical_version"]}
            await authority.automation_put(context, key, "derived", {**binding["data"], "ticket_command": ticket}, binding["revision"])
        elif ticket["category_id"] != category_id:
            raise PlatformError("IDEMPOTENCY_CONFLICT", 409)
        await adapter.materialize(context, case["id"], **ticket, idempotency_key=key + ":ticket")
    return await progress(authority, context, case["id"])


async def session_cases(storage, user_id, agent_id, session_id):
    authority, context = await customer_scope(storage, user_id, agent_id, session_id)
    rows = await authority.automation_list(context, "derived")
    items = []
    for row in rows:
        data = row["data"]
        if (data.get("type"), data.get("agent_id"), data.get("session_id")) != ("customer-case", agent_id, session_id):
            continue
        if not data.get("case_id"):
            items.append({"id": row["id"], "sync_status": "outcome_unknown", "next_action": "retry_original_request",
                "as_of": None, "events": [], "actions": []})
            continue
        try:
            items.append(await progress(authority, context, data["case_id"]))
        except PlatformError as exc:
            # Keep each case visible during outages/revocation without showing
            # a cached snapshot as current or dropping the other cases.
            items.append({"id": data["case_id"], "sync_status": "unavailable", "error": exc.code,
                "next_action": "reconnect_domain" if exc.status == 403 else "retry_sync",
                "as_of": None, "events": [], "actions": []})
    return {"items": items}


async def linked_context(storage, user_id, agent_id, session_id):
    authority, context = await customer_scope(storage, user_id, agent_id, session_id)
    # Consume C04's owner-scoped public reader; no consumer SQL or credentials.
    from ..vin_platform._router import link_list
    links = await link_list(who=(authority, context))
    items = []
    for link in links["items"]:
        if link["status"] == "active":
            profile = await DomainAdapter(authority).request(context, link["id"], "GET", "/me")
            items.append({"link_id": link["id"], "apartments": profile.get("apartments", []),
                "service_categories": profile.get("service_categories", [])})
    return {"items": items}


def decision_actions(domain):
    """Build reviewable choices from the canonical projection, never model text."""
    actions = []
    version = domain.get("canonical_version")
    permissions = domain.get("permissions", {})
    revision = domain.get("resolutionRevision")
    for plan in domain.get("plans", []):
        if plan.get("canDecide") is True and plan.get("status") == "resident_pending" and type(plan.get("version")) is int:
            for decision, label in (("approve", "Đồng ý phương án"), ("reject", "Từ chối phương án")):
                actions.append({"action": "plan-decision", "label": label + ": " + plan["title"], "requires_note": True,
                    "payload": {"plan_id": plan["id"], "expectedVersion": plan["version"], "decision": decision}})
    if version and revision:
        if permissions.get("canConfirm"):
            actions.append({"action": "confirm", "label": "Xác nhận hoàn tất", "payload": {"resolutionRevision": revision}})
        if permissions.get("canRequestRework"):
            actions.append({"action": "reopen", "label": "Yêu cầu làm lại", "payload": {"resolutionRevision": revision}, "requires_note": True})
    # C07 supplies the exact version expected by Domain approval decisions
    # (its ticket version). Never substitute the outer case version.
    for item in domain.get("pending_decisions", []):
        if item.get("status") == "pending" and isinstance(item.get("version"), int):
            for approved, label in ((True, "Đồng ý"), (False, "Từ chối")):
                actions.append({"action": "work-approval", "label": label, "requires_note": True,
                    "payload": {"approval_id": item["id"], "version": item["version"], "approved": approved}})
    for action in actions:
        action["expected_version"] = version
    return actions


async def progress(authority, context, case_id):
    from ..vin_platform._router import case_events
    adapter = DomainAdapter(authority)
    case = await adapter.get_case(context, case_id, refresh=True)
    domain = case["data"]["domain"]
    page = await case_events(case_id, after=0, limit=100, sync=True, who=(authority, context))
    current = page.get("sync_status") == "applied" and page.get("canonical_version") == domain.get("canonical_version")
    # Explicit DTO: never return authority rows, link data, grants or proofs.
    safe_fields = ("code", "title", "description", "location", "canonical_version", "service_status", "status",
        "as_of", "next_action", "pending_decisions", "plans", "work_orders", "resolution", "result_photos", "photos")
    result = {key: domain[key] for key in safe_fields if key in domain}
    result.update(id=case_id, sync_status="applied" if current else "sync_pending",
        ticket_ids=[str(item["id"]) for item in domain.get("tickets", []) if item.get("id")],
        as_of=domain.get("as_of"), next_action=domain.get("next_action"),
        events=[{"id": event["event_id"], "sequence": event["sequence"], "at": event["occurred_at"],
            "label": event["data"].get("label", event["event_type"]), "note": event["data"].get("note")}
            for event in page["items"]], next_cursor=page["next_cursor"], has_more=page["has_more"],
        actions=decision_actions(domain) if current else [])
    return result
