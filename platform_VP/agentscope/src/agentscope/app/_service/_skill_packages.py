"""Bounded, checksum-verified skill snapshots; no model or hub at reuse."""
import base64
import hashlib

from fastapi import HTTPException

MAX_ARCHIVE_BYTES = 2_000_000


async def cache_archive(record, stream, archive_format):
    payload = bytearray()
    if isinstance(stream, (bytes, bytearray)):
        payload.extend(stream)
    else:
        async for chunk in stream:
            payload.extend(chunk)
            if len(payload) > MAX_ARCHIVE_BYTES:
                raise HTTPException(413, "Skill archive vượt giới hạn 2 MB.")
    if len(payload) > MAX_ARCHIVE_BYTES or archive_format not in {"zip", "tar"}:
        raise HTTPException(413, "Skill archive không hợp lệ hoặc vượt giới hạn.")
    record.archive_base64 = base64.b64encode(payload).decode()
    record.archive_format = archive_format
    record.archive_sha256 = hashlib.sha256(payload).hexdigest()


def archive_bytes(record):
    try:
        data = base64.b64decode(record.archive_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(409, "Skill archive không đọc được.") from exc
    if len(data) > MAX_ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != record.archive_sha256:
        raise HTTPException(409, "Checksum skill không khớp; cần cài lại bản đã duyệt.")
    return data


async def byte_stream(data):
    yield data
