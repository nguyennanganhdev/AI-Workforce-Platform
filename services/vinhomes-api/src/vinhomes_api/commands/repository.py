"""Storage operations for durable idempotency receipts."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.command_receipt import CommandReceipt, CommandReceiptStatus


class IdempotencyKeyConflict(Exception):
    """A key was reused for a different command payload."""


class CommandReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self,
        *,
        tenant_id,
        actor_type: str,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
        for_update: bool = False,
    ) -> CommandReceipt | None:
        statement = select(CommandReceipt).where(
            CommandReceipt.tenant_id == tenant_id,
            CommandReceipt.actor_type == actor_type,
            CommandReceipt.actor_id == actor_id,
            CommandReceipt.command_type == command_type,
            CommandReceipt.idempotency_key == idempotency_key,
        )
        if for_update:
            statement = statement.with_for_update(of=CommandReceipt)
        return await self.session.scalar(statement)

    def add(
        self,
        *,
        tenant_id,
        actor_type: str,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
        payload_hash: str,
        subject_type: str,
        subject_id: str | None = None,
    ) -> CommandReceipt:
        receipt = CommandReceipt(
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            subject_type=subject_type,
            subject_id=subject_id,
            response_json=None,
            status=CommandReceiptStatus.IN_PROGRESS,
        )
        self.session.add(receipt)
        return receipt

    async def complete(
        self,
        receipt: CommandReceipt,
        *,
        subject_id: str,
        response_json: dict,
    ) -> CommandReceipt:
        receipt.subject_id = subject_id
        receipt.response_json = response_json
        receipt.status = CommandReceiptStatus.COMPLETED
        receipt.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return receipt
