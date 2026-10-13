"""Ticket-bound, bidirectional asset upload and download service."""

from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from ..contracts import (
    ActorContext,
    AssetDownloadGrant,
    AssetOrigin,
    AssetProjection,
    AssetStatus,
    AssetUploadSession,
    CustomerAssetUploadRequest,
    PartnerAudience,
    PartnerOperation,
    ProviderAssetUploadRequest,
    Scope,
    VerifiedProviderContext,
)
from ..execution._utils import ExecutionError, owner, value

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})


def _safe_name(value_: str) -> str:
    name = value_.replace("\\", "/").rsplit("/", 1)[-1].strip()[:512]
    if (
        not name
        or name in {".", ".."}
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise ExecutionError("ASSET_FILENAME_INVALID", 422)
    return name


def _audience(record: dict[str, Any]) -> PartnerAudience:
    return PartnerAudience(
        partner_client_id=record["partner_client_id"],
        external_user_id=record["external_user_id"],
        external_ticket_id=record["external_ticket_id"],
        external_conversation_id=record["external_conversation_id"],
    )


def _scope(record: dict[str, Any]) -> Scope:
    return Scope(
        tenant_id=record["tenant_id"],
        domain_id=record["domain_id"],
        area_id=record["area_id"],
        manager_account_id=record["manager_account_id"],
    )


class WorkforceAssetService:
    """Own private objects while exposing only short-lived signed URLs."""

    def __init__(
        self,
        repository: Any,
        blob_store: Any,
        routing: Any,
        identity: Any,
        operations: Any,
        *,
        clock: Any = lambda: datetime.now(UTC),
        ids: Any = lambda: uuid4().hex,
        upload_ttl_seconds: int = 900,
        download_ttl_seconds: int = 300,
    ) -> None:
        self.repo = repository
        self.blob_store = blob_store
        self.routing = routing
        self.identity = identity
        self.operations = operations
        self.clock = clock
        self.ids = ids
        self.upload_ttl_seconds = upload_ttl_seconds
        self.download_ttl_seconds = download_ttl_seconds

    @staticmethod
    def _validate_file(content_type: str, byte_size: int) -> None:
        if content_type.lower() not in ALLOWED_IMAGE_TYPES:
            raise ExecutionError("ASSET_CONTENT_TYPE_UNSUPPORTED", 422)
        if byte_size < 1 or byte_size > 20 * 1024 * 1024:
            raise ExecutionError("ASSET_SIZE_INVALID", 422)

    @staticmethod
    def _require_customer(actor: ActorContext) -> None:
        if (
            actor.kind != "partner"
            or actor.credential_purpose != "customer_api"
            or actor.external_user_id is None
        ):
            raise ExecutionError("AUTHORIZATION_DENIED", 403)

    async def create_customer_upload(self, actor_: Any, request_: Any) -> Any:
        actor = ActorContext.model_validate(actor_)
        request = CustomerAssetUploadRequest.model_validate(request_)
        self._require_customer(actor)
        if actor.external_user_id != request.external_user_id:
            raise ExecutionError("AUTHORIZATION_DENIED", 403)
        self._validate_file(request.content_type, request.byte_size)
        audience = PartnerAudience(
            partner_client_id=actor.partner_client_id,
            external_user_id=request.external_user_id,
            external_ticket_id=request.external_ticket_id,
            external_conversation_id=request.external_conversation_id,
            residence_id=request.residence_id,
        )
        route = await self.routing.resolve(
            actor,
            {
                "external_management_ref": request.external_management_ref,
                "external_user_id": request.external_user_id,
                "residence_id": request.residence_id,
            },
        )
        async with self.repo.transaction() as uow:
            await self.identity.check_scope_active(route.scope, uow)
            await self.routing.revalidate(
                route.scope,
                route.route_id,
                route.route_revision,
                actor,
                audience,
                PartnerOperation.SUBMIT_REQUEST,
                uow,
            )
            return await self._create(
                route.scope,
                audience,
                AssetOrigin.CUSTOMER,
                request.filename,
                request.content_type,
                request.byte_size,
                uow,
            )

    async def create_provider_upload(self, principal_: Any, request_: Any) -> Any:
        principal = VerifiedProviderContext.model_validate(principal_)
        request = ProviderAssetUploadRequest.model_validate(request_)
        self._validate_file(request.content_type, request.byte_size)
        async with self.operations.repo.transaction() as uow:
            operation = await self.operations.resolve(
                value(principal), request.model_dump(mode="python"), uow
            )
            if operation is None:
                raise ExecutionError("OPERATION_NOT_FOUND", 404)
            audience = PartnerAudience.model_validate(operation["audience_ref"])
            return await self._create(
                Scope.model_validate(operation["scope"]),
                audience,
                AssetOrigin.PROVIDER,
                request.filename,
                request.content_type,
                request.byte_size,
                uow,
                workflow_id=operation["workflow_id"],
                operation_id=operation["id"],
                provider_integration_id=principal.provider_integration_id,
            )

    async def _create(
        self,
        scope: Scope,
        audience: PartnerAudience,
        origin: AssetOrigin,
        filename: str,
        content_type: str,
        byte_size: int,
        uow: Any,
        *,
        workflow_id: str | None = None,
        operation_id: str | None = None,
        provider_integration_id: str | None = None,
    ) -> AssetUploadSession:
        asset_id = self.ids()
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("asset clock must be timezone-aware")
        filename = _safe_name(filename)
        suffix = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
        }[content_type.lower()]
        scope_key = sha256(":".join(owner(scope).values()).encode("utf-8")).hexdigest()[
            :20
        ]
        key = f"workforce-assets/staging/{scope_key}/{now:%Y/%m}/{asset_id}.{suffix}"
        object_uri, upload_url, headers = await self.blob_store.presign_put(
            key,
            content_type=content_type.lower(),
            metadata={"asset-id": asset_id},
            expires_in=self.upload_ttl_seconds,
        )
        expires_at = now + timedelta(seconds=self.upload_ttl_seconds)
        await self.repo.insert(
            {
                "id": asset_id,
                **owner(scope),
                "origin": origin.value,
                "status": AssetStatus.PENDING_UPLOAD.value,
                "partner_client_id": audience.partner_client_id,
                "external_user_id": audience.external_user_id,
                "external_ticket_id": audience.external_ticket_id,
                "external_conversation_id": audience.external_conversation_id,
                "workflow_id": workflow_id,
                "operation_id": operation_id,
                "provider_integration_id": provider_integration_id,
                "object_uri": object_uri,
                "filename": filename,
                "content_type": content_type.lower(),
                "expected_size": byte_size,
                "actual_size": None,
                "upload_expires_at": expires_at,
                "created_at": now,
                "updated_at": now,
            },
            uow,
        )
        return AssetUploadSession(
            asset_id=asset_id,
            upload_url=upload_url,
            required_headers=headers,
            expires_at=expires_at,
            complete_url=f"/workforce/v1/{'partner' if origin == AssetOrigin.CUSTOMER else 'provider'}/assets/{asset_id}/complete",
        )

    async def complete_customer(
        self,
        actor_: Any,
        asset_id: str,
        *,
        external_user_id: str | None = None,
        external_conversation_id: str | None = None,
        external_ticket_id: str | None = None,
    ) -> Any:
        actor = ActorContext.model_validate(actor_)
        self._require_customer(actor)
        async with self.repo.transaction() as uow:
            record = await self.repo.get(asset_id, uow)
            if record is None:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if (
                record["origin"] != AssetOrigin.CUSTOMER.value
                or record["partner_client_id"] != actor.partner_client_id
                or record["external_user_id"] != actor.external_user_id
                or (
                    external_user_id is not None
                    and record["external_user_id"] != external_user_id
                )
                or (
                    external_conversation_id is not None
                    and record["external_conversation_id"] != external_conversation_id
                )
                or (
                    external_conversation_id is not None
                    and record["external_ticket_id"] != external_ticket_id
                )
            ):
                raise ExecutionError("AUTHORIZATION_DENIED", 403)
            await self.identity.check_scope_active(
                _scope(record),
                uow,
            )
        return await self._complete(record["id"])

    async def complete_provider(self, principal_: Any, asset_id: str) -> Any:
        principal = VerifiedProviderContext.model_validate(principal_)
        async with self.repo.transaction() as uow:
            record = await self.repo.get(asset_id, uow)
            if record is None:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if (
                record["origin"] != AssetOrigin.PROVIDER.value
                or record["tenant_id"] != principal.tenant_id
                or record["provider_integration_id"]
                != principal.provider_integration_id
            ):
                raise ExecutionError("AUTHORIZATION_DENIED", 403)
            await self.identity.check_scope_active(_scope(record), uow)
        return await self._complete(record["id"])

    async def _complete(self, asset_id: str) -> AssetProjection:
        staged_uri: str | None = None
        mismatch = False
        async with self.repo.transaction() as uow:
            current = await self.repo.get(asset_id, uow, lock=True)
            if current is None:
                raise ExecutionError("RESOURCE_NOT_FOUND", 404)
            if current["status"] == AssetStatus.ACTIVE.value:
                return self._projection(current)
            if current["status"] != AssetStatus.PENDING_UPLOAD.value:
                raise ExecutionError("ASSET_NOT_COMPLETABLE", 409)
            now = self.clock()
            if now > current["upload_expires_at"]:
                raise ExecutionError("ASSET_UPLOAD_SESSION_EXPIRED", 410)
            staged_uri = current["object_uri"]
            stat = await self.blob_store.stat(staged_uri)
            valid = (
                stat is not None
                and stat["byte_size"] == current["expected_size"]
                and stat["content_type"].split(";", 1)[0].lower()
                == current["content_type"]
                and stat.get("metadata", {}).get("asset-id") == current["id"]
                and await self._image_signature_matches(current)
            )
            if not valid:
                mismatch = True
                await self.repo.update(
                    current["id"],
                    {"status": AssetStatus.REJECTED.value, "updated_at": now},
                    uow,
                )
            else:
                final_key = self._final_key(staged_uri)
                final_uri = await self.blob_store.promote(
                    staged_uri,
                    final_key,
                    content_type=current["content_type"],
                    metadata={"asset-id": current["id"]},
                )
                final_record = {**current, "object_uri": final_uri}
                final_stat = await self.blob_store.stat(final_uri)
                final_valid = (
                    final_stat is not None
                    and final_stat["byte_size"] == current["expected_size"]
                    and final_stat["content_type"].split(";", 1)[0].lower()
                    == current["content_type"]
                    and final_stat.get("metadata", {}).get("asset-id") == current["id"]
                    and await self._image_signature_matches(final_record)
                )
                if not final_valid:
                    raise ExecutionError("ASSET_STORAGE_PROMOTION_FAILED", 503)
                current.update(
                    object_uri=final_uri,
                    status=AssetStatus.ACTIVE.value,
                    actual_size=final_stat["byte_size"],
                    updated_at=now,
                )
                await self.repo.update(
                    current["id"],
                    {
                        "object_uri": final_uri,
                        "status": current["status"],
                        "actual_size": current["actual_size"],
                        "updated_at": now,
                    },
                    uow,
                )
                projection = self._projection(current)
        if staged_uri is not None:
            # Finalization must remain successful if best-effort staging
            # cleanup fails; bucket lifecycle rules provide the safety net.
            with suppress(Exception):
                await self.blob_store.delete(staged_uri)
        if mismatch:
            raise ExecutionError("ASSET_UPLOAD_MISMATCH", 422)
        return projection

    @staticmethod
    def _final_key(staged_uri: str) -> str:
        marker = "/workforce-assets/staging/"
        _, found, suffix = staged_uri.partition(marker)
        if not found or not suffix:
            raise ExecutionError("ASSET_STORAGE_URI_INVALID", 500)
        return f"workforce-assets/objects/{suffix}"

    async def _image_signature_matches(self, record: dict[str, Any]) -> bool:
        async with self.blob_store.open(record["object_uri"]) as stream:
            header = await stream.read(16)
        content_type = record["content_type"]
        if content_type == "image/jpeg":
            return header.startswith(b"\xff\xd8\xff")
        if content_type == "image/png":
            return header.startswith(b"\x89PNG\r\n\x1a\n")
        if content_type == "image/gif":
            return header.startswith((b"GIF87a", b"GIF89a"))
        return (
            content_type == "image/webp"
            and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
        )

    def _projection(self, record: dict[str, Any]) -> AssetProjection:
        return AssetProjection(
            asset_id=record["id"],
            origin=record["origin"],
            status=record["status"],
            filename=record["filename"],
            content_type=record["content_type"],
            byte_size=record["actual_size"] or record["expected_size"],
            workflow_id=record["workflow_id"],
            created_at=record["created_at"],
        )

    async def bind_customer_assets(
        self,
        scope_: Any,
        audience_: Any,
        workflow_id: str,
        asset_ids: tuple[str, ...],
        uow: Any,
    ) -> None:
        scope = Scope.model_validate(scope_)
        audience = PartnerAudience.model_validate(audience_)
        for asset_id in asset_ids:
            record = await self.repo.get(asset_id, uow, lock=True)
            if record is None:
                raise ExecutionError("ASSET_NOT_FOUND", 422)
            if (
                record["status"] != AssetStatus.ACTIVE.value
                or record["origin"] != AssetOrigin.CUSTOMER.value
                or {key: record[key] for key in owner(scope)} != owner(scope)
                or _audience(record)
                != audience.model_copy(update={"residence_id": None})
                or record["workflow_id"] not in {None, workflow_id}
            ):
                raise ExecutionError("ASSET_BINDING_MISMATCH", 403)
            if record["workflow_id"] is None:
                await self.repo.update(
                    asset_id,
                    {"workflow_id": workflow_id, "updated_at": self.clock()},
                    uow,
                )

    async def customer_download(
        self,
        actor_: Any,
        asset_id: str,
        *,
        external_user_id: str | None = None,
        external_conversation_id: str | None = None,
        external_ticket_id: str | None = None,
    ) -> AssetDownloadGrant:
        actor = ActorContext.model_validate(actor_)
        self._require_customer(actor)
        async with self.repo.transaction() as uow:
            record = await self.repo.get(asset_id, uow)
            if record is not None:
                await self.identity.check_scope_active(
                    _scope(record),
                    uow,
                )
        if record is None:
            raise ExecutionError("RESOURCE_NOT_FOUND", 404)
        if (
            record["status"] != AssetStatus.ACTIVE.value
            or record["partner_client_id"] != actor.partner_client_id
            or record["external_user_id"] != actor.external_user_id
            or (
                external_user_id is not None
                and record["external_user_id"] != external_user_id
            )
            or (
                external_conversation_id is not None
                and record["external_conversation_id"] != external_conversation_id
            )
            or (
                external_conversation_id is not None
                and record["external_ticket_id"] != external_ticket_id
            )
        ):
            raise ExecutionError("AUTHORIZATION_DENIED", 403)
        return await self._download_grant(record)

    async def _download_grant(self, record: dict[str, Any]) -> AssetDownloadGrant:
        expires_at = self.clock() + timedelta(seconds=self.download_ttl_seconds)
        url = await self.blob_store.presign_get(
            record["object_uri"],
            expires_in=self.download_ttl_seconds,
            download_name=record["filename"],
        )
        return AssetDownloadGrant(
            asset_id=record["id"],
            filename=record["filename"],
            content_type=record["content_type"],
            byte_size=record["actual_size"],
            download_url=url,
            expires_at=expires_at,
        )

    async def materialize_for_provider(
        self, scope_: Any, context: Any, descriptor: Any, arguments: Any
    ) -> dict[str, Any]:
        data = deepcopy(value(arguments))
        asset_ids: list[str] = []
        for item in data.get("asset_ids", []):
            if isinstance(item, str):
                asset_ids.append(item)
        for item in data.get("attachments", []):
            if isinstance(item, str):
                asset_ids.append(item)
            elif isinstance(item, dict) and isinstance(item.get("asset_id"), str):
                asset_ids.append(item["asset_id"])
        asset_ids = list(dict.fromkeys(asset_ids))
        if not asset_ids:
            return data
        properties = value(descriptor).get("input_schema", {}).get("properties", {})
        if (
            "asset_download_v1" not in value(descriptor).get("capabilities", [])
            or "asset_downloads" not in properties
        ):
            raise ExecutionError("TOOL_ASSET_CAPABILITY_MISSING", 422)
        workflow_id = value(context).get("workflow_id")
        if not workflow_id:
            raise ExecutionError("ASSET_WORKFLOW_REQUIRED", 422)
        grants = []
        async with self.repo.transaction() as uow:
            records = []
            for asset_id in asset_ids:
                record = await self.repo.get(asset_id, uow)
                if (
                    record is None
                    or record["status"] != AssetStatus.ACTIVE.value
                    or record["origin"] != AssetOrigin.CUSTOMER.value
                    or record["workflow_id"] != workflow_id
                    or {key: record[key] for key in owner(scope_)} != owner(scope_)
                ):
                    raise ExecutionError("ASSET_BINDING_MISMATCH", 403)
                records.append(record)
        for record in records:
            grants.append((await self._download_grant(record)).model_dump(mode="json"))
        data["asset_downloads"] = grants
        return data

    async def validate_provider_event_assets(
        self, principal_: Any, envelope: Any, uow: Any
    ) -> None:
        """Reject event attachments not uploaded for the correlated operation."""
        principal = VerifiedProviderContext.model_validate(principal_)
        items = value(envelope).get("attachments") or []
        if not items:
            return
        if not isinstance(items, (list, tuple)):
            raise ExecutionError("PROVIDER_ASSET_REFERENCE_INVALID", 422)
        asset_ids = []
        for item in items:
            asset_id = item.get("asset_id") if isinstance(item, dict) else None
            if not isinstance(asset_id, str) or not asset_id:
                raise ExecutionError("PROVIDER_ASSET_REFERENCE_INVALID", 422)
            asset_ids.append(asset_id)
        if len(asset_ids) != len(set(asset_ids)):
            raise ExecutionError("PROVIDER_ASSET_REFERENCE_INVALID", 422)
        operation = await self.operations.resolve(
            value(principal), value(envelope), uow
        )
        if operation is None:
            raise ExecutionError("OPERATION_NOT_FOUND", 404)
        for asset_id in asset_ids:
            record = await self.repo.get(asset_id, uow)
            if (
                record is None
                or record["status"] != AssetStatus.ACTIVE.value
                or record["origin"] != AssetOrigin.PROVIDER.value
                or record["operation_id"] != operation["id"]
                or record["workflow_id"] != operation["workflow_id"]
                or record["provider_integration_id"]
                != principal.provider_integration_id
            ):
                raise ExecutionError("PROVIDER_ASSET_BINDING_MISMATCH", 403)


__all__ = ["ALLOWED_IMAGE_TYPES", "WorkforceAssetService"]
