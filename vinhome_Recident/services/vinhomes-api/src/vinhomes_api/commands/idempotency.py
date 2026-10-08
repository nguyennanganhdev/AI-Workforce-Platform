"""Small helpers for replaying durable command receipts in API routes."""

from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.command_receipt import CommandReceiptStatus
from .hashing import command_payload_hash
from .repository import CommandReceiptRepository

ReadModel = TypeVar("ReadModel", bound=BaseModel)


async def replay_command_response(
    *,
    session: AsyncSession,
    tenant_id,
    actor_type: str,
    actor_id: str,
    command_type: str,
    idempotency_key: str | None,
    subject_type: str,
    subject_id: str,
    payload: BaseModel,
    response_model: type[ReadModel],
) -> ReadModel | None:
    if idempotency_key is None:
        return None
    receipt = await CommandReceiptRepository(session).get(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        command_type=command_type,
        idempotency_key=idempotency_key,
        for_update=True,
    )
    if receipt is None:
        return None
    payload_hash = command_payload_hash({
        "subjectType": subject_type,
        "subjectId": subject_id,
        "payload": payload.model_dump(mode="json", by_alias=True),
    })
    if receipt.payload_hash != payload_hash:
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
    if receipt.status is not CommandReceiptStatus.COMPLETED or receipt.response_json is None:
        raise HTTPException(status_code=409, detail="Command with this Idempotency-Key is still in progress")
    return response_model.model_validate(receipt.response_json)


async def store_command_response(
    *,
    session: AsyncSession,
    tenant_id,
    actor_type: str,
    actor_id: str,
    command_type: str,
    idempotency_key: str | None,
    subject_type: str,
    subject_id: str,
    payload: BaseModel,
    response: BaseModel,
) -> None:
    if idempotency_key is None:
        return
    payload_hash = command_payload_hash({
        "subjectType": subject_type,
        "subjectId": subject_id,
        "payload": payload.model_dump(mode="json", by_alias=True),
    })
    receipts = CommandReceiptRepository(session)
    receipt = receipts.add(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        command_type=command_type,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    await receipts.complete(
        receipt,
        subject_id=subject_id,
        response_json=response.model_dump(mode="json", by_alias=True),
    )
