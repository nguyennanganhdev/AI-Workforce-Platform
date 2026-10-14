"""The worker of the platform bridge (docs/domain/NOI_WORKFORCE_V1.md section 5.2).

    python -m vinhomes_api.platform_sync        (reads DATABASE_URL and VINHOMES_API_PLATFORM_*; runs until stopped)

Four steps, each safe to run twice and by two workers at once:
  1. send the commands the API queued (start, reply, approval decision, close), oldest first per ticket, and
     queue the close of a linked ticket that people ended in their own screens;
  2. read each open conversation's events and write them into the resident's chat and the link; a link is closed
     here, when the log of its closed workflow was read to the end;
  3. turn new ticket events of linked tickets into progress events;
  4. send those, signed, follow their receipts and render quote controls after Platform applies the event.
It uses the API's restricted database role and scopes every transaction to one tenant, as jobs.py does.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .platform import (ACTIVE, PROGRESS, RETRY_CODES, SILENT_TEXT, STOP_TRACKING, TENANT, TIMEZONE, Bridge, Platform,
                       PlatformError, apply_event, apply_result, apply_snapshot, event_body, fail_link, post_chat,
                       provider_events, quote_card, retryable)

log = logging.getLogger("vinhomes_api.platform_sync")
EVERY_SECONDS = 1.0
# The platform allows a key 600 calls a minute; every open conversation is read once a pass. Past this many
# conversations a pass waits longer, so the reads stay well under the limit and leave room for commands.
READS_PER_SECOND = 6
# A command waits for the coordinator's turn (up to the route's wait_seconds) on its own connection:
# no more than this many at once, so reading events never waits for one.
MAX_SENDING = 8
# Alert after repeated refusals; a completion never silently becomes "stop tracking".
CLOSE_TRIES = 5
# Receipts the platform has not finished with.
WAITING = "('accepted','processing','quarantined')"
_sending: dict[str, asyncio.Task] = {}  # ticket id -> its command on the wire, in this process
_run_tenant: ContextVar[str | None] = ContextVar('platform_sync_tenant', default=None)


async def _tenants(engine: AsyncEngine) -> list[str]:
    if _run_tenant.get() is not None:
        return [_run_tenant.get()]
    async with engine.connect() as probe:
        return [str(row[0]) for row in await probe.execute(text("select id from tenants where status='active'"))]


@asynccontextmanager
async def _scoped(engine: AsyncEngine, tenant: str):
    async with engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:t,true)"), {"t": tenant})
        yield db


def _backoff(cap: int) -> str:
    # 1, 2, 4 ... seconds up to `cap`, by the attempts already made.
    return f"now()+make_interval(secs => least(power(2,least(attempts,10)),{cap}))"


# ---- 1. commands ---------------------------------------------------------------------------------------------------

async def _deliver(client: Platform, link, command) -> dict:
    kind, body = command["kind"], command["body"]
    # The same ids on every attempt: the platform answers a repeated external_request_id with the first result.
    base = {"schema_version": "1", "external_request_id": str(command["id"]), "external_user_id": link["user_id"],
            "external_ticket_id": str(link["ticket_id"]),
            "external_conversation_id": f"{link['channel_id']}:{link['ticket_id']}"}
    if kind == "approval_decision":
        return await client.decide(body["approval_id"], {
            **base, "workflow_id": link["workflow_id"], "decision": body["decision"], "expected_revision": body["sent_revision"],
            "arguments_hash": body["arguments_hash"], **({"quote_ref": body["quote_ref"]} if body.get("quote_ref") else {})})
    if kind == "close":
        return await client.close(link["workflow_id"], {
            **base, "expected_revision": body["sent_revision"], "reason": body["reason"],
            **({"stop_tracking_only": True} if body.get("stop_tracking_only") else {})})
    return await client.request({
        **base, "command_type": kind, "external_management_ref": link["management_ref"], "timezone": TIMEZONE,
        "message": {"type": "text", "text": body["text"]},
        **({"workflow_id": link["workflow_id"]} if kind == "workflow_reply" else {})})


async def _send(engine: AsyncEngine, client: Platform, tenant: str, ticket: str) -> None:
    async with _scoped(engine, tenant) as db:
        # One sender per ticket, here or in another worker: commands of a ticket reach the platform in order.
        free = await db.execute(text("select pg_try_advisory_xact_lock(hashtextextended(:key,0))"), {"key": "platform-command:" + ticket})
        if not free.scalar_one():
            return
        # Oldest first, but an approval decision goes ahead: a reply the platform holds back until the approval
        # is decided must not keep the decision waiting behind it.
        command = (await db.execute(text(f"""
            select id,kind,body,attempts,next_attempt_at<=now() as due from platform_commands
            where ticket_id=:ticket and tenant_id={TENANT} and status='pending'
            order by (kind='approval_decision') desc,created_at,id limit 1
        """), {"ticket": ticket})).mappings().first()
        if command is None or not command["due"]:
            return
        link = (await db.execute(text(f"select * from platform_links where ticket_id=:ticket and tenant_id={TENANT}"),
                                 {"ticket": ticket})).mappings().one()
        done = "update platform_commands set status='done',attempts=attempts+1,last_error=null,result=cast(:result as jsonb) where id=:id"
        ended = link["status"] == "closed" or link["state"] == "closed"
        if ended or link["status"] == "failed":
            # Nothing to tell a workflow that ended; a close of a closed one is done.
            if command["kind"] == "close" and ended:
                await db.execute(text(done), {"id": command["id"], "result": "null"})
            else:
                await fail_link(db, link, "closed" if ended else "failed")
            return
        body = command["body"]
        if command["kind"] in ("approval_decision", "close") and "sent_revision" not in body:
            # The revision the resident's answer was given at, or where the workflow is known to stand since. Fixed
            # before the first try, in a transaction of its own so that it outlives a crash here: the platform
            # takes the same request id with another revision for another request.
            body = {**body, "sent_revision": max(body.get("expected_revision") or 0, link["revision"] or 0)}
            async with _scoped(engine, tenant) as kept:
                await kept.execute(text("update platform_commands set body=cast(:body as jsonb) where id=:id"),
                                   {"id": command["id"], "body": json.dumps(body, ensure_ascii=False)})
        try:
            answer = await _deliver(client, link, {**command, "body": body})
        except (httpx.HTTPError, PlatformError) as exc:
            code = exc.code if isinstance(exc, PlatformError) else type(exc).__name__
            error = str(exc) if isinstance(exc, PlatformError) else code
            if retryable(exc):
                if code == "REVISION_CONFLICT" and isinstance(exc.details.get("current_revision"), int):
                    await db.execute(text(f"update platform_links set revision=greatest(coalesce(revision,0),:now) where ticket_id=:ticket and tenant_id={TENANT}"),
                                     {"now": exc.details["current_revision"], "ticket": ticket})
                if code in RETRY_CODES:
                    # The platform itself said no, so nothing was applied: the next try may carry the newer revision.
                    body = {key: value for key, value in body.items() if key != "sent_revision"}
                if code == "WORKFLOW_NOT_READY_TO_CLOSE" and command["attempts"] + 1 >= CLOSE_TRIES:
                    log.warning("Platform still tracks work for ticket %s; completion close remains pending", ticket)
                await db.execute(text(f"""
                    update platform_commands set attempts=attempts+1,last_error=:error,next_attempt_at={_backoff(30)},
                      body=cast(:body as jsonb) where id=:id
                """), {"id": command["id"], "error": error, "body": json.dumps(body, ensure_ascii=False)})
                return
            if code == "WORKFLOW_CLOSED":
                # It ended on the platform's side. The link stays open until the reader has the rest of its log.
                await db.execute(text(f"update platform_links set state='closed',next_action='none' where ticket_id=:ticket and tenant_id={TENANT}"),
                                 {"ticket": ticket})
                if command["kind"] == "close":
                    await db.execute(text(done), {"id": command["id"], "result": "null"})
                    return
            log.warning("Platform refused %s of ticket %s: %s", command["kind"], ticket, code)
            await db.execute(text("update platform_commands set status='failed',attempts=attempts+1,last_error=:error where id=:id"),
                             {"id": command["id"], "error": error})
            if command["kind"] == "approval_decision" and code in ("APPROVAL_NOT_PENDING", "APPROVAL_EXPIRED"):
                # Only this answer came too late. The workflow goes on and its events say how the approval ended.
                await db.execute(text(f"update platform_approvals set status='expired' where approval_id=:id and tenant_id={TENANT}"),
                                 {"id": command["body"]["approval_id"]})
                return
            await fail_link(db, link, "closed" if code == "WORKFLOW_CLOSED" else "failed")
            return
        if answer.get("request_status") in ("failed", "blocked"):
            # Accepted, but the coordinator's turn failed for good or the route was taken away: nobody answers
            # this request any more. People take over and the resident is told so.
            error = (answer.get("error") or {}).get("code") or answer["request_status"]
            await db.execute(text("update platform_commands set status='failed',attempts=attempts+1,last_error=:error,result=cast(:result as jsonb) where id=:id"),
                             {"id": command["id"], "error": error, "result": json.dumps(answer, ensure_ascii=False)})
            await apply_result(db, link, answer)
            await fail_link(db, link)
            return
        await db.execute(text(done), {"id": command["id"], "result": json.dumps(answer, ensure_ascii=False)})
        await apply_result(db, link, answer)
        if command["kind"] == "workflow_reply" and not body.get("own") and answer.get("request_status") == "completed" \
                and not (answer.get("result") or {}).get("messages") and answer.get("workflow_state") != "awaiting_approval":
            # The platform lets the coordinator end a turn without a word while work is pending. The resident
            # wrote and must not be left with silence: one honest line (an approval card is an answer of its own).
            await post_chat(db, link, f"silent:{command['id']}", {"text": SILENT_TEXT})


async def _send_logged(engine: AsyncEngine, client: Platform, tenant: str, ticket: str) -> None:
    try:
        await _send(engine, client, tenant, ticket)
    except Exception:  # noqa: BLE001 - the command stays pending and the next pass takes it again
        log.exception("Could not send the command of ticket %s", ticket)
    finally:
        _sending.pop(ticket, None)


async def send_commands(engine: AsyncEngine, client: Platform, wait: bool = True) -> None:
    """Start sending the due command of every ticket that has one. `wait=False`: return while they are on the wire."""
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            due = [str(row[0]) for row in await db.execute(text(f"""
                select distinct ticket_id from platform_commands
                where tenant_id={TENANT} and status='pending' and next_attempt_at<=now()
            """))]
        for ticket in due:
            if ticket not in _sending and len(_sending) < MAX_SENDING:
                _sending[ticket] = asyncio.create_task(_send_logged(engine, client, tenant, ticket))
    if wait and _sending:
        await asyncio.gather(*list(_sending.values()))


# ---- 2. events -----------------------------------------------------------------------------------------------------

async def refresh_request_results(db, client: Platform, link) -> None:
    """202 is accepted, not finished. Persist the final outcome for turn UI/metrics."""
    commands = (await db.execute(text(f"""
        select id,result->>'request_id' as request_id from platform_commands
        where ticket_id=:ticket and tenant_id={TENANT} and status='done'
          and result->>'request_id' is not null
          and result->>'request_status' in ('accepted','running','deferred')
          and next_attempt_at<=now() order by created_at,id for update skip locked
    """), {"ticket": link["ticket_id"]})).mappings().all()
    for command in commands:
        try:
            answer = await client.result(command["request_id"], link["user_id"])
        except (httpx.HTTPError, PlatformError):
            await db.execute(text("update platform_commands set next_attempt_at=now()+interval '30 seconds' where id=:id"), {"id":command["id"]})
            continue
        await db.execute(text("""update platform_commands set result=cast(:result as jsonb),
            next_attempt_at=now()+interval '3 seconds' where id=:id"""),
            {"id":command["id"],"result":json.dumps(answer,ensure_ascii=False)})
        # The event log supplies the same messages; post_chat deduplicates them.
        await apply_result(db, link, answer)


async def _read(engine: AsyncEngine, client: Platform, tenant: str, ticket: str) -> None:
    async with _scoped(engine, tenant) as db:
        # Whoever holds the link applies its events; a second worker skips it this pass. Not a full row lock:
        # the resident's next message queues a command for this link and must not wait for the platform's answer.
        link = (await db.execute(text(f"""
            select * from platform_links where ticket_id=:ticket and tenant_id={TENANT} and status='open'
              and conversation_id is not null for no key update skip locked
        """), {"ticket": ticket})).mappings().first()
        if link is None:
            return
        await refresh_request_results(db, client, link)
        cursor = link["cursor"]
        while True:
            try:
                page = await client.history(link["conversation_id"], link["user_id"], cursor)
            except PlatformError as exc:
                if exc.code != "EVENT_CURSOR_EXPIRED":
                    raise
                # The log before the cursor was purged: the snapshot holds what the events would have said.
                cursor = await apply_snapshot(db, link, await client.snapshot(link["conversation_id"], link["user_id"]))
                break
            for event in page["items"]:
                await apply_event(db, link, event)
            cursor = page["next_cursor"]
            if not page["has_more"]:
                break
        if cursor != link["cursor"] or link["state"] == "closed":
            # The log was read to its end. If it is the log of a workflow that closed, nothing more will come: only
            # now is the link finished, so what was logged up to the close (the coordinator's last line) is in the chat.
            await db.execute(text(f"""
                update platform_links set cursor=:cursor,status=case when state='closed' then 'closed' else status end
                where ticket_id=:ticket and tenant_id={TENANT}
            """), {"cursor": cursor, "ticket": ticket})


async def read_events(engine: AsyncEngine, client: Platform) -> int:
    """Returns how many conversations were read."""
    read = 0
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            tickets = [str(row[0]) for row in await db.execute(text(
                f"select ticket_id from platform_links where tenant_id={TENANT} and status='open' order by updated_at"))]
        read += len(tickets)
        for ticket in tickets:
            try:
                await _read(engine, client, tenant, ticket)
            except (httpx.HTTPError, PlatformError) as exc:
                log.warning("Could not read the platform events of ticket %s: %s", ticket,
                            exc.code if isinstance(exc, PlatformError) else type(exc).__name__)
            except Exception:  # noqa: BLE001 - one conversation that cannot be applied must not stop the others
                log.exception("Could not apply the platform events of ticket %s", ticket)
    return read


# ---- 3 and 4. staff progress ---------------------------------------------------------------------------------------

async def _context(db, event) -> dict:
    """What provider_events needs to know about one ticket event."""
    payload = event["payload"] or {}
    work, quote, result = payload.get("workOrderId"), None, None
    if event["event_type"] == "ticket.resolution_published":
        # About the ticket, not one job: it reports the finished job the platform dispatched and was not yet told of.
        result = (await db.execute(text(f"""
            select w.id as work_order_id,
              (select count(*) from evidence_items e where e.work_order_id=w.id and e.tenant_id=w.tenant_id and e.status='active'
                 and e.purpose in ('after','verification')) as photo_count,
              q.reported_by,q.note
            from work_orders w join platform_operations po on po.work_order_id=w.id and po.tenant_id=w.tenant_id
            left join lateral (select case when x.criteria->0->>'name'='acceptance_report' then x.note end as note,
                (select u.name from users u where u.id=x.checked_by and x.criteria->0->>'name'='acceptance_report') as reported_by
              from vh_qc_results x where x.work_order_id=w.id and x.tenant_id=w.tenant_id order by x.checked_at desc,x.id desc limit 1) q on true
            where w.ticket_id=:ticket and w.tenant_id={TENANT} and w.status='completed' and w.completed_at<=:at
              and not exists (select 1 from platform_outbox o where o.client_reference=po.client_reference
                and o.tenant_id=po.tenant_id and o.event_type='job.result_published')
            order by w.completed_at desc,w.id desc limit 1
        """), {"ticket": event["ticket_id"], "at": event["occurred_at"]})).mappings().first()
        work = result and result["work_order_id"]
    if payload.get("approvalId") or event["event_type"] == "work_order.repair_proposed":
        # A proposal event names only its work order: its quote is the newest one written by then.
        quote = (await db.execute(text(f"""
            select id,work_order_id,kind,request_detail as detail,expires_at from work_approvals
            where tenant_id={TENANT} and (id=cast(:approval as uuid) or (cast(:approval as uuid) is null
              and work_order_id=cast(:work as uuid) and kind='customer_repair' and created_at<=:at))
            order by created_at desc,id desc limit 1
        """), {"approval": payload.get("approvalId"), "work": work, "at": event["occurred_at"]})).mappings().first()
        work = work or (quote and quote["work_order_id"])
    # The assignment the event names, else whoever holds the work.
    staff = (await db.execute(text(f"""
        select a.work_order_id,a.eta_at,u.name from work_assignments a
        join staff_profiles sp on sp.id=a.staff_id and sp.tenant_id=a.tenant_id join users u on u.id=sp.user_id
        where a.tenant_id={TENANT} and (a.id=cast(:assignment as uuid) or (cast(:assignment as uuid) is null
          and a.work_order_id=cast(:work as uuid) and a.status in ('accepted','completed')))
        order by a.created_at desc,a.id desc limit 1
    """), {"assignment": payload.get("assignmentId"), "work": work and str(work)})).mappings().first()
    operations = await db.execute(text(f"""
        select work_order_id,client_reference from platform_operations
        where ticket_id=:ticket and tenant_id={TENANT} and work_order_id is not null
    """), {"ticket": event["ticket_id"]})
    return {"work_order_id": work or (staff and staff["work_order_id"]),
            "operations": {str(row[0]): row[1] for row in operations},
            "staff_name": staff and staff["name"], "eta_at": staff and staff["eta_at"],
            "quote": dict(quote) if quote else None, "result": dict(result) if result else None}


async def queue_progress(engine: AsyncEngine) -> None:
    """Step 3. A ticket's events are numbered and written under its lock, so the highest number already queued
    marks how far the ticket was read; an event that maps to nothing is read again until a later one is queued."""
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            events = (await db.execute(text(f"""
                select e.id,e.ticket_id,e.seq,e.event_type,e.payload,e.occurred_at,l.channel_id from ticket_events e
                join platform_links l on l.ticket_id=e.ticket_id and l.tenant_id=e.tenant_id
                where e.tenant_id={TENANT} and l.status='open' and e.event_type=any(:types)
                  and e.seq>coalesce((select max(o.provider_version) from platform_outbox o
                    where o.ticket_id=e.ticket_id and o.tenant_id=e.tenant_id),0)
                order by e.ticket_id,e.seq
            """), {"types": list(PROGRESS)})).mappings().all()
            for event in events:
                context = await _context(db, event)
                item = provider_events(dict(event), context)
                if item is not None:
                    await db.execute(text(f"""
                        insert into platform_outbox(event_id,tenant_id,ticket_id,client_reference,external_job_id,event_type,
                          provider_version,occurred_at,data)
                        values (:id,{TENANT},:ticket,:reference,:job,:type,:version,:at,cast(:data as jsonb))
                        on conflict (event_id) do nothing
                    """), {"id": event["id"], "ticket": event["ticket_id"], "reference": item["client_reference"],
                           "job": item["external_job_id"], "type": item["event_type"], "version": event["seq"],
                           "at": event["occurred_at"], "data": json.dumps(item["data"], ensure_ascii=False)})


async def close_ended(engine: AsyncEngine) -> None:
    """A linked ticket that people closed or cancelled in their own screens: its workflow is told to end, whatever
    work the platform still tracks for it. The resident's own confirmation and the cancel tool queue their close
    themselves, in their transaction; this finds every other way a ticket ends."""
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            await db.execute(text(f"""
                insert into platform_commands(tenant_id,ticket_id,kind,body)
                select l.tenant_id,l.ticket_id,'close',cast(:body as jsonb) from platform_links l
                join tickets t on t.id=l.ticket_id and t.tenant_id=l.tenant_id
                where l.tenant_id={TENANT} and l.status in {ACTIVE} and t.status in ('closed','cancelled')
                  and not exists (select 1 from platform_commands c where c.ticket_id=l.ticket_id
                    and c.tenant_id=l.tenant_id and c.kind='close')
            """), {"body": json.dumps(STOP_TRACKING)})


async def _send_ticket_progress(engine: AsyncEngine, client: Platform, tenant: str, ticket: str) -> None:
    async with _scoped(engine, tenant) as db:
        # One sender per ticket, here or in another worker: a later event must not overtake an earlier one
        # that someone else is still sending.
        free = await db.execute(text("select pg_try_advisory_xact_lock(hashtextextended(:key,0))"), {"key": "platform-progress:" + ticket})
        if not free.scalar_one():
            return
        rows = (await db.execute(text(f"""
            select *,next_attempt_at<=now() as due from platform_outbox
            where ticket_id=:ticket and tenant_id={TENANT} and status='pending' order by provider_version,event_id
        """), {"ticket": ticket})).mappings().all()
        for row in rows:
            if not row["due"]:
                return
            try:
                receipt = await client.job_event(event_body(row))
            except (httpx.HTTPError, PlatformError) as exc:
                code = exc.code if isinstance(exc, PlatformError) else type(exc).__name__
                if retryable(exc):
                    await db.execute(text(f"update platform_outbox set attempts=attempts+1,next_attempt_at={_backoff(60)} where event_id=:id"),
                                     {"id": row["event_id"]})
                    return
                log.warning("Platform refused progress event %s (%s): %s", row["event_id"], row["event_type"], code)
                await db.execute(text("update platform_outbox set status='rejected',attempts=attempts+1,receipt=cast(:receipt as jsonb) where event_id=:id"),
                                 {"id": row["event_id"], "receipt": json.dumps({"error": code, "message": str(exc)})})
                continue
            await db.execute(text("update platform_outbox set status='sent',attempts=0,next_attempt_at=now(),receipt=cast(:receipt as jsonb) where event_id=:id"),
                             {"id": row["event_id"], "receipt": json.dumps(receipt)})


async def send_progress(engine: AsyncEngine, client: Platform) -> None:
    """Step 4. In order per ticket: the platform drops an event older than one it already applied."""
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            tickets = [str(row[0]) for row in await db.execute(text(
                f"select distinct ticket_id from platform_outbox where tenant_id={TENANT} and status='pending'"))]
        for ticket in tickets:
            await _send_ticket_progress(engine, client, tenant, ticket)
        async with _scoped(engine, tenant) as db:
            # Accepted is not applied: the platform may still find the event stale or matching nothing.
            waiting = (await db.execute(text(f"""
                select event_id,receipt->>'receipt_id' as receipt_id from platform_outbox
                where tenant_id={TENANT} and status='sent' and receipt->>'ingestion_status' in {WAITING} and next_attempt_at<=now()
                order by updated_at for update skip locked
            """))).mappings().all()
            for row in waiting:
                try:
                    receipt = await client.receipt(row["receipt_id"])
                except (httpx.HTTPError, PlatformError):
                    break
                await db.execute(text(f"""
                    update platform_outbox set receipt=receipt||cast(:receipt as jsonb),attempts=attempts+1,next_attempt_at={_backoff(60)},
                      status=case when cast(:state as text)='rejected' then 'rejected' else status end where event_id=:id
                """), {"id": row["event_id"], "receipt": json.dumps(receipt), "state": receipt.get("ingestion_status")})
        async with _scoped(engine, tenant) as db:
            # Acknowledged by Platform, not merely accepted onto its queue. The
            # domain renders the resident's decision control; Platform owns progress.
            quotes = (await db.execute(text(f"""
                select e.*,l.channel_id from platform_outbox o
                join ticket_events e on e.id=o.event_id and e.tenant_id=o.tenant_id
                join platform_links l on l.ticket_id=o.ticket_id and l.tenant_id=o.tenant_id
                where o.tenant_id={TENANT} and o.event_type='job.quote_ready'
                  and o.receipt->>'ingestion_status'='applied' and l.status='open'
                  and not exists(select 1 from messages m where m.channel_id=l.channel_id
                    and m.tenant_id=l.tenant_id and m.body->'platform'->>'approval_id'=o.data->>'approval_id')
            """))).mappings().all()
            for event in quotes:
                context = await _context(db, event)
                if context["quote"]:
                    await post_chat(db, event, f"quote:{context['quote']['id']}", quote_card(context["quote"]))


# ---- the loop ------------------------------------------------------------------------------------------------------

async def run_once(engine: AsyncEngine, client: Platform) -> None:
    """One pass of all four steps; returns when every command it started has its answer."""
    # Progress is queued first: a close written together with the last events of a ticket must not shut the
    # link before they are queued.
    await queue_progress(engine)
    await close_ended(engine)
    await send_commands(engine, client)
    await read_events(engine, client)
    await send_progress(engine, client)


async def run(engine: AsyncEngine, client: Platform) -> None:
    while True:
        read = 0
        try:
            # Commands are left on the wire: the other steps go on while the coordinator works on an answer.
            await queue_progress(engine)
            await close_ended(engine)
            await send_commands(engine, client, wait=False)
            read = await read_events(engine, client)
            await send_progress(engine, client)
        except Exception:  # noqa: BLE001 - a pass that failed (database away, a bad row) must not end the worker
            log.exception("Platform sync pass failed")
        await asyncio.sleep(max(EVERY_SECONDS, read / READS_PER_SECOND))


async def configured_pass(engine: AsyncEngine, clients: dict, retired: list) -> None:
    """Reload tenant settings each pass; keep in-flight commands on their original transport."""
    from .platform_settings import load_bridge, row
    for tenant in await _tenants(engine):
        async with _scoped(engine, tenant) as db:
            bridge = await load_bridge(db)
            saved = await row(db)
            if saved:
                await db.execute(text(f"""UPDATE platform_connection_settings
                    SET worker_seen_at=now(),worker_version=version WHERE tenant_id={TENANT}
                    AND (worker_seen_at IS NULL OR worker_seen_at<now()-interval '15 seconds' OR worker_version IS DISTINCT FROM version)
                """))
        old = clients.get(tenant)
        if old and old.bridge != bridge:
            retired.append(clients.pop(tenant))
            old = None
        if bridge is None:
            continue
        client = old or Platform(bridge)
        clients[tenant] = client
        token = _run_tenant.set(tenant)
        try:
            await queue_progress(engine)
            await close_ended(engine)
            await send_commands(engine, client, wait=False)
            await read_events(engine, client)
            await send_progress(engine, client)
        finally:
            _run_tenant.reset(token)
    if not _sending:
        for client in retired:
            await client.aclose()
        retired.clear()


async def _main(url: str) -> None:
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=MAX_SENDING + 2)
    clients, retired = {}, []
    try:
        while True:
            try:
                await configured_pass(engine, clients, retired)
            except Exception:
                # Do not log credentials or exception bodies from settings/network responses.
                log.error('Platform configuration/sync unavailable; retrying')
            await asyncio.sleep(EVERY_SECONDS)
    finally:
        if _sending:
            await asyncio.gather(*_sending.values(), return_exceptions=True)
        for client in [*clients.values(), *retired]:
            await client.aclose()
        await engine.dispose()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    asyncio.run(_main(url.replace("postgresql://", "postgresql+asyncpg://", 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
