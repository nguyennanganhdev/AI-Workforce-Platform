"""Atomic quota reservations. Unknown provider outcomes retain their budget."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, insert, select, update

from . import _tables as t
from ._contracts import PlatformError, QuotaPolicy

VIN_TIMEZONE = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


async def insert_once(connection, table, values):
    if connection.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as upsert
    elif connection.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as upsert
    else:
        raise PlatformError("UNSUPPORTED_AUTHORITY_DATABASE", 503)
    result = await connection.execute(upsert(table).values(**values).on_conflict_do_nothing())
    return result.rowcount


class QuotaAuthority:
    def __init__(self, service):
        self.service = service

    async def _policy(self, db, context):
        tenant, user = context.tenant_id, context.billing_subject_id
        groups = await self.service.groups(db, tenant, user)
        keys = ["user:" + user, *["group:" + g for g in groups], "role:" + context.role]
        rows = (await db.execute(select(t.policies).where(
            t.policies.c.tenant_id == tenant, t.policies.c.active.is_(True), t.policies.c.subject.in_(keys),
        ).order_by(t.policies.c.subject))).mappings().all()
        by_key = {r["subject"]: r for r in rows}
        selected = by_key.get(keys[0])
        if selected is None:
            group_rows = [by_key[k] for k in keys[1:-1] if k in by_key]
            if len({str(r["data"]) for r in group_rows}) > 1:
                raise PlatformError("QUOTA_POLICY_AMBIGUOUS", 403)
            selected = (group_rows[0] if group_rows else by_key.get(keys[-1]))
        if selected is None:
            raise PlatformError("QUOTA_POLICY_REQUIRED", 403)
        policy = QuotaPolicy.model_validate(selected["data"])
        if not policy.enabled:
            raise PlatformError("QUOTA_DISABLED", 403)
        pools = (await db.execute(select(t.policies).where(
            t.policies.c.tenant_id == tenant,
            t.policies.c.active.is_(True),
            t.policies.c.subject.in_(["pool:" + g for g in groups]),
        ).order_by(t.policies.c.subject))).mappings().all()
        return policy, selected["revision"], [(r["subject"], QuotaPolicy.model_validate(r["data"])) for r in pools]

    async def policy(self, context):
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context)
            policy, revision, _ = await self._policy(db, context)
            return policy, revision

    async def reserve(self, context, *, budget, purpose, model, attempt_id=None, now=None):
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise PlatformError("INVALID_QUOTA_RESERVATION", 422)
        now = now or datetime.now(UTC)
        local = now.astimezone(VIN_TIMEZONE)
        windows = ["day:" + local.strftime("%Y-%m-%d"), "month:" + local.strftime("%Y-%m")]
        if purpose == "embedding":
            windows.append("embedding-day:" + local.strftime("%Y-%m-%d"))
        attempt_id = attempt_id or uuid4().hex
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context)
            policy, revision, pools = await self._policy(db, context)
            if model not in policy.models:
                raise PlatformError("MODEL_NOT_ENTITLED", 403)
            prior = (await db.execute(select(t.attempts).where(t.attempts.c.id == attempt_id))).mappings().first()
            if prior:
                if (prior["tenant_id"], prior["user_id"], prior["budget"], prior["purpose"]) != (
                    context.tenant_id, context.billing_subject_id, budget, purpose,
                ):
                    raise PlatformError("IDEMPOTENCY_CONFLICT", 409)
                raise PlatformError("ATTEMPT_ALREADY_RESERVED", 409)
            scopes = []
            subject_policies = [("user:" + context.billing_subject_id, policy), *pools]
            for subject, limits in sorted(subject_policies, key=lambda item: item[0]):
                if not limits.enabled:
                    raise PlatformError("QUOTA_DISABLED", 403)
                key = and_(t.subjects.c.tenant_id == context.tenant_id, t.subjects.c.subject == subject)
                await insert_once(db, t.subjects, dict(tenant_id=context.tenant_id, subject=subject,
                    active_calls=0, stored_bytes=0, reserved_bytes=0))
                changed = await db.execute(update(t.subjects).where(key,
                    t.subjects.c.active_calls < limits.max_concurrency,
                ).values(active_calls=t.subjects.c.active_calls + 1))
                if changed.rowcount != 1:
                    raise PlatformError("QUOTA_CONCURRENCY_EXCEEDED", 429)
                for window in windows:
                    limit = limits.embedding_daily_tokens if window.startswith("embedding-day:") else limits.daily_tokens if window.startswith("day:") else limits.monthly_tokens
                    await insert_once(db, t.buckets, dict(tenant_id=context.tenant_id, subject=subject,
                        window=window, used=0, reserved=0))
                    result = await db.execute(update(t.buckets).where(
                        t.buckets.c.tenant_id == context.tenant_id, t.buckets.c.subject == subject,
                        t.buckets.c.window == window,
                        t.buckets.c.used + t.buckets.c.reserved + budget <= limit,
                    ).values(reserved=t.buckets.c.reserved + budget))
                    if result.rowcount != 1:
                        raise PlatformError("QUOTA_EXCEEDED", 429, window=window)
                    scopes.append({"subject": subject, "window": window})
            await db.execute(insert(t.attempts).values(id=attempt_id, tenant_id=context.tenant_id,
                user_id=context.billing_subject_id, state="reserved", purpose=purpose, budget=budget,
                scopes=scopes, created_at=now, data={"model": model, "policy_revision": revision,
                    "initiator_user_id": context.initiator_user_id, "workspace_id": context.workspace_id}))
        return attempt_id

    async def settle(self, tenant, attempt_id, actual, *, provider_request_id=None):
        if actual is not None and (isinstance(actual, bool) or not isinstance(actual, int) or actual < 0):
            raise PlatformError("INVALID_PROVIDER_USAGE", 422)
        async with self.service.engine.begin() as db:
            row = (await db.execute(select(t.attempts).where(t.attempts.c.id == attempt_id,
                t.attempts.c.tenant_id == tenant).with_for_update())).mappings().first()
            if row is None:
                raise PlatformError("RESERVATION_NOT_FOUND", 404)
            if row["state"] == "settled":
                if actual != row["actual"]:
                    raise PlatformError("SETTLEMENT_CONFLICT", 409)
                return
            if actual is None:
                if not row["data"].get("concurrency_released"):
                    changed = await db.execute(update(t.attempts).where(t.attempts.c.id == attempt_id,
                        t.attempts.c.state == row["state"],
                        t.attempts.c.data["concurrency_released"].as_boolean().is_not(True),
                    ).values(state="pending_reconciliation", data={**row["data"],
                        "provider_request_id": provider_request_id, "concurrency_released": True}))
                    if changed.rowcount:
                        await self._release_slots(db, tenant, row["scopes"])
                return
            # CAS protects SQLite too. The row lock protects PostgreSQL concurrent settle.
            claimed = await db.execute(update(t.attempts).where(t.attempts.c.id == attempt_id,
                t.attempts.c.state.in_(["reserved", "pending_reconciliation"]),
            ).values(state="settled", actual=actual, data={**row["data"], "provider_request_id": provider_request_id}))
            if claimed.rowcount != 1:
                raise PlatformError("SETTLEMENT_CONFLICT", 409)
            for scope in row["scopes"]:
                await db.execute(update(t.buckets).where(t.buckets.c.tenant_id == tenant,
                    t.buckets.c.subject == scope["subject"], t.buckets.c.window == scope["window"],
                ).values(reserved=t.buckets.c.reserved - row["budget"], used=t.buckets.c.used + actual))
            if not row["data"].get("concurrency_released"):
                await self._release_slots(db, tenant, row["scopes"])

    async def _release_slots(self, db, tenant, scopes):
        for subject in sorted({scope["subject"] for scope in scopes}):
            await db.execute(update(t.subjects).where(t.subjects.c.tenant_id == tenant,
                t.subjects.c.subject == subject, t.subjects.c.active_calls > 0,
            ).values(active_calls=t.subjects.c.active_calls - 1))

    async def mark_dispatched(self, tenant, attempt_id):
        async with self.service.engine.begin() as db:
            data = (await db.execute(select(t.attempts.c.data).where(t.attempts.c.tenant_id == tenant,
                t.attempts.c.id == attempt_id, t.attempts.c.state == "reserved").with_for_update())).scalar_one()
            await db.execute(update(t.attempts).where(t.attempts.c.tenant_id == tenant,
                t.attempts.c.id == attempt_id, t.attempts.c.state == "reserved",
            ).values(data={**data, "dispatch_started": True}))

    async def usage(self, context):
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            rows = (await db.execute(select(t.buckets).where(t.buckets.c.tenant_id == context.tenant_id,
                t.buckets.c.subject == "user:" + context.billing_subject_id))).mappings().all()
            pending = (await db.execute(select(t.attempts.c.id).where(t.attempts.c.tenant_id == context.tenant_id,
                t.attempts.c.user_id == context.billing_subject_id, t.attempts.c.state != "settled"))).scalars().all()
            policy, revision, pools = await self._policy(db, context)
            local = datetime.now(UTC).astimezone(VIN_TIMEZONE)
            windows = {"day": "day:" + local.strftime("%Y-%m-%d"), "month": "month:" + local.strftime("%Y-%m"),
                "embedding-day": "embedding-day:" + local.strftime("%Y-%m-%d")}
            limits = []
            for subject, rules in [("user:" + context.billing_subject_id, policy), *pools]:
                for period, window in windows.items():
                    row = (await db.execute(select(t.buckets).where(t.buckets.c.tenant_id == context.tenant_id,
                        t.buckets.c.subject == subject, t.buckets.c.window == window))).mappings().first()
                    used, reserved = (row["used"], row["reserved"]) if row else (0, 0)
                    limit = rules.embedding_daily_tokens if period == "embedding-day" else rules.daily_tokens if period == "day" else rules.monthly_tokens
                    limits.append({"subject": subject, "window": window, "limit": limit,
                        "used": used, "reserved": reserved, "remaining": max(0, limit - used - reserved)})
            return {"timezone": "Asia/Ho_Chi_Minh", "buckets": [dict(r) for r in rows],
                "pending_reconciliation": len(pending), "effective_limits": limits, "policy_revision": revision}
