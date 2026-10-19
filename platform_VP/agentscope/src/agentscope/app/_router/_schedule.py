# -*- coding: utf-8 -*-
"""Schedule router — CRUD endpoints for scheduled agent tasks."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..access import ResourceKind
from .._manager import SchedulerManager
from ..deps import (
    get_current_user_id,
    get_resource_access_service,
    get_scheduler_manager,
    get_session_service,
    get_storage,
)
from ._schema import (
    CreateScheduleRequest,
    CreateScheduleResponse,
    ListSchedulesResponse,
    ScheduleSessionsResponse,
    UpdateScheduleRequest,
)
from .._service import ResourceAccessService, SessionService
from .._service._runnable_agents import is_runnable
from ...permission import PermissionMode
from ..storage import (
    StorageBase,
    ScheduleData,
    ScheduleRecord,
    ScheduleSource,
)

schedule_router = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
    responses={404: {"description": "Not found"}},
)


@schedule_router.get("/{schedule_id}/runs")
async def personal_schedule_runs(schedule_id: str, user_id: str = Depends(get_current_user_id), storage: StorageBase = Depends(get_storage), cursor: str | None = None, limit: int = Query(25, ge=1, le=100)):
    from .._service._personal_jobs import ledger
    from ..vin_platform import PlatformError
    if await storage.get_schedule(user_id, schedule_id) is None:
        raise HTTPException(404, "Schedule not found")
    try:
        return await ledger(storage, user_id, "schedule-run", schedule_id, cursor=cursor, limit=limit)
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc


@schedule_router.post("/{schedule_id}/runs/{job_id}/repair-delivery")
async def repair_schedule_delivery(schedule_id: str, job_id: str, user_id: str = Depends(get_current_user_id), storage: StorageBase = Depends(get_storage)):
    from .._service._personal_jobs import repair_delivery
    from ..vin_platform import PlatformError
    if await storage.get_schedule(user_id, schedule_id) is None:
        raise HTTPException(404, "Schedule not found")
    try:
        return await repair_delivery(storage, user_id, "schedule-run", schedule_id, job_id)
    except PlatformError as exc:
        raise HTTPException(exc.status, exc.code) from exc


@schedule_router.get(
    "/",
    response_model=ListSchedulesResponse,
    summary="List all schedules",
)
async def list_schedules(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> ListSchedulesResponse:
    """List all schedules owned by the current user.

    Args:
        user_id (`str`): Authenticated user ID.
        storage (`StorageBase`): Storage instance.

    Returns:
        `ListSchedulesResponse`:
            Paginated list of schedule records.
    """
    schedules = await storage.list_schedules(user_id)
    return ListSchedulesResponse(schedules=schedules, total=len(schedules))


@schedule_router.post(
    "/",
    response_model=CreateScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new schedule",
)
async def create_schedule(
    body: CreateScheduleRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    access: ResourceAccessService = Depends(get_resource_access_service),
    scheduler: SchedulerManager = Depends(get_scheduler_manager),
) -> CreateScheduleResponse:
    """Create a new schedule and hand it to the scheduler.

    The referenced agent may be either the viewer's own or one shared
    to them through :class:`ResourceAccessPolicyBase`; the schedule
    record itself is always owned by the caller.

    Args:
        body (`CreateScheduleRequest`): Schedule configuration.
        user_id (`str`): Authenticated user ID.
        storage (`StorageBase`): Storage instance.
        access (`ResourceAccessService`): Access service.
        scheduler (`SchedulerManager`): Scheduler manager.

    Returns:
        `CreateScheduleResponse`:
            The ID of the newly created schedule.

    Raises:
        `HTTPException`: 404 if the specified agent or the credential
            referenced by ``chat_model_config`` is not visible to the
            caller; 422 if the cron expression, timezone or activation
            window is invalid.
    """
    # Visibility checks — raise 404 when neither owned nor shared. The
    # schedule fires under the owner's user_id, so re-validating the
    # credential here surfaces the error at creation time rather than
    # silently at the first (possibly much later) scheduled run.
    agent = await access.resolve_agent(user_id, body.agent_id)
    await access.get_resource(
        user_id,
        ResourceKind.CREDENTIAL,
        body.chat_model_config.credential_id,
    )

    record = ScheduleRecord(
        user_id=user_id,
        agent_id=body.agent_id,
        data=ScheduleData(
            name=body.name,
            description=body.description,
            cron_expression=body.cron_expression,
            timezone=body.timezone,
            enabled=body.enabled,
            stateful=body.stateful,
            permission_mode=body.permission_mode,
            chat_model_config=body.chat_model_config,
            once=body.once,
            ended_at=None if body.once else body.ended_at,
            deliver_channel_id=body.deliver_channel_id,
            deliver_chat_id=body.deliver_chat_id,
            source=ScheduleSource.USER,
            # Aware on purpose: the trigger reads a naive start time in
            # the schedule's own timezone, not the server's.
            started_at=datetime.now().astimezone(),
        ),
    )

    record = await _checked(record, agent, storage, scheduler)
    await storage.upsert_schedule(user_id, record)
    await scheduler.notify_changed(record.id)

    return CreateScheduleResponse(schedule_id=record.id)


async def _checked(record, agent, storage, scheduler) -> ScheduleRecord:
    """Workforce rules for an unattended run, plus the cron validation.

    Only the Leader or a published agent runs on a schedule; it never runs
    with BYPASS, so a write tool still needs a person; a result channel must
    be the owner's own. A one-time schedule ends just after its next fire.
    """
    if not is_runnable(agent):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Agent “{agent.data.name}” chưa phát hành. Chỉ Leader hoặc agent "
            "đã phát hành mới được chạy theo lịch.",
        )
    if record.data.permission_mode == PermissionMode.BYPASS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Lịch chạy không được dùng chế độ BYPASS; thao tác cần đồng ý "
            "vẫn phải có người duyệt.",
        )
    if bool(record.data.deliver_channel_id) != bool(record.data.deliver_chat_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Chọn cả kênh và cuộc trò chuyện nhận kết quả, hoặc bỏ trống cả hai.",
        )
    if record.data.deliver_channel_id:
        channel = await storage.get_channel(record.data.deliver_channel_id)
        if channel is None or channel.user_id != record.user_id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Không tìm thấy kênh nhận kết quả.",
            )
    try:
        trigger = scheduler.validate_schedule(record)
        if record.data.once:
            first = trigger.get_next_fire_time(None, datetime.now(trigger.timezone))
            if first is None:
                raise ValueError("The one-time schedule has no future fire time")
            record = record.model_copy(update={"data": record.data.model_copy(
                update={"ended_at": first + timedelta(minutes=1)},
            )})
            scheduler.validate_schedule(record)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return record


@schedule_router.patch(
    "/{schedule_id}",
    response_model=ScheduleRecord,
    summary="Update a schedule",
)
async def update_schedule(
    schedule_id: str,
    body: UpdateScheduleRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    scheduler: SchedulerManager = Depends(get_scheduler_manager),
    access: ResourceAccessService = Depends(get_resource_access_service),
) -> ScheduleRecord:
    """Partially update a schedule.

    Fields omitted from the request body keep their current values.
    Changing ``cron_expression`` or ``timezone`` reschedules the job, and
    ``enable=False`` stops it firing without deleting the record — both
    take effect once the timer-owning node reconciles.

    Args:
        schedule_id (`str`): ID of the schedule to update.
        body (`UpdateScheduleRequest`): Fields to update.
        user_id (`str`): Authenticated user ID.
        storage (`StorageBase`): Storage instance.
        scheduler (`SchedulerManager`): Scheduler manager.

    Returns:
        `ScheduleRecord`:
            The updated schedule record.

    Raises:
        `HTTPException`: 404 if the schedule does not exist; 422 if the
            update leaves an invalid cron expression, timezone or
            activation window.
    """
    existing = await storage.get_schedule(user_id, schedule_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found.",
        )

    updates = body.model_dump(exclude_none=True)
    if updates.get("once") is False:
        updates["ended_at"] = None
    updated_data = existing.data.model_copy(update=updates)
    updated_record = existing.model_copy(
        update={"data": updated_data, "updated_at": datetime.now()},
    )
    agent = await access.resolve_agent(user_id, existing.agent_id)
    updated_record = await _checked(updated_record, agent, storage, scheduler)

    await storage.upsert_schedule(user_id, updated_record)
    await scheduler.notify_changed(schedule_id)

    return updated_record


@schedule_router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a schedule",
)
async def delete_schedule(
    schedule_id: str,
    user_id: str = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
    scheduler: SchedulerManager = Depends(get_scheduler_manager),
) -> None:
    """Permanently delete a schedule.

    Cancels any in-flight chat run for sessions this schedule has
    triggered, removes their records via the session service, and tells
    the timer-owning node to drop the job.

    Args:
        schedule_id (`str`): ID of the schedule to delete.
        user_id (`str`): Authenticated user ID.
        session_service (`SessionService`): Injected session service.
        scheduler (`SchedulerManager`): Scheduler manager.

    Raises:
        `HTTPException`: 404 if the schedule does not exist.
    """
    deleted = await session_service.delete_schedule(user_id, schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found.",
        )
    await scheduler.notify_changed(schedule_id)


@schedule_router.get(
    "/{schedule_id}/sessions",
    response_model=ScheduleSessionsResponse,
    summary="List execution sessions for a schedule",
)
async def list_schedule_sessions(
    schedule_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> ScheduleSessionsResponse:
    """Return all sessions triggered by a given schedule.

    Args:
        schedule_id (`str`): ID of the schedule.
        user_id (`str`): Authenticated user ID.
        storage (`StorageBase`): Storage instance.

    Returns:
        `ScheduleSessionsResponse`:
            List of execution sessions ordered by creation time (newest first).

    Raises:
        `HTTPException`: 404 if the schedule does not exist.
    """
    existing = await storage.get_schedule(user_id, schedule_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule '{schedule_id}' not found.",
        )

    sessions = await storage.list_sessions_by_schedule(user_id, schedule_id)
    return ScheduleSessionsResponse(sessions=sessions, total=len(sessions))
