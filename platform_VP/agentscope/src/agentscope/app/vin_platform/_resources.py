"""Persisted resource policy and server-only provider references."""

import os

from ..access import ResourceAccessPolicyBase, ResourceKind, ResourcePermission, ResourceRef
from ..storage import ChatModelConfig, CredentialRecord
from ._contracts import PlatformError

PLATFORM_PROVIDER_ID = "vin-platform-openai"
PLATFORM_KEY_REFERENCE = "vin:platform-openai"
# Name of the per-user copies of the platform key that the pre-Vin console
# wrote (``_workforce_console._platform_credential``).
LEGACY_PLATFORM_COPY_NAME = "Model của platform"


def _is_owned(record, user_id):
    return bool(record and record.user_id == user_id and record.id != PLATFORM_PROVIDER_ID
                and not record.data.get("secret_ref"))


def is_platform_copy(record):
    """A legacy per-user copy of the platform key: read-only for its owner."""
    platform_key = os.getenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", "").strip()
    return bool(record and (record.data.get("name") == LEGACY_PLATFORM_COPY_NAME
                            or (platform_key and record.data.get("api_key") == platform_key)))


def _is_personal(record, user_id):
    """A provider the customer added with their own key.

    Legacy copies of the platform key are owned by the user too, but they
    spend the platform's account, so they keep the platform token quota.
    """
    return _is_owned(record, user_id) and not is_platform_copy(record)


async def _owned_record(service, user_id, credential_id):
    if credential_id == PLATFORM_PROVIDER_ID:
        return None
    load = getattr(service.storage, "get_credential", None)
    return await load(user_id, credential_id) if load else None


async def is_private_credential(service, user_id, credential_id):
    """Owner-isolated key: needs no platform catalog entitlement."""
    return _is_owned(await _owned_record(service, user_id, credential_id), user_id)


async def is_personal_credential(service, user_id, credential_id):
    """Customer's own provider account: also outside the platform token quota."""
    return _is_personal(await _owned_record(service, user_id, credential_id), user_id)


async def personal_model_config(storage, user_id, model=None):
    """The customer's newest own chat provider, or None when they have none.

    A key the customer adds outranks the shared platform provider, so the
    Leader, Builder and team members run on it instead of the platform quota.
    """
    from ...credential import CredentialFactory
    load = getattr(storage, "list_credentials", None)
    records = [r for r in (await load(user_id) if load else []) if _is_personal(r, user_id)]
    for record in sorted(records, key=lambda r: str(r.created_at or ""), reverse=True):
        try:
            cards = CredentialFactory.from_dict(record.data).list_models()
        except Exception:  # not a chat provider (or an unknown type)
            continue
        names = [c.name for c in cards if c.status == "active"] or [c.name for c in cards]
        chosen = model or os.getenv("WORKFORCE_MODEL_NAME", "").strip() or (names[0] if names else "")
        if chosen:
            return ChatModelConfig(type=str(record.data["type"]), credential_id=record.id,
                                   model=chosen, parameters={})
    return None


async def prefer_personal_model(storage, user_id, config):
    """Swap a session's shared platform provider for the user's own key.

    Sessions copy their model config when they are created, so tickets,
    members and pack agents made before the user added a key still point at
    the platform provider. Runtime re-checks it here.
    """
    from . import enabled
    if not enabled() or config is None or config.credential_id != PLATFORM_PROVIDER_ID:
        return config
    personal = await personal_model_config(storage, user_id)
    if personal is None:
        return config
    if personal.type == config.type:
        personal = personal.model_copy(update={"model": config.model})
    return personal.model_copy(update={"parameters": dict(config.parameters)})


async def resource_context(service, user_id):
    from ._context import execution_context
    context = execution_context.get()
    return context if context is not None and context.initiator_user_id == user_id else await service.context(user_id)


def reference_platform_key(data):
    """Prevent legacy console code from copying the shared key into user data."""
    key = os.getenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", "").strip()
    from . import enabled
    if enabled() and key and data.get("api_key") == key:
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
    if credential_id != PLATFORM_PROVIDER_ID:
        # Personal keys use the normal owner/grant boundary, not the shared
        # platform provider's catalog entitlement.
        return None
    context = await resource_context(service, user_id)
    entries = await service.catalog(context, "credential", "execute")
    entry = next((r for r in entries if r["resource_id"] == credential_id), None)
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
