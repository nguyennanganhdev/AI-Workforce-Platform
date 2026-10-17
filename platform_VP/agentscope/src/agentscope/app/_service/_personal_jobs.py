"""C09 consumers for personal schedules, Discord events and saved delivery.

The existing wakeup dispatcher owns this worker. A model run is never retried
after an uncertain crash; delivery retries reuse a fenced immutable body.
"""

import asyncio
import hashlib
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from ._catalog_resources import catalog_authority
from ._discord_identity import verified_owner
from ._runnable_agents import ensure_runnable
from ...message import UserMsg
from ...permission import PermissionContext
from ...state import AgentState
from ..storage import ScheduleOrigin, SessionConfig
from ..vin_platform import PlatformError
from ..workforce.foundation.event_delivery import JobLeaseLostError

personal_job = ContextVar("personal_automation_job", default=None)
HEARTBEAT_SECONDS = 15


async def personal_context(storage, user_id):
    authority = catalog_authority(storage)
    if authority is None:
        return None
    context = await authority.context(user_id)
    return (authority, context) if context.role == "VIN_USER" else None


def schedule_input(record):
    fields = ("name", "description", "stateful", "permission_mode", "chat_model_config", "deliver_channel_id", "deliver_chat_id")
    value = record.data.model_dump(mode="json")
    return {key: value[key] for key in fields}


async def enqueue_schedule(storage, record, slot):
    authority, context = await personal_context(storage, record.user_id)
    return await authority.jobs.enqueue(context, kind="schedule-run", key=record.id + ":" + slot,
        payload={"schedule_id": record.id, "slot": slot, "agent_id": record.agent_id, "config": schedule_input(record)})


async def enqueue_channel(storage, record, event):
    authority, context = await personal_context(storage, record.user_id)
    await validate_private_channel(authority, context, record)
    if not event.channel_message_id:
        raise PlatformError("CHANNEL_EVENT_ID_REQUIRED", 422)
    if event.metadata.get("chat_type") != "dm" or event.channel_user_id not in record.platform_config.get("allowed_user_ids", []):
        raise PlatformError("PRIVATE_CHANNEL_DENIED", 403)
    return await authority.jobs.enqueue(context, kind="channel-event", key=record.id + ":" + event.channel_message_id,
        payload={"channel_id": record.id, "event": event.model_dump(mode="json", exclude={"received_at"})})


async def validate_private_channel(authority, context, record):
    owner = await verified_owner(authority, context)
    if record is None or not record.enabled or record.user_id != context.initiator_user_id or record.channel_type != "discord":
        raise PlatformError("PRIVATE_CHANNEL_UNAVAILABLE", 403)
    if record.platform_config.get("owner_user_id") != owner["discord_user_id"]:
        raise PlatformError("DISCORD_OWNER_MISMATCH", 403)
    return owner


async def enqueue_deliveries(authority, context, run_id, result):
    for delivery in result.get("deliveries", []):
        await authority.jobs.enqueue(context, kind="delivery", key=run_id + ":" + delivery["key"], payload=delivery)


class PersonalJobWorker:
    """One worker per existing dispatcher process; SQL arbitrates all claims."""

    def __init__(self, storage, chat_service, workspace_manager):
        self.storage, self.chat, self.workspaces = storage, chat_service, workspace_manager
        self.worker_id = "vin-personal:" + str(uuid4())
        self.schema_checked = False

    async def run_one(self):
        authority = catalog_authority(self.storage)
        if authority is None:
            return False
        if not self.schema_checked:
            await authority.check_schema()
            self.schema_checked = True
        job = await authority.jobs.claim(self.worker_id, seconds=60)
        if job is None:
            return False

        async def execute():
            context = await authority.jobs.context_for(job)
            token = personal_job.set(job)
            try:
                if job.job_type == "delivery":
                    result = await self._deliver(authority, context, job.payload["body"])
                elif job.job_type in {"schedule-run", "channel-event"}:
                    result = await self._run(authority, context, job)
                    await authority.jobs.checkpoint(job, self.worker_id, result)
                    await enqueue_deliveries(authority, context, job.job_id, result)
                elif job.job_type == "publish-batch":
                    from ._publish_batch import run
                    # The conversation guard lease is 300s. Bound staging
                    # below it; timeout leaves a repairable checkpoint.
                    result = await asyncio.wait_for(run(self, authority, context, job), timeout=240)
                else:
                    raise PlatformError("PERSONAL_JOB_HANDLER_UNAVAILABLE", 503)
                await authority.jobs.complete(job, self.worker_id, result)
            finally:
                personal_job.reset(token)

        task = asyncio.create_task(execute())
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=HEARTBEAT_SECONDS)
                if not done:
                    # Losing this fence cancels execution before any next
                    # model/tool call or outbox write can be authorized.
                    await authority.jobs.heartbeat(job, self.worker_id, seconds=60)
            await task
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        except JobLeaseLostError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception as exc:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            code = exc.code if isinstance(exc, PlatformError) else "PERSONAL_RUN_FAILED"
            try:
                await authority.jobs.fail(job, self.worker_id, code)
            except JobLeaseLostError:
                pass
        return True

    async def _run(self, authority, context, job):
        body = job.payload["body"]
        if job.job_type == "schedule-run":
            record = await self.storage.get_schedule(context.initiator_user_id, body["schedule_id"])
            if (record is None or record.agent_id != body["agent_id"] or (not record.data.enabled and not record.data.once)
                    or schedule_input(record) != body["config"]):
                raise PlatformError("SCHEDULE_CHANGED_OR_DISABLED", 403)
            agent_id = record.agent_id
            await ensure_runnable(self.storage, context.initiator_user_id, agent_id)
            session_id = record.id + "_stateful" if record.data.stateful else "vin-job-" + job.job_id
            session = await self.storage.get_session(context.initiator_user_id, agent_id, session_id)
            if session is None:
                session = await self.storage.upsert_session(context.initiator_user_id, agent_id,
                    config=SessionConfig(workspace_id=await self.workspaces.assign_workspace_id(user_id=context.initiator_user_id,
                        agent_id=agent_id, session_id=session_id), chat_model_config=record.data.chat_model_config),
                    session_id=session_id, state=AgentState(permission_context=PermissionContext(mode=record.data.permission_mode)),
                    origin=ScheduleOrigin(schedule_id=record.id, deliver_channel_id=record.data.deliver_channel_id,
                        deliver_chat_id=record.data.deliver_chat_id))
            input_msg = UserMsg(name="schedule", content=record.data.description)
            destination = (record.data.deliver_channel_id, record.data.deliver_chat_id, None)
        else:
            from ..channel._base import ChannelEvent
            from ..channel._gateway import ChannelGateway
            record = await self.storage.get_channel(body["channel_id"])
            await validate_private_channel(authority, context, record)
            event = ChannelEvent.model_validate(body["event"])
            if event.metadata.get("chat_type") != "dm" or event.channel_user_id not in record.platform_config.get("allowed_user_ids", []):
                raise PlatformError("PRIVATE_CHANNEL_DENIED", 403)
            gateway = ChannelGateway(self.storage, self.chat._message_bus, self.workspaces)
            from ..channel._routing import resolve
            agent_id, session_id, scope = resolve(event, record)
            await ensure_runnable(self.storage, context.initiator_user_id, agent_id)
            content = await gateway._aggregate_media(event)
            if content is None:
                return {"state": "media_buffered", "deliveries": []}
            await gateway._ensure_session(record, agent_id, session_id, event, scope)
            input_msg = UserMsg(name=event.channel_user_id, content=content)
            destination = (record.id, event.chat_id, event.channel_user_id)
        await self.chat.run(context.initiator_user_id, session_id, agent_id, input_msg)
        after, _ = await self.storage.list_messages(context.initiator_user_id, session_id, limit=100)
        replies = [msg for msg in after if msg.role == "assistant" and msg.metadata.get("personal_job_id") == job.job_id]
        if not replies:
            raise PlatformError("RUN_OUTCOME_UNKNOWN", 409)
        result = {"state": "succeeded", "session_id": session_id, "agent_id": agent_id,
            "reply_ids": [msg.id for msg in replies], "deliveries": []}
        if any(getattr(msg.finished_reason, "value", msg.finished_reason) in {"error", "interrupted", "exceed_max_iters"} for msg in replies):
            result["state"] = "failed"
        elif any(msg.finished_reason is None for msg in replies):
            result["state"] = "awaiting_permission"
        channel_id, chat_id, recipient = destination
        if channel_id and chat_id:
            channel = await self.storage.get_channel(channel_id)
            owner = await validate_private_channel(authority, context, channel)
            recipient = recipient or owner["discord_user_id"]
            if recipient not in channel.platform_config.get("allowed_user_ids", []):
                raise PlatformError("PRIVATE_CHANNEL_DENIED", 403)
            for msg in replies:
                text = (msg.get_text_content() or "").strip()
                if not text:
                    text = "Kết quả cần bạn xem hoặc phê duyệt trong cuộc trò chuyện trên Platform."
                for index, offset in enumerate(range(0, len(text), 1900)):
                    result["deliveries"].append({"key": msg.id + ":" + str(index), "channel_id": channel_id,
                        "chat_id": chat_id, "recipient_id": recipient, "identity_revision": owner["revision"],
                        "body": text[offset:offset + 1900], "created_at": int(time.time()),
                        "nonce": hashlib.sha256((job.job_id + msg.id + str(index)).encode()).hexdigest()[:24]})
        if job.job_type == "schedule-run":
            current = await self.storage.get_schedule(context.initiator_user_id, body["schedule_id"])
            if current is not None:
                await self.storage.upsert_schedule(context.initiator_user_id, current.model_copy(update={"data": current.data.model_copy(update={
                    "last_fired_at": datetime.now(timezone.utc), "last_session_id": session_id,
                    "last_error": "" if result["state"] == "succeeded" else "RUN_FAILED"})}))
        return result

    async def _deliver(self, authority, context, body):
        record = await self.storage.get_channel(body["channel_id"])
        owner = await validate_private_channel(authority, context, record)
        if owner["revision"] != body["identity_revision"] or body["recipient_id"] not in record.platform_config.get("allowed_user_ids", []):
            raise PlatformError("DELIVERY_AUTHORIZATION_REVOKED", 403)
        # Discord's nonce guarantee is time-bounded. A delayed/uncertain send
        # outside that window stays unknown rather than duplicating a message.
        if time.time() - body["created_at"] > 120:
            raise PlatformError("DELIVERY_OUTCOME_UNKNOWN", 409)
        clients = self.chat._channel_clients
        channel = await clients.get(record.id) if clients is not None else None
        if channel is None:
            raise PlatformError("DELIVERY_CHANNEL_UNAVAILABLE", 503)
        return await channel.send_saved_private(body)


async def ledger(storage, user_id, kind, source_id):
    scope = await personal_context(storage, user_id)
    if scope is None:
        raise PlatformError("PERSONAL_WORKSPACE_REQUIRED", 403)
    authority, context = scope
    jobs = await authority.jobs.list(context, kind)
    key = "schedule_id" if kind == "schedule-run" else "channel_id"
    deliveries = await authority.jobs.list(context, "delivery")
    result = []
    for job in jobs:
        if job.payload["body"].get(key) != source_id:
            continue
        matching = [item for item in deliveries if item.idempotency_key.startswith("delivery:" + job.job_id + ":")]
        result.append({"id": job.job_id, "status": job.status, "attempt": job.attempt, "fencing_token": job.fencing_token,
            "created_at": job.created_at, "updated_at": job.updated_at, "session_id": (job.result or {}).get("session_id"),
            "outcome": (job.result or {}).get("state"), "error": (job.error or {}).get("code"),
            "can_repair_delivery": bool((job.result or {}).get("deliveries")) and not matching
                and all(time.time() - d["created_at"] <= 120 for d in job.result["deliveries"]),
            "deliveries": [{"id": item.job_id, "status": item.status, "attempt": item.attempt,
                "error": (item.error or {}).get("code")} for item in matching]})
    return {"items": result}


async def repair_delivery(storage, user_id, kind, source_id, job_id):
    scope = await personal_context(storage, user_id)
    if scope is None:
        raise PlatformError("PERSONAL_WORKSPACE_REQUIRED", 403)
    authority, context = scope
    key = "schedule_id" if kind == "schedule-run" else "channel_id"
    job = next((item for item in await authority.jobs.list(context, kind) if item.job_id == job_id
        and item.payload["body"].get(key) == source_id), None)
    if job is None or not job.result or not job.result.get("deliveries"):
        raise PlatformError("SAVED_DELIVERY_NOT_FOUND", 404)
    context = await authority.jobs.context_for(job)
    for body in job.result["deliveries"]:
        if time.time() - body["created_at"] > 120:
            raise PlatformError("DELIVERY_OUTCOME_UNKNOWN", 409)
        record = await storage.get_channel(body["channel_id"])
        owner = await validate_private_channel(authority, context, record)
        if owner["revision"] != body["identity_revision"]:
            raise PlatformError("DELIVERY_AUTHORIZATION_REVOKED", 403)
    await enqueue_deliveries(authority, context, job_id, job.result)
    return {"queued": True}
