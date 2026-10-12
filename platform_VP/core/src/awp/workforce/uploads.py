"""Image assets of the partner API (spec A3): an EXTENSION beyond contract v1, which standardises text only and says
files need "a contract of their own" (contract 6.2). Nothing here exists for a client without the capability
`attach_asset`, which an operator gives after the partner agreed to the extension.

  POST /workforce/v1/partner/assets?external_request_id=..&external_user_id=..&external_conversation_id=..
       body: the image bytes (the Content-Type header is ignored: the type is read from the first bytes)
       201 {asset_id, content_type, size, sha256, external_user_id, external_conversation_id, created_at}

Order of checks: credential -> operation `attach_asset` of the key -> capability of the client -> the three ids ->
the store is configured -> size, while the body is read (413) -> type by magic bytes (422) -> idempotency -> the
object, then the rows. Nothing of the body is read before the key, the operation and the capability are checked.

An asset belongs to the audience its upload named (client, user, the partner's conversation id) and to nobody else:
a message may carry it only with exactly those three (`for_message`), and a leader may link it only inside the
workflow whose conversation it was sent in (`of_workflow`). The answer never holds where the bytes are.

The platform never fetches anything for an asset: the bytes come in this POST or not at all.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from .. import assets
from ..assets import StoreError
from . import tables as t
from .auth import authenticate
from .common import iso, now
from .errors import UploadRoute, WorkforceError, failed, field_errors, load_body
from .schemas import ExtId
from .tables import new_id

log = logging.getLogger("awp.workforce")
CAPABILITY = "attach_asset"
COMMAND = "attach_asset"  # the command_type of an upload in wf_requests: one idempotency namespace for every command
IDS = ("external_request_id", "external_user_id", "external_conversation_id")
_ext = TypeAdapter(ExtId)


def has_capability(p: Any) -> bool:
    return CAPABILITY in p.client.capabilities


async def can_attach(db, client_id: str) -> bool:
    """The client has the capability now (read from its row: an operator may have taken it away since)."""
    async with db.engine.connect() as conn:
        caps = (await conn.execute(select(t.clients.c.capabilities).where(t.clients.c.id == client_id))).scalar()
    return CAPABILITY in (caps or [])


def store_down(configured: bool) -> WorkforceError:
    return WorkforceError("INTERNAL_ERROR", 503, "Image storage is not available.",
                          {"reason": "asset_store_unavailable" if configured else "asset_store_not_configured"},
                          retryable=configured)


def unknown_asset() -> WorkforceError:
    """One answer for an id that does not exist, is another client's, another resident's, or was uploaded for another
    conversation: which of them it is tells a caller something about somebody else."""
    return WorkforceError("NOT_FOUND", 404, "No such asset for this user and conversation.", {"field": "message.asset_id"})


def _ids(request: Request) -> dict[str, str]:
    out, errors = {}, []
    for name in IDS:
        try:
            value = request.query_params.get(name)
            if value is None:
                raise ValueError("required")
            out[name] = _ext.validate_python(value)
        except (ValidationError, ValueError) as e:
            errs = e.errors() if isinstance(e, ValidationError) else [{"msg": "required"}]
            errors += field_errors([{**x, "loc": (name,)} for x in errs])
    if errors:
        raise failed("The upload needs external_request_id, external_user_id and external_conversation_id in the query.", errors)
    return out


def fingerprint(ids: dict, digest: str) -> str:
    meaning = {"command_type": COMMAND, "user": ids["external_user_id"],
               "conversation": ids["external_conversation_id"], "sha256": digest}
    return "sha256:" + hashlib.sha256(json.dumps(meaning, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


async def ensure_store(rt: Any) -> bool:
    """The store answers and its bucket exists. Tried when the process starts and again by the first upload that
    finds it not ready: a store that is down when the platform starts costs uploads, never the start."""
    if rt.assets is None:
        return False
    if not rt.assets_ready:
        try:
            await rt.assets.ensure()
            rt.assets_ready = True
        except StoreError as e:
            log.error("asset store not ready: %s", e)
    return rt.assets_ready


async def _prior(conn, client: str, request_id: str) -> Any:
    return (await conn.execute(select(t.requests).where(
        t.requests.c.client_id == client, t.requests.c.external_request_id == request_id))).mappings().first()


def _again(prior: Any, fp: str) -> JSONResponse:
    if prior["fingerprint"] != fp:
        raise WorkforceError("IDEMPOTENCY_CONFLICT", 409, "This external_request_id was used with a different request.")
    return JSONResponse(prior["response"]["body"], status_code=201)


async def for_message(conn, client_id: str, user: str, external_conversation: str, asset_id: str) -> Any:
    """The asset a message of this audience may carry; raises the one refusal otherwise."""
    row = (await conn.execute(select(t.assets).where(t.assets.c.id == asset_id, t.assets.c.client_id == client_id))).mappings().first()
    if row is None or row["external_user_id"] != user or row["external_conversation_id"] != external_conversation:
        raise unknown_asset()
    return row


async def bind(conn, asset_id: str, conversation_id: str) -> None:
    """The first message that carries the asset ties it to the platform's conversation, for good."""
    await conn.execute(update(t.assets).where(t.assets.c.id == asset_id, t.assets.c.conversation_id.is_(None))
                       .values(conversation_id=conversation_id))


async def of_workflow(db, wf: Any, asset_ids: list[str]) -> list[dict]:
    """The assets among `asset_ids` that were sent in the conversation of `wf`, in the order asked."""
    if not asset_ids:
        return []
    async with db.engine.connect() as conn:
        rows = (await conn.execute(select(t.assets).where(
            t.assets.c.id.in_(asset_ids), t.assets.c.client_id == wf["client_id"],
            t.assets.c.conversation_id == wf["conversation_id"]))).mappings().all()
    found = {r["id"]: dict(r) for r in rows}
    return [found[a] for a in asset_ids if a in found]


def build_uploads(ctx: Any) -> APIRouter:
    r = APIRouter(route_class=UploadRoute)
    db, rt, limit = ctx.db, ctx.rt, ctx.settings.asset_max_bytes

    @r.post("/partner/assets", status_code=201)
    async def upload(request: Request):
        p = await authenticate(request, "customer", COMMAND)
        if not has_capability(p):
            raise WorkforceError("PERMISSION_DENIED", 403, "This client has not been given the capability.", {"capability": CAPABILITY})
        ids = _ids(request)
        if rt.assets is None:
            raise store_down(False)
        data = await load_body(request, limit)
        kind = assets.sniff(data)
        if kind is None:
            raise failed("The body is not a PNG, JPEG, WebP or GIF image.", [{"field": "body", "reason": "unsupported image type"}])
        digest, client = hashlib.sha256(data).hexdigest(), p.client.id
        fp = fingerprint(ids, digest)
        async with db.engine.connect() as conn:
            prior = await _prior(conn, client, ids["external_request_id"])
        if prior is not None:
            return _again(prior, fp)
        if not await ensure_store(rt):
            raise store_down(True)
        key, stamp, asset_id, rid = assets.new_key(client, kind), now(), new_id("ast"), new_id("req")
        try:
            await rt.assets.put(key, data, kind)
        except StoreError as e:
            log.error("asset upload %s: %s", p.request_id, e)
            raise store_down(True)
        body = {"asset_id": asset_id, "content_type": kind, "size": len(data), "sha256": digest,
                "external_user_id": ids["external_user_id"], "external_conversation_id": ids["external_conversation_id"],
                "created_at": iso(stamp)}
        try:
            async with db.engine.begin() as conn:
                # the request row is the idempotency claim, as for every command: a twin of this upload meets its unique key
                await conn.execute(insert(t.requests).values(
                    id=rid, client_id=client, external_request_id=ids["external_request_id"], command_type=COMMAND,
                    fingerprint=fp, status="completed", accepted_at=stamp, completed_at=stamp,
                    response={"body": body, "last_event_id": None}))
                await conn.execute(insert(t.assets).values(
                    id=asset_id, client_id=client, external_user_id=ids["external_user_id"],
                    external_conversation_id=ids["external_conversation_id"], conversation_id=None, object_key=key,
                    content_type=kind, size=len(data), sha256=digest, created_at=stamp))
        except Exception as e:
            await _discard(rt, key)  # no row names the object: it must not stay
            if not isinstance(e, IntegrityError):
                raise
            async with db.engine.connect() as conn:
                prior = await _prior(conn, client, ids["external_request_id"])
            if prior is None:
                raise
            return _again(prior, fp)
        return JSONResponse(body, status_code=201)

    return r


async def _discard(rt: Any, key: str) -> None:
    try:
        await rt.assets.delete(key)
    except StoreError as e:  # left behind: an object no row names (it is found by listing the bucket against wf_assets)
        log.error("an orphan object stays in the asset store: %s", e)
