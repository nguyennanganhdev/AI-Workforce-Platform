"""Tenant-scoped authority, safe catalogs, secret references and durable jobs."""

import hashlib
import json
import os
import secrets as random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, insert, or_, select, text, update

from . import _tables as t
from ._contracts import CatalogEntry, ExecutionContext, PlatformError, QuotaPolicy, ResourceGrant
from ._quota import QuotaAuthority, insert_once


def now():
    return datetime.now(UTC)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class VinPlatformService:
    """One authority shared by HTTP, workers and model factories.

    The service reuses AuthService's SQL engine/lifecycle. Enabling it requires
    migrations; it never silently creates tables or falls back to memory.
    """

    def __init__(self, auth, storage, *, encryption_key=None, http_client=None):
        self.auth, self.storage = auth, storage
        self._encryption_key = encryption_key
        self.http_client = http_client
        self.quota = QuotaAuthority(self)

    @property
    def engine(self):
        return self.auth._require_engine()

    @property
    def jobs(self):
        from ._jobs import PersonalJobs
        return PersonalJobs(self)

    def cipher(self):
        key = self._encryption_key or os.getenv("VIN_PLATFORM_ENCRYPTION_KEY", "")
        if not key:
            raise PlatformError("SECRET_STORE_NOT_CONFIGURED", 503)
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise PlatformError("SECRET_STORE_NOT_CONFIGURED", 503) from exc

    async def check_schema(self):
        """Fail at startup rather than silently running an unmigrated authority."""
        from ..workforce.foundation._tables import durable_jobs
        async with self.engine.connect() as db:
            for table in t.metadata.sorted_tables:
                await db.execute(select(table).limit(0))
            await db.execute(select(durable_jobs.c.personal_user_id).limit(0))

    async def reconcile_attempt(self, context, ident, actual, receipt_ref):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            row = (await db.execute(select(t.attempts.c.state).where(t.attempts.c.tenant_id == context.tenant_id,
                t.attempts.c.id == ident))).first()
            if row is None:
                raise PlatformError("RESERVATION_NOT_FOUND", 404)
        await self.quota.settle(context.tenant_id, ident, actual, provider_request_id=receipt_ref)
        async with self.engine.begin() as db:
            await self.audit(db, context, "quota.reconciled", ident, actual=actual, receipt_ref=receipt_ref)

    async def assert_active(self, db, context, *, require_eligible=True):
        from ._workspaces import account as current_account, options
        row = await current_account(db, context.initiator_user_id)
        if row is None or row["status"] != "active" or row["tenant_id"] != context.tenant_id or row["role"] != context.role:
            raise PlatformError("AUTH_REQUIRED", 401)
        if context.billing_subject_id != context.initiator_user_id:
            # Service jobs must obtain a server-resolved customer context;
            # public callers cannot nominate somebody else's quota.
            raise PlatformError("BILLING_SUBJECT_MISMATCH", 403)
        if context.workspace_id not in {item.id for item in options(row)}:
            raise PlatformError("AUTHORIZATION_REVOKED", 403)
        account = (await db.execute(select(t.accounts).where(t.accounts.c.user_id == row["id"],
            t.accounts.c.tenant_id == context.tenant_id))).mappings().first()
        if account and account["revision"] != context.authorization_revision:
            raise PlatformError("AUTHORIZATION_REVOKED", 403)
        if require_eligible and row["role"] == "VIN_USER" and (account is None or not account["eligible"]):
            raise PlatformError("ELIGIBILITY_REQUIRED", 403)
        return row

    async def context(self, user_id, *, purpose="chat", environment="production", session_id=None, workspace_id=None):
        from ._workspaces import account, options, selected
        async with self.engine.connect() as db:
            row = await account(db, user_id)
            if not row or row["status"] != "active":
                raise PlatformError("AUTH_REQUIRED", 401)
            revision = (await db.execute(select(t.accounts.c.revision).where(
                t.accounts.c.user_id == user_id, t.accounts.c.tenant_id == row["tenant_id"]))).scalar_one_or_none() or 1
            choices = options(row)
            context = ExecutionContext(tenant_id=row["tenant_id"], initiator_user_id=user_id,
                billing_subject_id=user_id, workspace_id=workspace_id or choices[-1].id, role=row["role"],
                authorization_revision=revision, purpose=purpose, environment=environment)
            if session_id is not None and workspace_id is None:
                saved = await selected(db, context, session_id)
                if saved:
                    context.workspace_id = saved["data"]["workspace_id"]
                    if context.workspace_id not in {item.id for item in choices}:
                        context.workspace_id = choices[0].id
            if context.workspace_id not in {item.id for item in choices}:
                raise PlatformError("CAPABILITY_DENIED", 403)
            return context

    async def groups(self, db, tenant, user):
        return list((await db.execute(select(t.memberships.c.group_id).where(
            t.memberships.c.tenant_id == tenant, t.memberships.c.user_id == user,
            t.memberships.c.active.is_(True), or_(t.memberships.c.expires_at.is_(None), t.memberships.c.expires_at > now()),
        ).order_by(t.memberships.c.group_id))).scalars().all())

    @staticmethod
    def admin(context):
        if context.role != "PLATFORM_ADMIN" or not context.workspace_id.startswith("administration:"):
            raise PlatformError("CAPABILITY_DENIED", 403)

    async def audit(self, db, context, action, resource_id, **details):
        await db.execute(insert(t.audit).values(id=uuid4().hex, tenant_id=context.tenant_id,
            actor_id=context.initiator_user_id, action=action, resource_id=resource_id,
            data=details, created_at=now()))

    async def capabilities(self, context):
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            account = (await db.execute(select(t.accounts).where(t.accounts.c.user_id == context.initiator_user_id))).mappings().first()
            eligible = context.role != "VIN_USER" or bool(account and account["eligible"])
            return {"contract_version": "vin-platform-1", **context.model_dump(), "eligible": eligible,
                "capabilities": {"personal.read": True, "personal.create": eligible,
                    "personal.execute": eligible, "agents.author": eligible,
                    "schedules.manage": eligible, "channels.manage": eligible,
                    "providers.read": True, "mcps.read": True, "skills.read": True,
                    "domain-links.manage": True, "usage.read": True,
                    "accounts.manage": context.role in {"PLATFORM_ADMIN", "DOMAIN_ADMIN"} and context.workspace_id.startswith("administration:"),
                    "providers.manage": context.role == "PLATFORM_ADMIN" and context.workspace_id.startswith("administration:"),
                    "knowledge.private.manage": eligible, "catalog.manage": context.role == "PLATFORM_ADMIN" and context.workspace_id.startswith("administration:"),
                    "management.read": context.role == "AREA_MANAGER" and context.workspace_id.startswith("operations:"),
                    "quota.manage": context.role == "PLATFORM_ADMIN" and context.workspace_id.startswith("administration:")}}

    async def set_eligibility(self, context, user_id, eligible):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            target = (await db.execute(text("SELECT id FROM auth_users WHERE id=:id AND tenant_id=:t"),
                {"id": user_id, "t": context.tenant_id})).scalar_one_or_none()
            if not target:
                raise PlatformError("ACCOUNT_NOT_FOUND", 404)
            await insert_once(db, t.accounts, dict(user_id=user_id, tenant_id=context.tenant_id, eligible=False, revision=1))
            await db.execute(update(t.accounts).where(t.accounts.c.user_id == user_id).values(
                eligible=eligible, revision=t.accounts.c.revision + 1))
            await self.audit(db, context, "eligibility.changed", user_id, eligible=eligible)

    async def set_policy(self, context, subject, policy: QuotaPolicy):
        self.admin(context)
        if not subject.startswith(("user:", "role:", "group:", "pool:")) or len(subject) > 255:
            raise PlatformError("INVALID_QUOTA_SUBJECT", 422)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            await insert_once(db, t.policies, dict(tenant_id=context.tenant_id, subject=subject,
                data=policy.model_dump(), revision=0))
            await db.execute(update(t.policies).where(t.policies.c.tenant_id == context.tenant_id,
                t.policies.c.subject == subject).values(data=policy.model_dump(), revision=t.policies.c.revision + 1))
            await self.audit(db, context, "quota.policy_changed", subject)

    async def add_membership(self, context, user_id, group_id, *, domain_id=None, area_id=None, expires_at=None):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            target = (await db.execute(text("SELECT id FROM auth_users WHERE tenant_id=:t AND id=:u"),
                {"t": context.tenant_id, "u": user_id})).scalar_one_or_none()
            if not target:
                raise PlatformError("ACCOUNT_NOT_FOUND", 404)
            ident = uuid4().hex
            await db.execute(insert(t.memberships).values(id=ident, tenant_id=context.tenant_id, user_id=user_id,
                group_id=group_id, domain_id=domain_id, area_id=area_id, active=True, expires_at=expires_at))
            await self.audit(db, context, "membership.granted", ident)
            return ident

    async def revoke_membership(self, context, ident):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            await db.execute(update(t.memberships).where(t.memberships.c.id == ident,
                t.memberships.c.tenant_id == context.tenant_id).values(active=False))
            await self.audit(db, context, "membership.revoked", ident)

    async def publish_catalog(self, context, entry: CatalogEntry):
        self.admin(context)
        # Resource ownership must be in this tenant, including service accounts.
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            owner = (await db.execute(text("SELECT id FROM auth_users WHERE id=:u AND tenant_id=:t"),
                {"u": entry.owner_id, "t": context.tenant_id})).scalar_one_or_none()
            if not owner:
                raise PlatformError("RESOURCE_OWNER_NOT_FOUND", 404)
            existing = (await db.execute(select(t.catalog).where(t.catalog.c.tenant_id == context.tenant_id,
                t.catalog.c.kind == entry.kind, t.catalog.c.resource_id == entry.resource_id).with_for_update())).mappings().first()
            if existing:
                if entry.version <= existing["version"]:
                    raise PlatformError("REVISION_CONFLICT", 409)
                ident = existing["id"]
                await db.execute(update(t.catalog).where(t.catalog.c.id == ident).values(
                    version=entry.version, owner_id=entry.owner_id, active=entry.active, data=entry.model_dump()))
            else:
                ident = uuid4().hex
                await db.execute(insert(t.catalog).values(id=ident, tenant_id=context.tenant_id, kind=entry.kind,
                    resource_id=entry.resource_id, owner_id=entry.owner_id, version=entry.version,
                    active=entry.active, data=entry.model_dump()))
            await self.audit(db, context, "catalog.published", ident, version=entry.version)
            return ident

    async def grant(self, context, grant: ResourceGrant):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            resource = (await db.execute(select(t.catalog.c.id).where(t.catalog.c.id == grant.catalog_id,
                t.catalog.c.tenant_id == context.tenant_id))).scalar_one_or_none()
            if not resource:
                raise PlatformError("RESOURCE_NOT_FOUND", 404)
            ident = uuid4().hex
            await db.execute(insert(t.grants).values(id=ident, tenant_id=context.tenant_id, active=True,
                **grant.model_dump()))
            await self.audit(db, context, "resource.granted", ident)
            return ident

    async def revoke_grant(self, context, ident):
        self.admin(context)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            await db.execute(update(t.grants).where(t.grants.c.id == ident,
                t.grants.c.tenant_id == context.tenant_id).values(active=False))
            await self.audit(db, context, "resource.revoked", ident)

    async def catalog(self, context, kind=None, permission="view"):
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            groups = await self.groups(db, context.tenant_id, context.initiator_user_id)
            subjects = or_(and_(t.grants.c.subject_kind == "user", t.grants.c.subject_id == context.initiator_user_id),
                and_(t.grants.c.subject_kind == "role", t.grants.c.subject_id == context.role),
                and_(t.grants.c.subject_kind == "group", t.grants.c.subject_id.in_(groups)))
            query = select(t.catalog, t.grants.c.permissions).join(t.grants, t.grants.c.catalog_id == t.catalog.c.id).where(
                t.catalog.c.tenant_id == context.tenant_id, t.grants.c.tenant_id == context.tenant_id,
                t.catalog.c.active.is_(True), t.grants.c.active.is_(True), subjects,
                or_(t.grants.c.expires_at.is_(None), t.grants.c.expires_at > now()))
            if kind:
                query = query.where(t.catalog.c.kind == kind)
            rows = (await db.execute(query)).mappings().all()
            visible = {}
            for row in rows:
                if row["data"]["environment"] != context.environment:
                    continue
                entry = visible.setdefault(row["id"], {"catalog_id": row["id"], **row["data"], "permissions": []})
                entry["permissions"] = sorted(set(entry["permissions"]) | set(row["permissions"]))
            return sorted((r for r in visible.values() if permission in r["permissions"]), key=lambda r: r["catalog_id"])

    async def resolve_catalog(self, context, kind, ident, *, permission="bind", version=None):
        entries = await self.catalog(context, kind, permission)
        entry = next((r for r in entries if r["resource_id"] == ident), None)
        if entry is None:
            raise PlatformError("RESOURCE_NOT_FOUND", 404)
        if version is not None and version != entry["version"]:
            raise PlatformError("RESOURCE_REVOKED", 409)
        getter = getattr(self.storage, {"mcp": "get_mcp", "skill": "get_skill",
            "knowledge_base": "get_knowledge_base", "credential": "get_credential", "agent": "get_agent"}[kind])
        record = await getter(entry["owner_id"], ident)
        if record is None or (kind in {"mcp", "skill"} and not record.enabled) or (
            kind == "skill" and record.review_status != "approved"):
            raise PlatformError("RESOURCE_REVOKED", 404)
        return entry, record

    async def secret_put(self, context, value, purpose):
        self.admin(context)
        ident = uuid4().hex
        encrypted = self.cipher().encrypt(value.encode()).decode()
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            await db.execute(insert(t.secrets).values(id=ident, tenant_id=context.tenant_id,
                purpose=purpose, ciphertext=encrypted, active=True))
            await self.audit(db, context, "secret.stored", ident, purpose=purpose)
        return ident

    async def migrate_credentials(self, context, *, dry_run=True):
        """Remove exact shared-key copies without changing any resource ID.

        No provider requests, no raw key/hash in response/audit. Unrecognized
        legacy values require explicit operator mapping; never guess by name.
        """
        from ._resources import PLATFORM_KEY_REFERENCE
        self.admin(context)
        shared = os.getenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", "").strip()
        if not shared:
            raise PlatformError("PROVIDER_NOT_CONFIGURED", 503)
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            users = (await db.execute(text("SELECT id FROM auth_users WHERE tenant_id=:t"), {"t": context.tenant_id})).scalars().all()
        counts = {"scanned": 0, "matched": 0, "rewritten": 0, "conflicts": 0, "unmapped": 0, "dry_run": dry_run}
        for user in users:
            for record in await self.storage.list_credentials(user):
                counts["scanned"] += 1
                if record.data.get("secret_ref") == PLATFORM_KEY_REFERENCE:
                    continue
                if record.data.get("api_key") != shared:
                    counts["unmapped"] += 1
                    continue
                counts["matched"] += 1
                if not dry_run:
                    replacement = {**record.data, "api_key": "server-managed", "secret_ref": PLATFORM_KEY_REFERENCE}
                    changed = await self.storage.replace_credential_data(user, record.id, record.data, replacement)
                    counts["rewritten" if changed else "conflicts"] += 1
        async with self.engine.begin() as db:
            await self.audit(db, context, "credentials.reference_migration", "tenant", **counts)
        return counts

    async def secret_get(self, tenant, ident, purpose):
        async with self.engine.connect() as db:
            row = (await db.execute(select(t.secrets).where(t.secrets.c.tenant_id == tenant,
                t.secrets.c.id == ident, t.secrets.c.purpose == purpose, t.secrets.c.active.is_(True)))).mappings().first()
        if not row:
            raise PlatformError("SECRET_NOT_AVAILABLE", 503)
        try:
            return self.cipher().decrypt(row["ciphertext"].encode()).decode()
        except InvalidToken as exc:
            raise PlatformError("SECRET_NOT_AVAILABLE", 503) from exc

    async def automation_put(self, context, ident, kind, payload, expected_revision=0):
        if kind not in {"schedule", "channel", "delivery", "sandbox", "derived", "upload"}:
            raise PlatformError("INVALID_AUTOMATION_KIND", 422)
        async with self.engine.begin() as db:
            await self.assert_active(db, context)
            where = and_(t.automation.c.id == ident, t.automation.c.tenant_id == context.tenant_id,
                t.automation.c.user_id == context.initiator_user_id, t.automation.c.kind == kind)
            if expected_revision == 0:
                from sqlalchemy.exc import IntegrityError
                try:
                    await db.execute(insert(t.automation).values(id=ident, tenant_id=context.tenant_id,
                        user_id=context.initiator_user_id, kind=kind, data=payload, revision=1))
                except IntegrityError as exc:
                    raise PlatformError("REVISION_CONFLICT", 409) from exc
            else:
                changed = await db.execute(update(t.automation).where(where,
                    t.automation.c.revision == expected_revision,
                    or_(t.automation.c.lease_until.is_(None), t.automation.c.lease_until < now()),
                ).values(data=payload, claim_token=None, lease_until=None, revision=expected_revision + 1))
                if changed.rowcount != 1:
                    raise PlatformError("REVISION_CONFLICT", 409)
        return expected_revision + 1

    async def automation_list(self, context, kind):
        async with self.engine.begin() as db:
            await self.assert_active(db, context, require_eligible=False)
            rows = (await db.execute(select(t.automation).where(t.automation.c.tenant_id == context.tenant_id,
                t.automation.c.user_id == context.initiator_user_id, t.automation.c.kind == kind))).mappings().all()
            return [dict(r) for r in rows]

    async def claim(self, context, ident, *, seconds=60):
        if not 1 <= seconds <= 300:
            raise PlatformError("INVALID_LEASE", 422)
        token = random.token_urlsafe(32)
        async with self.engine.begin() as db:
            await self.assert_active(db, context)
            row = (await db.execute(select(t.automation).where(t.automation.c.id == ident,
                t.automation.c.tenant_id == context.tenant_id, t.automation.c.user_id == context.initiator_user_id).with_for_update())).mappings().first()
            if row is None or row["data"].get("state") in {"succeeded", "failed", "cancelled", "delivered"}:
                raise PlatformError("LEASE_NOT_AVAILABLE", 409)
            result = await db.execute(update(t.automation).where(t.automation.c.id == ident,
                t.automation.c.tenant_id == context.tenant_id, t.automation.c.user_id == context.initiator_user_id,
                or_(t.automation.c.lease_until.is_(None), t.automation.c.lease_until < now()),
            ).values(claim_token=token, lease_until=now() + timedelta(seconds=seconds), revision=t.automation.c.revision + 1))
            if result.rowcount != 1:
                raise PlatformError("LEASE_NOT_AVAILABLE", 409)
        return token

    async def complete_claim(self, context, ident, token, payload):
        async with self.engine.begin() as db:
            await self.assert_active(db, context)
            result = await db.execute(update(t.automation).where(t.automation.c.id == ident,
                t.automation.c.tenant_id == context.tenant_id, t.automation.c.user_id == context.initiator_user_id,
                t.automation.c.claim_token == token, t.automation.c.lease_until > now(),
            ).values(data=payload, claim_token=None, lease_until=None, revision=t.automation.c.revision + 1))
            if result.rowcount != 1:
                raise PlatformError("LEASE_LOST", 409)

    async def reserve_upload(self, context, document_id, size):
        if isinstance(size, bool) or size < 1:
            raise PlatformError("INVALID_UPLOAD_SIZE", 422)
        async with self.engine.begin() as db:
            await self.assert_active(db, context)
            policy, _, _ = await self.quota._policy(db, context)
            if size > policy.max_file_bytes:
                raise PlatformError("FILE_QUOTA_EXCEEDED", 413)
            subject = "user:" + context.billing_subject_id
            await insert_once(db, t.subjects, dict(tenant_id=context.tenant_id, subject=subject,
                active_calls=0, stored_bytes=0, reserved_bytes=0))
            changed = await db.execute(update(t.subjects).where(t.subjects.c.tenant_id == context.tenant_id,
                t.subjects.c.subject == subject, t.subjects.c.stored_bytes + t.subjects.c.reserved_bytes + size <= policy.storage_bytes,
            ).values(reserved_bytes=t.subjects.c.reserved_bytes + size))
            if changed.rowcount != 1:
                raise PlatformError("STORAGE_QUOTA_EXCEEDED", 413)
            await db.execute(insert(t.automation).values(id="upload:" + document_id, tenant_id=context.tenant_id,
                user_id=context.initiator_user_id, kind="upload", revision=1, data={"bytes": size, "state": "reserved"}))

    async def settle_upload(self, context, document_id, *, stored):
        async with self.engine.begin() as db:
            row = (await db.execute(select(t.automation).where(t.automation.c.id == "upload:" + document_id,
                t.automation.c.tenant_id == context.tenant_id, t.automation.c.user_id == context.initiator_user_id,
            ).with_for_update())).mappings().first()
            if not row:
                return
            state = row["data"]["state"]
            if state == ("stored" if stored else "released"):
                return
            amount = row["data"]["bytes"]
            if state == "reserved":
                values = {"reserved_bytes": t.subjects.c.reserved_bytes - amount}
                if stored:
                    values["stored_bytes"] = t.subjects.c.stored_bytes + amount
            elif state == "stored" and not stored:
                values = {"stored_bytes": t.subjects.c.stored_bytes - amount}
            else:
                raise PlatformError("UPLOAD_SETTLEMENT_CONFLICT", 409)
            await db.execute(update(t.subjects).where(t.subjects.c.tenant_id == context.tenant_id,
                t.subjects.c.subject == "user:" + context.billing_subject_id).values(**values))
            changed = await db.execute(update(t.automation).where(t.automation.c.id == row["id"],
                t.automation.c.revision == row["revision"]).values(
                data={"bytes": amount, "state": "stored" if stored else "released"}, revision=row["revision"] + 1))
            if changed.rowcount != 1:
                raise PlatformError("UPLOAD_SETTLEMENT_CONFLICT", 409)
