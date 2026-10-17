"""Persisted resource policy and server-only provider references."""

import os

from ..access import ResourceAccessPolicyBase, ResourceKind, ResourcePermission, ResourceRef
from ..storage import ChatModelConfig, CredentialRecord
from ._contracts import PlatformError

PLATFORM_PROVIDER_ID = "vin-platform-openai"
PLATFORM_KEY_REFERENCE = "vin:platform-openai"


async def resource_context(service, user_id):
    from ._context import execution_context
    context = execution_context.get()
    return context if context is not None and context.initiator_user_id == user_id else await service.context(user_id)


def reference_platform_key(data):
    """Prevent legacy console code from copying the shared key into user data."""
    key = os.getenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", "").strip()
    if os.getenv("VIN_PLATFORM_ENABLED", "false").lower() == "true" and key and data.get("api_key") == key:
        return {**data, "api_key": "server-managed", "secret_ref": PLATFORM_KEY_REFERENCE}
    return data


def hydrate_platform_credential(record):
    """Resolve an opaque reference only for provider construction, never a DTO."""
    if record.data.get("secret_ref") != PLATFORM_KEY_REFERENCE:
        return record
    key = os.getenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", "").strip()
    if not key:
        raise PlatformError("PROVIDER_NOT_CONFIGURED", 503)
    return record.model_copy(update={"data": {**record.data, "api_key": key}})


class PersistedResourcePolicy(ResourceAccessPolicyBase):
    def __init__(self, service):
        self.service = service

    async def list_accessible(self, viewer_id, kind, storage):
        context = await resource_context(self.service, viewer_id)
        rows = await self.service.catalog(context, str(kind), "execute" if kind == ResourceKind.CREDENTIAL else "bind")
        return [ResourceRef(kind=kind, owner_id=r["owner_id"], resource_id=r["resource_id"],
            permission=ResourcePermission.READ) for r in rows if r["owner_id"] != viewer_id]


async def platform_model_config(service, user_id):
    """Callable C03 for the console/Studio consumer; it never persists a key."""
    context = await resource_context(service, user_id)
    policy, _ = await service.quota.policy(context)
    entries = await service.catalog(context, "credential", "execute")
    entry = next((r for r in entries if r["resource_id"] == PLATFORM_PROVIDER_ID), None)
    models = [name for name in policy.models if entry and name in entry["model_names"]]
    if not models:
        raise PlatformError("MODEL_NOT_ENTITLED", 403)
    return ChatModelConfig(type="openai_credential", credential_id=PLATFORM_PROVIDER_ID,
        model=models[0], parameters={"max_tokens": policy.max_output_tokens})


async def resolve_platform_credential(service, user_id, credential_id):
    context = await resource_context(service, user_id)
    entries = await service.catalog(context, "credential", "execute")
    entry = next((r for r in entries if r["resource_id"] == credential_id), None)
    if context.role == "VIN_USER" and entry is None:
        raise PlatformError("RESOURCE_NOT_ENTITLED", 403)
    if credential_id != PLATFORM_PROVIDER_ID:
        return None
    if entry is None:
        raise PlatformError("RESOURCE_NOT_ENTITLED", 403)
    return hydrate_platform_credential(CredentialRecord(id=credential_id, user_id=entry["owner_id"],
        data={"type": "openai_credential", "name": entry["name"], "api_key": "server-managed",
              "secret_ref": PLATFORM_KEY_REFERENCE,
              **({"base_url": os.environ["WORKFORCE_PLATFORM_OPENAI_BASE_URL"]}
                 if os.getenv("WORKFORCE_PLATFORM_OPENAI_BASE_URL") else {})}))


async def catalog_records(service, user_id, kind, permission="view"):
    """Existing library pages/runtime use the same owner/version authority."""
    context = await resource_context(service, user_id)
    rows = []
    for entry in await service.catalog(context, kind, permission):
        try:
            _, record = await service.resolve_catalog(context, kind, entry["resource_id"], permission=permission)
        except PlatformError as exc:
            if exc.code == "RESOURCE_REVOKED":
                continue
            raise
        rows.append((entry, record))
    return rows
