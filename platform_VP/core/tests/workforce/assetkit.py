"""Helpers for the image-asset tests (spec A3): tiny images, a client that may send them, the upload call.

The images are only as long as the checks need: the platform reads the first bytes of an upload, it never decodes one.
"""
from __future__ import annotations

import itertools
import os
import re
from pathlib import Path

from conftest import ADM, ALL_CUSTOMER, key_headers

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 40
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 40
GIF = b"GIF89a" + b"\x01\x00\x01\x00" + b"\x00" * 40
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 40
OPS = [*ALL_CUSTOMER, "attach_asset"]
URL = "/workforce/v1/partner/assets"
ASSET = re.compile(r"ast_[0-9a-f]{32}")
LINK = re.compile(r"X-A(?:mz|wp)-Signature=")  # what every signed link holds, whichever backend made it
_n = itertools.count(1)

S3_ENDPOINT = os.environ.get("AWP_TEST_S3_ENDPOINT", "").strip()


def minio_settings(bucket: str) -> dict:
    """Settings of an app whose images go to the tests' real MinIO (AWP_TEST_S3_*)."""
    return dict(asset_backend="s3", s3_endpoint=S3_ENDPOINT, s3_bucket=bucket, s3_access_key=os.environ["AWP_TEST_S3_ACCESS_KEY"],
                s3_secret_key=os.environ["AWP_TEST_S3_SECRET_KEY"], s3_region=os.environ.get("AWP_TEST_S3_REGION", "us-east-1"))


def grant(env, client_id: str, on: bool = True, headers=ADM):
    """The operator gives (or takes) the capability through the admin API."""
    return env.http.patch(f"/platform/v1/wf/clients/{client_id}", json={"capabilities": ["attach_asset"] if on else []},
                          headers=headers)


def with_images(flow):
    """The flow's partner may send images from now on: the capability on its client, the operation on its key."""
    r = grant(flow.env, flow.client["client_id"])
    assert r.status_code == 200 and r.json()["capabilities"] == ["attach_asset"], r.text
    flow.key = flow.env.key(flow.client["client_id"], operations=OPS)
    return flow


def upload(http, api_key: str, data: bytes = PNG, *, rid: str | None = None, user: str | None = "resident-123",
           conv: str | None = "CHAT-IMG-1", content_type: str | None = "image/png", headers: dict | None = None, **params):
    """POST one image. `rid`, `user`, `conv`: the three ids of the query (None leaves one out)."""
    query = {"external_request_id": rid or f"up-{next(_n)}", "external_user_id": user, "external_conversation_id": conv, **params}
    head = {**key_headers(api_key), **({"Content-Type": content_type} if content_type else {}), **(headers or {})}
    return http.post(URL, params={k: v for k, v in query.items() if v is not None}, content=data, headers=head)


def uploaded(flow, data: bytes = PNG, **kw) -> dict:
    r = upload(flow.http, flow.key["api_key"], data, **kw)
    assert r.status_code == 201, r.text
    return r.json()


def image(asset_id: str, text: str | None = None) -> dict:
    return {"type": "image", "asset_id": asset_id, **({"text": text} if text is not None else {})}


def store_of(env):
    return env.app.state.awp.rt.assets


def files(env) -> list[Path]:
    """Every object the local store holds."""
    return sorted(p for p in Path(store_of(env).root).rglob("*") if p.is_file())


def rows(env, where: str = "", args=()) -> list[dict]:
    keys = ("id", "client_id", "external_user_id", "external_conversation_id", "conversation_id", "object_key",
            "content_type", "size", "sha256")
    return [dict(zip(keys, r)) for r in env.sql(f"select {', '.join(keys)} from wf_assets {where} order by created_at", args)]


def error(r) -> tuple:
    return r.status_code, r.json()["error"]["code"]
