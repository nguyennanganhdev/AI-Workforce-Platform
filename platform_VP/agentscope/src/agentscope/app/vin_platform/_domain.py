"""Account-link and case adapter. All URLs are admin-registered trust anchors."""

import base64
import hashlib
import hmac
import secrets
import json
import time
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from . import _tables as t
from ._contracts import DomainProvider, PlatformError
from ._service import aware, digest, now


def validate_url(url):
    parsed = urlsplit(url)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if not parsed.netloc or parsed.username or parsed.password or parsed.fragment or (
        parsed.scheme != "https" and not (parsed.scheme == "http" and local)
    ):
        raise PlatformError("INVALID_TRUST_ENDPOINT", 422)
    return parsed


class DomainAdapter:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def safe_snapshot(ident, snapshot):
        """Never persist/publish Domain signed photo URLs in Platform DTOs."""
        def photos(items):
            from uuid import UUID
            return [{"id": str(UUID(p["id"])), "name": p.get("name", ""),
                "url": "/service-cases/" + ident + "/photos/" + str(UUID(p["id"]))} for p in items]
        result = {**snapshot}
        for key in ("photos", "result_photos"):
            if key in result:
                result[key] = photos(result[key])
        if result.get("resolution"):
            result["resolution"] = {**result["resolution"], "photos": photos(result["resolution"].get("photos", []))}
        return result

    async def exchange(self, method, url, *, raw=False, **kwargs):
        validate_url(url)
        async def send(client):
            response = await client.request(method, url, follow_redirects=False, **kwargs)
            if not 200 <= response.status_code < 300:
                if response.status_code == 401:
                    raise PlatformError("DOMAIN_LINK_EXPIRED", 403)
                if response.status_code == 403:
                    raise PlatformError("DOMAIN_PERMISSION_REVOKED", 403)
                raise PlatformError("DOMAIN_UNAVAILABLE" if response.status_code >= 500 else "DOMAIN_REQUEST_REJECTED",
                    503 if response.status_code >= 500 else 409, upstream_status=response.status_code)
            if raw:
                if len(response.content) > 10 * 1024 * 1024:
                    raise PlatformError("DOMAIN_FILE_TOO_LARGE", 413)
                return {"content": response.content, "content_type": response.headers.get("content-type", "application/octet-stream")}
            return response.json()
        if self.service.http_client is not None:
            return await send(self.service.http_client)
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            try:
                return await send(client)
            except (httpx.HTTPError, ValueError) as exc:
                raise PlatformError("DOMAIN_OUTCOME_UNKNOWN", 503) from exc

    async def configure(self, context, provider: DomainProvider):
        self.service.admin(context)
        endpoints = [validate_url(getattr(provider, name)) for name in (
            "issuer", "authorization_url", "token_url", "api_base_url", "redirect_uri")]
        if len({(u.scheme, u.netloc) for u in endpoints[:4]}) != 1:
            raise PlatformError("DOMAIN_ENDPOINT_ORIGIN_MISMATCH", 422)
        await self.service.secret_get(context.tenant_id, provider.client_secret_ref, "domain-client")
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            from ._quota import insert_once
            await insert_once(db, t.providers, {"tenant_id": context.tenant_id, "id": provider.id, "data": provider.model_dump()})
            await db.execute(update(t.providers).where(t.providers.c.tenant_id == context.tenant_id,
                t.providers.c.id == provider.id).values(data=provider.model_dump()))
            await self.service.audit(db, context, "domain.configured", provider.id)

    async def provider(self, context, ident):
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            row = (await db.execute(select(t.providers.c.data).where(t.providers.c.tenant_id == context.tenant_id,
                t.providers.c.id == ident))).scalar_one_or_none()
        if not row or not row["active"]:
            raise PlatformError("DOMAIN_NOT_CONFIGURED", 503)
        return DomainProvider.model_validate(row)

    async def start(self, context, provider_id):
        provider = await self.provider(context, provider_id)
        verifier, state = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        ident = uuid4().hex
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        async with self.service.engine.begin() as db:
            await db.execute(insert(t.link_transactions).values(id=ident, tenant_id=context.tenant_id,
                user_id=context.initiator_user_id, provider_id=provider_id, state_hash=digest(state),
                verifier=self.service.cipher().encrypt(verifier.encode()).decode(), status="pending",
                expires_at=now() + timedelta(minutes=5)))
        params = {"client_id": provider.client_id, "redirect_uri": provider.redirect_uri, "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256", "response_type": "code",
            "platform_user_id": context.initiator_user_id, "scope": " ".join(provider.scopes)}
        return {"transaction_id": ident, "authorization_url": provider.authorization_url + "?" + urlencode(params)}

    async def complete(self, context, provider_id, transaction_id, state, code):
        provider = await self.provider(context, provider_id)
        async with self.service.engine.begin() as db:
            row = (await db.execute(select(t.link_transactions).where(t.link_transactions.c.id == transaction_id,
                t.link_transactions.c.tenant_id == context.tenant_id, t.link_transactions.c.user_id == context.initiator_user_id,
                t.link_transactions.c.provider_id == provider_id).with_for_update())).mappings().first()
            if not row or row["status"] != "pending" or aware(row["expires_at"]) <= now() or not hmac.compare_digest(row["state_hash"], digest(state)):
                raise PlatformError("LINK_TRANSACTION_INVALID", 409)
            changed = await db.execute(update(t.link_transactions).where(t.link_transactions.c.id == transaction_id,
                t.link_transactions.c.status == "pending").values(status="exchanging"))
            if changed.rowcount != 1:
                raise PlatformError("LINK_TRANSACTION_INVALID", 409)
        verifier = self.service.cipher().decrypt(row["verifier"].encode()).decode()
        secret = await self.service.secret_get(context.tenant_id, provider.client_secret_ref, "domain-client")
        result = await self.exchange("POST", provider.token_url, json={"grant_type": "authorization_code",
            "client_id": provider.client_id, "client_secret": secret, "code": code, "code_verifier": verifier,
            "redirect_uri": provider.redirect_uri, "platform_user_id": context.initiator_user_id})
        if result.get("issuer") != provider.issuer or result.get("platform_user_id") != context.initiator_user_id or not result.get("subject") or not result.get("link_token"):
            raise PlatformError("DOMAIN_IDENTITY_INVALID", 403)
        if not set(result.get("scopes", [])) <= set(provider.scopes):
            raise PlatformError("DOMAIN_SCOPE_INVALID", 403)
        ident, secret_ref = uuid4().hex, uuid4().hex
        encrypted = self.service.cipher().encrypt(result["link_token"].encode()).decode()
        try:
            async with self.service.engine.begin() as db:
                prior = (await db.execute(select(t.links).where(t.links.c.tenant_id == context.tenant_id,
                    t.links.c.provider_id == provider_id, t.links.c.issuer == provider.issuer,
                    t.links.c.subject == result["subject"]).with_for_update())).mappings().first()
                if prior and prior["user_id"] != context.initiator_user_id:
                    raise PlatformError("DOMAIN_SUBJECT_ALREADY_LINKED", 409)
                await db.execute(insert(t.secrets).values(id=secret_ref, tenant_id=context.tenant_id,
                    purpose="domain-link", ciphertext=encrypted, active=True))
                data = {"domain_link_id": result["link_id"], "consent_version": result.get("consent_version", "1")}
                if prior:
                    ident = prior["id"]
                    await db.execute(update(t.secrets).where(t.secrets.c.id == prior["secret_ref"]).values(active=False))
                    await db.execute(update(t.links).where(t.links.c.id == ident).values(status="active",
                        secret_ref=secret_ref, scopes=result["scopes"], data=data, revision=prior["revision"] + 1))
                else:
                    await db.execute(insert(t.links).values(id=ident, tenant_id=context.tenant_id,
                        user_id=context.initiator_user_id, provider_id=provider_id, issuer=provider.issuer,
                        subject=result["subject"], status="active", secret_ref=secret_ref,
                        scopes=result["scopes"], revision=1, data=data))
                await db.execute(update(t.link_transactions).where(t.link_transactions.c.id == transaction_id).values(status="completed", verifier=""))
                await self.service.audit(db, context, "domain.linked", ident, provider_id=provider_id)
        except IntegrityError as exc:
            raise PlatformError("DOMAIN_SUBJECT_ALREADY_LINKED", 409) from exc
        return {"id": ident, "provider_id": provider_id, "status": "active"}

    async def link(self, context, link_id, *, active=True):
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            row = (await db.execute(select(t.links).where(t.links.c.id == link_id,
                t.links.c.tenant_id == context.tenant_id, t.links.c.user_id == context.initiator_user_id))).mappings().first()
        if not row or (active and row["status"] != "active"):
            raise PlatformError("DOMAIN_LINK_REQUIRED", 403)
        return dict(row)

    async def request(self, context, link_id, method, path, *, payload=None, idempotency_key=None, raw=False):
        link = await self.link(context, link_id)
        provider = await self.provider(context, link["provider_id"])
        if provider.environment != context.environment:
            raise PlatformError("SANDBOX_UNAVAILABLE" if context.environment == "sandbox" else "DOMAIN_ENVIRONMENT_MISMATCH", 403)
        credential = await self.service.secret_get(context.tenant_id, link["secret_ref"], "domain-link")
        client_secret = await self.service.secret_get(context.tenant_id, provider.client_secret_ref, "domain-client")
        grant = await self.exchange("POST", provider.api_base_url.rstrip("/") + "/grants", json={
            "client_id": provider.client_id, "client_secret": client_secret, "link_token": credential})
        headers = {"Authorization": "Bearer " + grant["access_token"], "X-Correlation-ID": idempotency_key or uuid4().hex}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if not path.startswith("/") or ".." in path or ":" in path:
            raise PlatformError("INVALID_DOMAIN_PATH", 422)
        return await self.exchange(method, provider.api_base_url.rstrip("/") + path, headers=headers, raw=raw,
            **({"json": payload} if payload is not None else {}))

    async def revoke(self, context, link_id):
        link = await self.link(context, link_id, active=False)
        if link["status"] == "revoked":
            return
        # Local revoke is authoritative for new work even if Domain is down.
        async with self.service.engine.begin() as db:
            await db.execute(update(t.links).where(t.links.c.id == link_id).values(status="revoke_pending", revision=t.links.c.revision + 1))
            await self.service.audit(db, context, "domain.unlink_requested", link_id)
        provider = await self.provider(context, link["provider_id"])
        credential = await self.service.secret_get(context.tenant_id, link["secret_ref"], "domain-link")
        secret = await self.service.secret_get(context.tenant_id, provider.client_secret_ref, "domain-client")
        await self.exchange("POST", provider.api_base_url.rstrip("/") + "/revoke", json={
            "client_id": provider.client_id, "client_secret": secret, "link_token": credential})
        async with self.service.engine.begin() as db:
            await db.execute(update(t.links).where(t.links.c.id == link_id).values(status="revoked"))
            await db.execute(update(t.secrets).where(t.secrets.c.id == link["secret_ref"]).values(active=False))

    async def create_case(self, context, command):
        await self.link(context, command.link_id)
        payload_hash = digest(command.model_dump(exclude={"idempotency_key"}))
        ident = uuid4().hex
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context)
            from ._quota import insert_once
            await insert_once(db, t.cases, dict(id=ident, tenant_id=context.tenant_id,
                user_id=context.initiator_user_id, link_id=command.link_id, idempotency_key=command.idempotency_key,
                payload_hash=payload_hash, state="pending", data={"request": command.request}, revision=1))
            row = (await db.execute(select(t.cases).where(t.cases.c.tenant_id == context.tenant_id,
                t.cases.c.user_id == context.initiator_user_id, t.cases.c.idempotency_key == command.idempotency_key))).mappings().one()
            ident = row["id"]
            if row["payload_hash"] != payload_hash:
                raise PlatformError("IDEMPOTENCY_CONFLICT", 409)
            if row["state"] == "applied":
                return {"id": ident, "state": "applied", "domain": row["data"]["domain"]}
        # Request ID is persisted before IO. Lost responses safely retry the same Domain command.
        result = await self.request(context, command.link_id, "POST", "/requests", payload={
            "platform_case_id": ident, "platform_workflow_id": ident, "request": command.request},
            idempotency_key=command.idempotency_key)
        result = self.safe_snapshot(ident, result)
        async with self.service.engine.begin() as db:
            await db.execute(update(t.cases).where(t.cases.c.id == ident).values(state="applied",
                data={"request": command.request, "domain": result}, revision=t.cases.c.revision + 1))
        return {"id": ident, "state": "applied", "domain": result}

    async def get_case(self, context, ident, refresh=False):
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            row = (await db.execute(select(t.cases).where(t.cases.c.id == ident,
                t.cases.c.tenant_id == context.tenant_id, t.cases.c.user_id == context.initiator_user_id))).mappings().first()
        if not row:
            raise PlatformError("CASE_NOT_FOUND", 404)
        await self.link(context, row["link_id"])
        result = dict(row)
        result.pop("payload_hash", None)
        if refresh and row["state"] == "applied":
            domain_id = row["data"]["domain"]["id"]
            from uuid import UUID
            canonical = self.safe_snapshot(ident, await self.request(context, row["link_id"], "GET", "/requests/" + str(UUID(domain_id))))
            result["data"] = {**row["data"], "domain": canonical}
            async with self.service.engine.begin() as db:
                await db.execute(update(t.cases).where(t.cases.c.id == ident).values(data=result["data"], revision=t.cases.c.revision + 1))
            if canonical.get("projection_hash"):
                # Acknowledgement follows durable SQL projection, never HTTP
                # acceptance or a model's claim that publication succeeded.
                await self.request(context, row["link_id"], "POST", "/requests/" + str(UUID(domain_id)) + "/projection-acks",
                    payload={"canonical_version": canonical["canonical_version"], "content_hash": canonical["projection_hash"]})
        return result

    async def decide(self, context, intent):
        case = await self.get_case(context, intent.case_id)
        if intent.action not in {"confirm", "reopen", "plan-decision", "work-approval", "cancel", "reschedule"}:
            raise PlatformError("ACTION_NOT_ENTITLED", 403)
        body = {"action": intent.action, "expected_version": intent.expected_version, "payload": intent.payload}
        fingerprint = digest(body)
        async with self.service.engine.begin() as db:
            from ._quota import insert_once
            await insert_once(db, t.commands, dict(id=uuid4().hex, tenant_id=context.tenant_id,
                user_id=context.initiator_user_id, case_id=intent.case_id, idempotency_key=intent.idempotency_key,
                payload_hash=fingerprint, state="pending", data=body))
            row = (await db.execute(select(t.commands).where(t.commands.c.tenant_id == context.tenant_id,
                t.commands.c.user_id == context.initiator_user_id, t.commands.c.case_id == intent.case_id,
                t.commands.c.idempotency_key == intent.idempotency_key))).mappings().one()
            if row["payload_hash"] != fingerprint:
                raise PlatformError("IDEMPOTENCY_CONFLICT", 409)
            if row["state"] == "applied":
                return row["data"]["result"]
        from uuid import UUID
        request_id = str(UUID(case["data"]["domain"]["id"]))
        link = await self.link(context, case["link_id"])
        provider = await self.provider(context, link["provider_id"])
        secret = await self.service.secret_get(context.tenant_id, provider.client_secret_ref, "domain-client")
        proof = {"client_id": provider.client_id, "platform_user_id": context.initiator_user_id,
            "domain_link_id": link["data"]["domain_link_id"], "request_id": request_id,
            "platform_case_id": intent.case_id, "source_event_id": row["id"], **body,
            "expires_at": int(time.time()) + 300}
        signature = hmac.new(hashlib.sha256(secret.encode()).digest(),
            json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
        result = await self.request(context, case["link_id"], "POST", "/requests/" + request_id + "/decisions",
            payload={**body, "platform_case_id": intent.case_id, "source_event_id": row["id"],
                "intent_proof": proof, "intent_signature": signature},
            idempotency_key=intent.idempotency_key)
        async with self.service.engine.begin() as db:
            await db.execute(update(t.commands).where(t.commands.c.id == row["id"]).values(state="applied", data={**body, "result": result}))
        return result

    async def materialize(self, context, ident, category_id, expected_version, idempotency_key):
        case = await self.get_case(context, ident)
        from uuid import UUID
        return await self.request(context, case["link_id"], "POST", "/requests/" + str(UUID(case["data"]["domain"]["id"])) + "/tickets",
            payload={"category_id": str(UUID(category_id)), "expected_version": expected_version}, idempotency_key=idempotency_key)

    async def ticket_grant(self, context, ident, ticket_id, tools):
        """Internal runtime hook; never return this payload to a public DTO."""
        case = await self.get_case(context, ident)
        from uuid import UUID
        return await self.request(context, case["link_id"], "POST", "/requests/" + str(UUID(case["data"]["domain"]["id"])) + "/ticket-grants",
            payload={"ticket_id": str(UUID(ticket_id)), "tools": tools})

    async def photo(self, context, ident, file_id):
        case = await self.get_case(context, ident)
        from uuid import UUID
        return await self.request(context, case["link_id"], "GET", "/requests/" + str(UUID(case["data"]["domain"]["id"]))
            + "/photos/" + str(UUID(file_id)), raw=True)

    async def eval_fixtures(self, context, link_id, run_id, count=5):
        if context.environment != "sandbox":
            raise PlatformError("SANDBOX_UNAVAILABLE", 403)
        return await self.request(context, link_id, "POST", "/eval-fixtures", payload={"run_id": run_id, "count": count})

    async def cleanup_eval(self, context, link_id, run_id):
        if context.environment != "sandbox":
            raise PlatformError("SANDBOX_UNAVAILABLE", 403)
        return await self.request(context, link_id, "POST", "/eval-fixtures/cleanup", payload={"run_id": run_id})

    async def sync_events(self, context, ident):
        from sqlalchemy import func
        from ._contracts import CaseEvent
        case = await self.get_case(context, ident)
        async with self.service.engine.begin() as db:
            cursor = (await db.execute(select(func.max(t.events.c.sequence)).where(t.events.c.tenant_id == context.tenant_id,
                t.events.c.case_id == ident))).scalar_one_or_none() or 0
        from uuid import UUID
        page = await self.request(context, case["link_id"], "GET", "/requests/" + str(UUID(case["data"]["domain"]["id"])) + "/events?after=" + str(cursor))
        events = [CaseEvent.model_validate(item) for item in page["items"]]
        if any(e.case_id != ident or e.audience != "customer" or e.sequence != cursor + i + 1 for i, e in enumerate(events)):
            raise PlatformError("SYNC_PENDING", 409)
        async with self.service.engine.begin() as db:
            await self.service.assert_active(db, context, require_eligible=False)
            await db.execute(select(t.cases.c.id).where(t.cases.c.id == ident).with_for_update())
            from ._quota import insert_once
            for event in events:
                data = event.model_dump(mode="json")
                await insert_once(db, t.events, {"tenant_id": context.tenant_id, "case_id": ident,
                    "sequence": event.sequence, "event_id": event.event_id, "audience": "customer", "data": data})
                existing = (await db.execute(select(t.events.c.data).where(t.events.c.tenant_id == context.tenant_id,
                    t.events.c.case_id == ident, t.events.c.sequence == event.sequence))).scalar_one()
                if existing != data:
                    raise PlatformError("EVENT_REPLAY_CONFLICT", 409)
        applied = events[-1].sequence if events else cursor
        return {"last_sequence": page["last_sequence"], "applied_sequence": applied,
            "sync_status": "sync_pending" if page["has_more"] or page["last_sequence"] > applied else "applied",
            "synced_at": now().isoformat(), "has_more": page["has_more"], "canonical_version": page["canonical_version"]}
