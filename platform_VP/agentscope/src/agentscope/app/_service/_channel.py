# -*- coding: utf-8 -*-
"""ChannelService — stateless CRUD for channel records.

Validates, writes the record, and publishes a lifecycle notification so
every node's :class:`ChannelLifecycleDispatcher` reconciles its running
instances against storage. Holds no channel instances.
"""
import time
from datetime import datetime, timedelta

from ..._utils._common import _generate_id
from ..message_bus import MessageBus, MessageBusKeys
from ..storage import (
    ChannelRecord,
    RoutingConfig,
    SessionSettings,
    StorageBase,
)
from ..channel._base import ChannelHeartbeat, ChannelStatus
from ..channel._errors import ChannelError
from ..channel._registry import ChannelTypeRegistry


class ChannelService:
    """CRUD operations on channel records."""

    def __init__(
        self,
        storage: StorageBase,
        message_bus: MessageBus,
        type_registry: ChannelTypeRegistry,
    ) -> None:
        """Bind storage, the message bus, and the channel type registry.

        Args:
            storage (`StorageBase`): Application storage.
            message_bus (`MessageBus`): For lifecycle notifications.
            type_registry (`ChannelTypeRegistry`): Validates types and
                builds instances for the pre-create connection check.
        """
        self._storage = storage
        self._bus = message_bus
        self._types = type_registry

    async def create(
        self,
        *,
        user_id: str,
        channel_type: str,
        credentials: dict,
        platform_config: dict,
        routing: RoutingConfig,
        session: SessionSettings,
        enabled: bool = True,
        name: str | None = None,
    ) -> ChannelRecord:
        """Create a channel, rejecting a bot already bound elsewhere.

        Args:
            user_id (`str`): Owner of the channel.
            channel_type (`str`): Registered platform type id.
            name (`str | None`): Optional display name.
            credentials (`dict`): Platform credentials.
            platform_config (`dict`): Platform behaviour options.
            routing (`RoutingConfig`): Inbound routing rules.
            session (`SessionSettings`): Derived-session settings.
            enabled (`bool`): Whether to start the channel immediately.
        """
        platform_config = await self._discord_config(user_id, channel_type, platform_config, creating=True, credentials=credentials)
        from pydantic import ValidationError

        channel_cls = self._types.get(channel_type)
        if channel_cls is None:
            raise ChannelError("Loại kênh không được hỗ trợ.", 400)
        try:
            credentials = channel_cls.Credentials.model_validate(credentials).model_dump()
            platform_config = channel_cls.Config.model_validate(platform_config).model_dump()
        except ValidationError as exc:
            fields = ", ".join(".".join(map(str, error["loc"])) or "credentials" for error in exc.errors())
            raise ChannelError(f"Cấu hình kênh không hợp lệ. Kiểm tra: {fields}.", 400) from None
        bot_id = self._types.extract_platform_bot_id(
            channel_type,
            credentials,
        )
        existing = await self._storage.get_channel_id_by_platform_bot_id(
            bot_id,
        )
        if existing:
            raise ChannelError(
                f"Bot '{bot_id}' already registered as channel "
                f"'{existing}'.",
                409,
            )

        channel_id = _generate_id()
        now = datetime.now()
        record = ChannelRecord(
            id=channel_id,
            channel_type=channel_type,
            name=name,
            user_id=user_id,
            enabled=enabled,
            credentials=self._types.seal_credentials(channel_type, credentials),
            platform_config=platform_config,
            routing=routing,
            session=session,
            created_at=now,
            updated_at=now,
        )
        await self._storage.upsert_channel(record, bot_id)
        await self._notify(record.id)
        return record

    async def update(self, channel_id: str, updates: dict) -> ChannelRecord:
        """Apply routing/session/platform_config/enabled changes;
        credentials and channel_type are immutable (recreate to change).

        Args:
            channel_id (`str`): The channel to update.
            updates (`dict`): Field changes to apply.
        """
        record = await self._require(channel_id)
        if "platform_config" in updates:
            updates = {**updates, "platform_config": await self._discord_config(
                record.user_id, record.channel_type, updates["platform_config"],
                trusted_owner=record.platform_config.get("owner_user_id"),
            )}
        updates.pop("credentials", None)
        updates.pop("channel_type", None)
        updated = record.model_copy(
            update={**updates, "updated_at": datetime.now()},
        )
        bot_id = self._types.extract_platform_bot_id(
            updated.channel_type,
            updated.credentials,
        )
        await self._storage.upsert_channel(updated, bot_id)
        await self._notify(channel_id)
        return updated

    async def rotate_secrets(self, channel_id: str, changes: dict) -> ChannelRecord:
        """Rotate a token without replacing channel/session identity."""
        from pydantic import ValidationError
        from ..channel._secrets import open_credentials, secret_fields

        record = await self._require(channel_id)
        channel_cls = self._types.get(record.channel_type)
        if record.channel_type not in {"telegram", "zalo_oa"} or channel_cls is None:
            raise ChannelError("Kênh này chưa hỗ trợ thay token tại chỗ.", 400)
        allowed = secret_fields(channel_cls.Credentials)
        if not changes or set(changes) - allowed or any(not isinstance(v, str) or not v.strip() for v in changes.values()):
            raise ChannelError("Chỉ được cập nhật các trường token hoặc khóa bí mật không rỗng.", 400)
        try:
            credentials = channel_cls.Credentials.model_validate({**open_credentials(record.credentials), **changes}).model_dump()
        except ValidationError:
            raise ChannelError("Token không hợp lệ hoặc không thuộc bot đang kết nối.", 400) from None
        version = max(datetime.now(tz=record.updated_at.tzinfo), record.updated_at + timedelta(microseconds=1))
        updated = record.model_copy(update={"credentials": self._types.seal_credentials(record.channel_type, credentials),
                                           "updated_at": version})
        bot_id = self._types.extract_platform_bot_id(record.channel_type, credentials)
        await self._storage.upsert_channel(updated, bot_id)
        await self._notify(channel_id)
        return updated

    async def set_enabled(
        self,
        channel_id: str,
        enabled: bool,
    ) -> ChannelRecord:
        """Enable or disable a channel.

        Args:
            channel_id (`str`): The channel to toggle.
            enabled (`bool`): The new enabled state.
        """
        return await self.update(channel_id, {"enabled": enabled})

    async def delete(self, channel_id: str) -> None:
        """Delete a channel and clear its bot-id index.

        Args:
            channel_id (`str`): The channel to delete.
        """
        record = await self._require(channel_id)
        bot_id = self._types.extract_platform_bot_id(
            record.channel_type,
            record.credentials,
        )
        await self._storage.delete_channel(channel_id, bot_id)
        await self._notify(channel_id)

    # -- Read-side (cluster-wide, no local instances needed) --

    async def get_status(self, channel_id: str) -> ChannelStatus:
        """The channel's connection status, from whichever node holds it.

        Nodes that run a channel heartbeat their view into a registry,
        so this answers correctly from an API replica that holds no
        connection. Reports older than the heartbeat TTL are ignored —
        the namespace expires as a whole, so a node that stopped
        reporting can leave its last entry behind indefinitely while a
        successor keeps the namespace alive.

        With no report at all, the enabled flag decides: an enabled
        channel is starting, a disabled one is stopped.

        Args:
            channel_id (`str`): The channel to report on.
        """
        try:
            entries = await self._bus.registry_getall(
                MessageBusKeys.channel_liveness(channel_id),
            )
        except Exception:  # pylint: disable=broad-except
            return ChannelStatus(state="stopped")

        now = time.time()
        best: ChannelStatus | None = None
        for raw in entries.values():
            beat = ChannelHeartbeat.model_validate_json(raw)
            if not beat.is_fresh(now):
                continue
            if beat.status.state == "connected":
                return beat.status
            if best is None or best.state == "stopped":
                best = beat.status
        if best is not None:
            return best

        # Nobody has reported yet. For an enabled channel that means it
        # has not been picked up *yet* — a freshly created one is on its
        # way — and calling that "stopped" sends the operator looking
        # for something to start that is already starting.
        record = await self._storage.get_channel(channel_id)
        if record is not None and record.enabled:
            return ChannelStatus(state="connecting")
        return ChannelStatus(state="stopped")

    async def list_seen_chat_ids(self, channel_id: str) -> list[str]:
        """Chat_ids passively recorded from inbound messages.

        Args:
            channel_id (`str`): The channel to list seen chats for.
        """
        fields = await self._bus.registry_getall(
            MessageBusKeys.channel_seen_chats(channel_id),
        )
        return sorted(fields.keys())

    # -- internals --

    async def _discord_config(self, user_id, channel_type, config, *, creating=False, credentials=None, trusted_owner=None):
        if channel_type != "discord":
            return config
        from ..channel._discord._channel import DiscordChannel

        options = DiscordChannel.Config.model_validate(config)
        authority = getattr(self._storage, "vin_platform_service", None)
        context = await authority.context(user_id) if authority is not None else None
        if context is not None and context.role == "VIN_USER":
            from ._discord_identity import bot_owner, verified_owner
            from ..vin_platform import PlatformError
            try:
                try:
                    owner = (await verified_owner(authority, context))["discord_user_id"]
                except PlatformError as exc:
                    if exc.code != "DISCORD_IDENTITY_REQUIRED":
                        raise
                    if creating and credentials:
                        owner = await bot_owner(authority, credentials)
                    elif trusted_owner:
                        owner = trusted_owner
                    else:
                        raise
            except PlatformError as exc:
                raise ChannelError(exc.code, exc.status) from exc
            if options.owner_user_id and options.owner_user_id != owner:
                raise ChannelError("DISCORD_OWNER_MISMATCH", 403)
            options.owner_user_id = owner
            if options.allowed_user_ids is None:
                options.allowed_user_ids = [options.owner_user_id]
            if creating and options.owner_user_id not in options.allowed_user_ids:
                raise ChannelError("Allowed Discord user IDs must include the owner; an empty list blocks everyone.", 400)
            if "approver_user_ids" not in options.model_fields_set:
                options.approver_user_ids = [options.owner_user_id]
        return options.model_dump(exclude_unset=True)

    async def _require(self, channel_id: str) -> ChannelRecord:
        """Load a channel record or raise a 404 ``ChannelError``.

        Args:
            channel_id (`str`): The channel to load.

        Returns:
            `ChannelRecord`: The record.
        """
        record = await self._storage.get_channel(channel_id)
        if record is None:
            raise ChannelError(f"Channel '{channel_id}' not found.", 404)
        return record

    async def _notify(self, channel_id: str) -> None:
        """Publish a lifecycle notification (best-effort).

        Args:
            channel_id (`str`): The changed channel; reconcile re-reads
                storage, so the payload is only a nudge.
        """
        try:
            await self._bus.publish(
                MessageBusKeys.channel_lifecycle(),
                {"channel_id": channel_id},
            )
        except Exception:  # pylint: disable=broad-except
            # Lost notifications are recovered by the periodic reconcile.
            pass
