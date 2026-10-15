"""Verified pre-intake images in the canonical files/file_objects registry."""

import hashlib
import hmac
import io
import time
import warnings
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from .resident_contract import BASE, OPERATIONS_BASE, TENANT, PHOTO_LIMIT, PHOTO_TYPES, UploadedPhoto, digest, fail
from .resident_cases import MANAGEMENT, OWNER, case_row, receipt, residence, save_receipt
from . import storage as object_storage
from .v3_files import FILE_ROOT, EXT, local_only

MAX_PIXELS = 20_000_000


def photo_dto(request: Request, actor: str, row) -> dict:
    expires = int(time.time()) + 900
    message = f"resident:{request.app.state.settings.tenant_id}:{actor}:{row['id']}:{expires}".encode()
    signature = hmac.new(request.app.state.image_access_key, message, hashlib.sha256).hexdigest()
    base = OPERATIONS_BASE if request.url.path.startswith(OPERATIONS_BASE) else BASE
    return {"id": str(row["id"]), "name": row["original_name"],
            "url": f"{base}/photos/{row['id']}/content?access={expires}.{signature}",
            "urlExpiresAt": datetime.fromtimestamp(expires, timezone.utc).isoformat()}


def verify_image(data: bytes, declared: str) -> tuple[bytes, int, int]:
    """Decode and sanitize bytes/metadata before marking the object verified."""
    if declared not in PHOTO_TYPES:
        fail(415, "UNSUPPORTED_MEDIA_TYPE", "Chỉ nhận ảnh JPG, PNG hoặc WebP.")
    expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[declared]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != expected or image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    fail(422, "VALIDATION_ERROR", "Ảnh không đúng định dạng, là ảnh động hoặc quá nhiều pixel.")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                output = io.BytesIO()
                converted = image.convert("RGB" if expected == "JPEG" else "RGBA")
                converted.save(output, format=expected)
                result = output.getvalue()
                if len(result) > PHOTO_LIMIT:
                    fail(413, "PAYLOAD_TOO_LARGE", "Ảnh đã xử lý vượt 10 MiB.")
                return result, image.width, image.height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(422, "VALIDATION_ERROR", "Ảnh bị hỏng hoặc vượt giới hạn pixel.")


def object_path(key: str):
    try:
        return object_storage.at(FILE_ROOT, key)
    except ValueError:
        fail(503, "SERVICE_UNAVAILABLE", "Cấu hình lưu trữ ảnh không hợp lệ.")


async def accessible_photo(scope, file_id: UUID, *, operations: bool = False):
    db, actor = scope[:2]
    # Intake file or an explicitly published result. Never expose arbitrary evidence.
    predicate = MANAGEMENT if operations else OWNER
    params = {"file": file_id, "actor": actor, "admin": bool(scope[2]) if operations else False}
    case = (await db.execute(text(f"""select c.id from vh_resident_cases c where c.tenant_id={TENANT}
      and {predicate} and (
        exists(select 1 from vh_resident_photos p where p.case_id=c.id and p.tenant_id=c.tenant_id and p.file_id=:file)
        or exists(select 1 from vh_resident_resolution_photos rp
          where rp.resolution_id=c.current_resolution_id and rp.tenant_id=c.tenant_id and rp.file_id=:file)) limit 1"""), params)).scalar_one_or_none()
    if case is None and not operations:
        staged = (await db.execute(text(f"""select unit_id from vh_resident_photos
          where tenant_id={TENANT} and file_id=:file and uploaded_by=:actor and case_id is null and expires_at>now()"""), params)).scalar_one_or_none()
        if staged is not None:
            await residence(db, actor, staged)
        else:
            fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy ảnh.")
    elif case is None:
        fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy ảnh.")
    elif not operations:
        row = await case_row(scope, case)
        # A revoked/superseded publication cannot make its result photos public.
        intake = (await db.execute(text(f"select 1 from vh_resident_photos where tenant_id={TENANT} and case_id=:case and file_id=:file"), {"case": case, "file": file_id})).first()
        if not intake and row["public_status"] not in {"confirmation", "completed"}:
            fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy ảnh.")
    row = (await db.execute(text(f"""select f.id,f.original_name,o.object_key,o.mime_type,o.location_id
      from files f join file_objects o on o.id=f.accepted_object_id and o.tenant_id=f.tenant_id
      join storage_locations s on s.id=o.location_id and s.tenant_id=o.tenant_id
      where f.id=:file and f.tenant_id={TENANT} and f.status='ready' and f.deleted_at is null
        and o.status='ready' and o.scan_status='clean' and o.verified_at is not null and s.provider='{object_storage.provider()}' and s.status!='disabled'"""), params)).mappings().first()
    if row is None or row['mime_type'] not in PHOTO_TYPES:
        fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy ảnh đã xác minh.")
    return dict(row)


async def upload(scope, apartment_id: UUID, file: UploadFile, request: Request, key: str):
    local_only(request)
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255 or any(c in filename for c in "/\\") or any(ord(c) < 32 for c in filename):
        fail(422, "VALIDATION_ERROR", "Tên ảnh phải là tên file, không chứa đường dẫn.")
    raw = await file.read(PHOTO_LIMIT + 1)
    await file.close()
    if len(raw) > PHOTO_LIMIT:
        fail(413, "PAYLOAD_TOO_LARGE", "Ảnh vượt giới hạn 10 MiB.")
    payload = {"apartmentId": str(apartment_id), "name": filename, "sha256": hashlib.sha256(raw).hexdigest(), "mime": file.content_type}
    previous = await receipt(scope, "photo", "photos", key, payload)
    if previous:
        await accessible_photo(scope, previous["result_id"])
        return previous["response_body"]
    db, actor = scope
    await residence(db, actor, apartment_id)
    data, width, height = await run_in_threadpool(verify_image, raw, file.content_type or "")
    storage = (await db.execute(text(f"""select id,tenant_prefix from storage_locations
      where tenant_id={TENANT} and provider='{object_storage.provider()}' and purpose='evidence' and status='active' order by created_at limit 1"""))).mappings().first()
    if storage is None:
        fail(503, "SERVICE_UNAVAILABLE", "Chưa cấu hình nơi lưu ảnh.")
    await db.execute(text("select pg_advisory_xact_lock(:lock)"), {"lock": int(digest([actor, "file-principal"])[:16], 16) - (1 << 63)})
    principal = (await db.execute(text(f"select id from execution_principals where tenant_id={TENANT} and kind='user' and user_id=:actor and status='active'"), {"actor": actor})).scalar_one_or_none()
    if principal is None:
        principal = (await db.execute(text(f"insert into execution_principals(tenant_id,kind,user_id,status) values({TENANT},'user',:actor,'active') returning id"), {"actor": actor})).scalar_one()
    file_id, object_id = uuid4(), uuid4()
    object_key = f"{storage['tenant_prefix']}resident/{file_id.hex}{EXT[file.content_type]}"
    path = object_path(object_key)
    written = False
    try:
        await run_in_threadpool(path.parent.mkdir, parents=True, exist_ok=True)
        def write():
            with path.open("xb") as output:
                output.write(data)
        await run_in_threadpool(write)
        written = True
        request.state.resident_created_paths.append(path)
        await db.execute(text(f"""insert into files(id,tenant_id,uploaded_by,original_name,owner_principal_id,scope_kind,unit_id,status,declared_mime_type,retention_until)
          values(:id,{TENANT},:actor,:name,:principal,'resident',:unit,'staged',:mime,now()+interval '24 hours')"""),
          {"id": file_id, "actor": actor, "name": filename, "principal": principal, "unit": apartment_id, "mime": file.content_type})
        await db.execute(text(f"""insert into file_objects(id,tenant_id,file_id,location_id,object_key,version_id,variant,mime_type,size_bytes,sha256,width_px,height_px,scan_status,verified_at,encryption_mode,status)
          values(:id,{TENANT},:file,:location,:object,:version,'original',:mime,:size,:sha,:width,:height,'clean',now(),'none','ready')"""),
          {"id": object_id, "file": file_id, "location": storage["id"], "object": object_key, "version": str(uuid4()),
           "mime": file.content_type, "size": len(data), "sha": hashlib.sha256(data).hexdigest(), "width": width, "height": height})
        await db.execute(text(f"update files set status='ready',accepted_object_id=:object where id=:file and tenant_id={TENANT}"), {"file": file_id, "object": object_id})
        await db.execute(text(f"insert into vh_resident_photos(tenant_id,file_id,unit_id,uploaded_by) values({TENANT},:file,:unit,:actor)"), {"file": file_id, "unit": apartment_id, "actor": actor})
        result = UploadedPhoto(**photo_dto(request, actor, {"id": file_id, "original_name": filename})).model_dump(mode="json")
        await save_receipt(scope, "photo", "photos", key, payload, result, 201, file_id)
        return result
    except BaseException:
        if written:
            await run_in_threadpool(path.unlink, missing_ok=True)
        raise


def verify_access(scope, file_id: UUID, request: Request, access: str):
    try:
        expires_text, signature = access.split(".", 1)
        expires = int(expires_text)
        message = f"resident:{request.app.state.settings.tenant_id}:{scope[1]}:{file_id}:{expires}".encode()
        expected = hmac.new(request.app.state.image_access_key, message, hashlib.sha256).hexdigest()
        if expires <= int(time.time()) or not hmac.compare_digest(signature, expected):
            raise ValueError()
    except (ValueError, TypeError):
        fail(403, "PHOTO_ACCESS_EXPIRED", "Link ảnh đã hết hạn. Vui lòng tải lại hồ sơ.")


async def content(scope, file_id: UUID, request: Request, access: str, *, operations=False):
    local_only(request)
    verify_access(scope, file_id, request, access)
    row = await accessible_photo(scope, file_id, operations=operations)
    path = object_path(row["object_key"])
    if not path.is_file():
        fail(404, "PHOTO_NOT_FOUND", "Không tìm thấy nội dung ảnh.")
    return object_storage.respond(path, media_type=row["mime_type"], filename=row["original_name"], content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
