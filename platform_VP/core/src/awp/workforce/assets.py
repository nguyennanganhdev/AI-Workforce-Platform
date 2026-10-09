"""Private MinIO assets: upload staging is never the immutable evidence object."""
import asyncio
import hashlib
import io
import time
from datetime import UTC, timedelta

from sqlalchemy import insert, update

from . import schema as s
from .service import Fault, digest, row, stamp


def client_for(service):
    from minio import Minio
    settings = service.rt.settings
    if not settings.minio_endpoint or not settings.minio_access_key or not settings.minio_secret_key:
        raise Fault(503, "ASSET_STORAGE_NOT_CONFIGURED")
    return Minio(settings.minio_endpoint, access_key=settings.minio_access_key,
                 secret_key=settings.minio_secret_key, secure=settings.minio_secure)


async def create_upload(service, client, body):
    store, bucket = client_for(service), service.rt.settings.minio_bucket
    async with service.tx() as conn:
        route = await service.route(conn, client, body.external_management_ref)
        if not route["config"]["asset_capability"]:
            raise Fault(422, "UNSUPPORTED_MESSAGE_PART")
        residence = await row(conn, s.residences, s.residences.c.client_id == client["id"],
            s.residences.c.user_id == body.external_user_id, s.residences.c.route_id == route["id"],
            s.residences.c.status == "active")
        if route["config"]["require_residence"] and not residence:
            raise Fault(403, "RESIDENCE_NOT_AUTHORIZED")
        asset_id = digest({"client": client["id"], **body.model_dump()})
        existing = await row(conn, s.assets, s.assets.c.id == asset_id)
        if not existing:
            await conn.execute(insert(s.assets).values(id=asset_id, client_id=client["id"], route_id=route["id"],
                user_id=body.external_user_id, external_ticket_id=body.external_ticket_id,
                external_conversation_id=body.external_conversation_id, object_key="assets/" + asset_id,
                status="uploading", workflow_id=None, metadata=body.model_dump(), created=time.time(),
                expires=time.time() + 900))
        elif existing["status"] == "ready":
            return {"asset_id": asset_id, "status": "ready"}
        else:
            await conn.execute(update(s.assets).where(s.assets.c.id == asset_id).values(expires=time.time() + 900))
    def presign():
        if not store.bucket_exists(bucket):
            from minio.error import S3Error
            try:
                store.make_bucket(bucket)
            except S3Error as exc:
                if exc.code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                    raise
            else:
                from minio.commonconfig import ENABLED, Filter
                from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule
                store.set_bucket_lifecycle(bucket, LifecycleConfig([
                    Rule(ENABLED, rule_filter=Filter(prefix="staging/"), rule_id="expired-upload-staging",
                         expiration=Expiration(days=1))]))
        from datetime import datetime

        from minio.datatypes import PostPolicy
        policy = PostPolicy(bucket, datetime.now(UTC) + timedelta(minutes=15))
        policy.add_equals_condition("key", "staging/" + asset_id)
        policy.add_equals_condition("Content-Type", body.content_type)
        policy.add_content_length_range_condition(body.size, body.size)
        return {**store.presigned_post_policy(policy), "key": "staging/" + asset_id,
                "Content-Type": body.content_type}
    fields = await asyncio.to_thread(presign)
    scheme = "https" if service.rt.settings.minio_secure else "http"
    origin = service.rt.settings.minio_upload_origin.rstrip("/") or f"{scheme}://{service.rt.settings.minio_endpoint}"
    return {"asset_id": asset_id, "status": "uploading", "method": "POST",
            "upload_url": f"{origin}/{bucket}",
            "fields": fields, "expires_at": stamp(time.time() + 900)}


async def owned(service, client, asset_id, user):
    async with service.rt.db.engine.connect() as conn:
        asset = await row(conn, s.assets, s.assets.c.id == asset_id, s.assets.c.client_id == client["id"],
                          s.assets.c.user_id == user)
        if not asset:
            raise Fault(404, "NOT_FOUND")
        route = await row(conn, s.routes, s.routes.c.id == asset["route_id"])
        if not route or route["status"] != "active":
            raise Fault(403, "ROUTE_NOT_AUTHORIZED")
        if asset["workflow_id"]:
            await service.binding(conn, client, asset["workflow_id"], user)
        elif route["config"]["require_residence"] and not await row(conn, s.residences,
                s.residences.c.client_id == client["id"], s.residences.c.route_id == route["id"],
                s.residences.c.user_id == user, s.residences.c.status == "active"):
            raise Fault(403, "RESIDENCE_NOT_AUTHORIZED")
    return asset


def read_bytes(store, bucket, key, limit):
    response = store.get_object(bucket, key)
    try:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise Fault(413, "ASSET_TOO_LARGE")
        return data
    finally:
        response.close()
        response.release_conn()


async def finalize(service, client, asset_id, user):
    asset = await owned(service, client, asset_id, user)
    if asset["status"] == "ready":
        return {"asset_id": asset_id, "status": "ready"}
    if asset["expires"] < time.time():
        raise Fault(409, "UPLOAD_EXPIRED")
    store, bucket = client_for(service), service.rt.settings.minio_bucket
    data = await asyncio.to_thread(read_bytes, store, bucket, "staging/" + asset_id, asset["metadata"]["size"])
    if len(data) != asset["metadata"]["size"] or hashlib.sha256(data).hexdigest() != asset["metadata"]["sha256"]:
        raise Fault(422, "ASSET_CHECKSUM_MISMATCH")
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20_000_000 or image.get_format_mimetype() != asset["metadata"]["content_type"]:
                raise Fault(422, "INVALID_IMAGE")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise Fault(422, "INVALID_IMAGE")
    # The final object is written from verified bytes, not copied from mutable staging after verification.
    await asyncio.to_thread(store.put_object, bucket, asset["object_key"], io.BytesIO(data), len(data),
                            content_type=asset["metadata"]["content_type"])
    async with service.tx() as conn:
        await conn.execute(update(s.assets).where(s.assets.c.id == asset_id).values(status="ready"))
    await asyncio.to_thread(store.remove_object, bucket, "staging/" + asset_id)
    return {"asset_id": asset_id, "status": "ready", "size": len(data), "sha256": asset["metadata"]["sha256"]}


async def content(service, client, asset_id, user):
    asset = await owned(service, client, asset_id, user)
    if asset["status"] != "ready":
        raise Fault(409, "ASSET_NOT_READY")
    store = client_for(service)
    data = await asyncio.to_thread(read_bytes, store, service.rt.settings.minio_bucket,
                                  asset["object_key"], asset["metadata"]["size"])
    if hashlib.sha256(data).hexdigest() != asset["metadata"]["sha256"]:
        raise Fault(409, "ASSET_CHECKSUM_MISMATCH")
    return data, asset["metadata"]["content_type"]


async def vision_blocks(service, wf, req):
    ids = req["body"]["message"].get("asset_ids", [])
    if not ids:
        return []
    spec = wf["snapshot"]["models"].get(wf["snapshot"]["leader_profile"], {})
    if not spec.get("supports_vision"):
        raise Fault(409, "MODEL_VISION_NOT_CONFIGURED")
    async with service.rt.db.engine.connect() as conn:
        conv = await row(conn, s.conversations, s.conversations.c.id == wf["conversation_id"])
        client = await row(conn, s.clients, s.clients.c.id == conv["client_id"])
    import base64

    from PIL import Image, ImageOps
    blocks = []
    for asset_id in ids:
        data, _ = await content(service, client, asset_id, conv["user_id"])
        def derive(raw=data):
            with Image.open(io.BytesIO(raw)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((768, 768))
                out = io.BytesIO()
                image.save(out, format="JPEG", quality=75)
                return out.getvalue()
        store = client_for(service)
        key = "derived/" + asset_id + "/vision-v1.jpg"
        async with service.tx() as conn:
            asset = await row(conn, s.assets, s.assets.c.id == asset_id, lock=True)
            prior = asset["metadata"].get("vision_derivative")
            if prior:
                derived = await asyncio.to_thread(read_bytes, store, service.rt.settings.minio_bucket,
                                                prior["object_key"], 10485760)
                if digest(derived) != prior["sha256"]:
                    raise Fault(409, "ASSET_CHECKSUM_MISMATCH")
            else:
                derived = await asyncio.to_thread(derive)
                await asyncio.to_thread(store.put_object, service.rt.settings.minio_bucket, key,
                                        io.BytesIO(derived), len(derived), content_type="image/jpeg")
                await conn.execute(update(s.assets).where(s.assets.c.id == asset_id).values(metadata={**asset["metadata"],
                    "vision_derivative": {"object_key": key, "sha256": digest(derived), "version": "vision-v1"}}))
        blocks.append({"type": "data", "name": asset_id, "source": {"type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(derived).decode()}})
    return blocks
