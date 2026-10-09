# -*- coding: utf-8 -*-
"""Private image storage backed by MinIO/AWS S3 and PostgreSQL metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import IO, Any
from uuid import uuid4

from ..rag.blob_store import S3BlobStore


_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


def _detect_image(header: bytes) -> tuple[str, str]:
    for signature, content_type, extension in _IMAGE_SIGNATURES:
        if header.startswith(signature):
            return content_type, extension
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise ValueError("unsupported or invalid image; use JPEG, PNG, GIF, or WebP")


def _owner_prefix(tenant_id: str, user_id: str) -> str:
    """Hide user-controlled identifiers from object paths."""
    tenant = hashlib.sha256(tenant_id.encode()).hexdigest()[:20]
    user = hashlib.sha256(user_id.encode()).hexdigest()[:20]
    return f"{tenant}/{user}"


@dataclass(slots=True, frozen=True)
class ImageAsset:
    """Database representation of one private image."""

    id: str
    tenant_id: str
    user_id: str
    object_uri: str
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ImageAssetService:
    """Validate, store, query, sign, and delete private image assets."""

    def __init__(
        self,
        *,
        engine: Any,
        blob_store: S3BlobStore,
        max_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self._engine = engine
        self._blob_store = blob_store
        self._max_bytes = max_bytes

    @staticmethod
    def _measure_and_hash(stream: IO[bytes]) -> tuple[int, str, bytes]:
        """Validate a seekable stream without retaining the image in RAM."""
        if not stream.seekable():
            raise ValueError("image stream must be seekable")
        stream.seek(0)
        header = stream.read(32)
        digest = hashlib.sha256()
        size = 0
        stream.seek(0)
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
        stream.seek(0)
        return size, digest.hexdigest(), header

    async def upload(
        self,
        *,
        tenant_id: str,
        user_id: str,
        filename: str,
        stream: IO[bytes],
        metadata: dict[str, Any] | None = None,
    ) -> ImageAsset:
        """Upload a validated image and atomically register its metadata.

        S3 and PostgreSQL cannot share a transaction. If the database insert
        fails, the newly uploaded object is deleted as compensation.
        """
        from sqlalchemy import text

        if not tenant_id or not user_id:
            raise ValueError("tenant_id and user_id are required")
        size, checksum, header = self._measure_and_hash(stream)
        if size <= 0 or size > self._max_bytes:
            raise ValueError(
                f"image size must be between 1 and {self._max_bytes} bytes",
            )
        content_type, extension = _detect_image(header)
        asset_id = str(uuid4())
        now = datetime.now(timezone.utc)
        prefix = _owner_prefix(tenant_id, user_id)
        key = f"images/{prefix}/{now:%Y/%m}/{asset_id}.{extension}"
        safe_filename = Path(filename).name[:512] or f"{asset_id}.{extension}"
        uri = await self._blob_store.write_stream_with_metadata(
            key,
            stream,
            content_type=content_type,
            metadata={"sha256": checksum, "asset-id": asset_id},
        )
        asset = ImageAsset(
            id=asset_id,
            tenant_id=tenant_id,
            user_id=user_id,
            object_uri=uri,
            original_filename=safe_filename,
            content_type=content_type,
            byte_size=size,
            sha256=checksum,
            status="active",
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO image_assets (
                            id, tenant_id, user_id, object_uri,
                            original_filename, content_type, byte_size, sha256,
                            status, metadata, created_at, updated_at
                        ) VALUES (
                            :id, :tenant_id, :user_id, :object_uri,
                            :original_filename, :content_type, :byte_size,
                            :sha256, :status, :metadata, :created_at, :updated_at
                        )
                        """,
                    ),
                    {
                        "id": asset.id,
                        "tenant_id": asset.tenant_id,
                        "user_id": asset.user_id,
                        "object_uri": asset.object_uri,
                        "original_filename": asset.original_filename,
                        "content_type": asset.content_type,
                        "byte_size": asset.byte_size,
                        "sha256": asset.sha256,
                        "status": asset.status,
                        "metadata": asset.metadata,
                        "created_at": asset.created_at,
                        "updated_at": asset.updated_at,
                    },
                )
        except Exception:
            try:
                await self._blob_store.delete(uri)
            except Exception:
                # Preserve the database error. An object-lifecycle policy or
                # orphan sweeper can remove the unreferenced object later.
                pass
            raise
        return asset

    async def get(
        self,
        *,
        tenant_id: str,
        user_id: str,
        asset_id: str,
    ) -> ImageAsset | None:
        """Fetch one active asset within its owner boundary."""
        from sqlalchemy import text

        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT * FROM image_assets
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND user_id = :user_id AND status = 'active'
                        """,
                    ),
                    {"id": asset_id, "tenant_id": tenant_id, "user_id": user_id},
                )
            ).mappings().first()
        return ImageAsset(**row) if row else None

    async def create_download_url(
        self,
        *,
        tenant_id: str,
        user_id: str,
        asset_id: str,
        expires_in: int = 900,
    ) -> str:
        """Authorize ownership, then return a short-lived private URL."""
        asset = await self.get(
            tenant_id=tenant_id,
            user_id=user_id,
            asset_id=asset_id,
        )
        if asset is None:
            raise KeyError(asset_id)
        return await self._blob_store.presign_get(
            asset.object_uri,
            expires_in=expires_in,
            download_name=asset.original_filename,
        )

    async def delete(
        self,
        *,
        tenant_id: str,
        user_id: str,
        asset_id: str,
    ) -> bool:
        """Delete object bytes and retain a tombstone for audit/retry.

        The row first moves to ``deleting`` so concurrent downloads stop.
        A failed S3 deletion restores ``active``; a successful deletion moves
        to ``deleted``. This is a small application-level saga because S3 and
        PostgreSQL cannot participate in one transaction.
        """
        from sqlalchemy import text

        async with self._engine.begin() as connection:
            object_uri = await connection.scalar(
                text(
                    """
                    UPDATE image_assets SET status = 'deleting', updated_at = :now
                    WHERE id = :id AND tenant_id = :tenant_id
                      AND user_id = :user_id AND status = 'active'
                    RETURNING object_uri
                    """,
                ),
                {
                    "id": asset_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "now": datetime.now(timezone.utc),
                },
            )
        if object_uri is None:
            return False
        try:
            await self._blob_store.delete(object_uri)
        except Exception:
            async with self._engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        UPDATE image_assets
                        SET status = 'active', updated_at = :now
                        WHERE id = :id AND tenant_id = :tenant_id
                          AND user_id = :user_id AND status = 'deleting'
                        """,
                    ),
                    {
                        "id": asset_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "now": datetime.now(timezone.utc),
                    },
                )
            raise
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE image_assets SET status = 'deleted', updated_at = :now
                    WHERE id = :id AND tenant_id = :tenant_id
                      AND user_id = :user_id AND status = 'deleting'
                    """,
                ),
                {
                    "id": asset_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "now": datetime.now(timezone.utc),
                },
            )
        return True
