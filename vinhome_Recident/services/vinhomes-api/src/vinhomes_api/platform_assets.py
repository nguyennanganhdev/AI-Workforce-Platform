"""Verified resident ticket images -> Platform Asset API. No model access, arbitrary URLs or credentials in messages."""

import hashlib
import json
from uuid import UUID

from minio.error import S3Error
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from . import storage, v3_files
from .platform import TENANT, PlatformError

LIMIT = 10 * 1024 * 1024


def read_image(row):
    target = storage.at(v3_files.FILE_ROOT, row["object_key"])
    if isinstance(target, storage.BucketObject):
        response = storage.client().get_object(storage.bucket(), target.key)
        try:
            raw = response.read(LIMIT + 1)
        finally:
            response.close()
            response.release_conn()
    else:
        with target.open("rb") as source:
            raw = source.read(LIMIT + 1)
    if (
        len(raw) != row["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != row["sha256"]
    ):
        raise ValueError("Verified image content changed")
    return raw


async def prepare(engine, client, tenant, link, command):
    body = command["body"]
    requested = body.get("file_ids") or []
    if not requested:
        return body
    try:
        ids = list(dict.fromkeys(UUID(str(value)) for value in requested))
    except ValueError:
        raise PlatformError(422, "DOMAIN_IMAGE_REFERENCE_INVALID") from None
    if len(ids) > 10:
        raise PlatformError(422, "DOMAIN_IMAGE_MESSAGE_LIMIT")
    destination = hashlib.sha256(
        json.dumps(
            [
                client.bridge.url,
                client.bridge.customer_key,
                link["management_ref"],
                link["user_id"],
                str(link["channel_id"]),
            ]
        ).encode()
    ).hexdigest()
    attachments = []
    async with engine.begin() as db:
        await db.execute(
            text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant}
        )
        files = (
            (
                await db.execute(
                    text(f"""select f.id,o.object_key,o.mime_type,o.size_bytes,o.sha256
            from ticket_files tf join files f on f.id=tf.file_id and f.tenant_id=tf.tenant_id
            join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
            join storage_locations s on s.id=o.location_id and s.tenant_id=o.tenant_id
            where tf.tenant_id={TENANT} and tf.ticket_id=:ticket and f.id=any(cast(:ids as uuid[]))
              and tf.purpose='issue' and tf.uploaded_by=:user and f.uploaded_by=:user
              and f.status='ready' and f.deleted_at is null and o.status='ready' and o.scan_status='clean'
              and o.verified_at is not null and s.provider=:provider and s.status='active'"""),
                    {
                        "ticket": link["ticket_id"],
                        "ids": ids,
                        "user": link["user_id"],
                        "provider": storage.provider(),
                    },
                )
            )
            .mappings()
            .all()
        )
        by_id = {row["id"]: row for row in files}
        if set(by_id) != set(ids) or any(
            row["mime_type"] not in v3_files.EXT or not 0 < row["size_bytes"] <= LIMIT
            for row in files
        ):
            raise PlatformError(403, "DOMAIN_IMAGE_SCOPE_FORBIDDEN")
        if body.get("asset_attachments"):
            # Frozen before the request is sent; the same request id always carries the same asset ids.
            return body
        for file_id in ids:
            row = by_id[file_id]
            cached = (
                (
                    await db.execute(
                        text(f"""select asset_id,source_sha256 from platform_resident_assets
                where tenant_id={TENANT} and ticket_id=:ticket and file_id=:file and destination_hash=:destination"""),
                        {
                            "ticket": link["ticket_id"],
                            "file": file_id,
                            "destination": destination,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if cached:
                if cached["source_sha256"] != row["sha256"]:
                    raise PlatformError(409, "DOMAIN_IMAGE_CHANGED")
                asset_id = cached["asset_id"]
            else:
                try:
                    raw = await run_in_threadpool(read_image, row)
                except (OSError, ValueError, S3Error) as exc:
                    raise PlatformError(
                        503,
                        "DOMAIN_IMAGE_UNAVAILABLE",
                        type(exc).__name__,
                        retryable=True,
                    ) from None
                asset_id = await client.upload_asset(
                    {
                        "external_management_ref": link["management_ref"],
                        "external_user_id": link["user_id"],
                        "external_ticket_id": str(link["ticket_id"]),
                        "external_conversation_id": f"{link['channel_id']}:{link['ticket_id']}",
                    },
                    f"resident-{file_id}{v3_files.EXT[row['mime_type']]}",
                    row["mime_type"],
                    raw,
                )
                await db.execute(
                    text(f"""insert into platform_resident_assets
                    (tenant_id,ticket_id,file_id,destination_hash,source_sha256,asset_id)
                    values({TENANT},:ticket,:file,:destination,:sha,:asset)"""),
                    {
                        "ticket": link["ticket_id"],
                        "file": file_id,
                        "destination": destination,
                        "sha": row["sha256"],
                        "asset": asset_id,
                    },
                )
            attachments.append({"asset_id": asset_id})
        body = {**body, "asset_attachments": attachments}
        await db.execute(
            text("update platform_commands set body=cast(:body as jsonb) where id=:id"),
            {"id": command["id"], "body": json.dumps(body, ensure_ascii=False)},
        )
    # This separate transaction commits the immutable references BEFORE the request can be accepted remotely.
    return body
