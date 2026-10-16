"""Partner onboarding endpoints (contract 8): confirm a route, sync a residence."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import and_, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .auth import RUNTIME_OPS, PartnerPrincipal, require, route_denied
from .common import iso, now
from .errors import WorkforceError, field_errors, failed, json_body
from .schemas import ConfirmRouteIn, ExtId, ResidenceIn

_ext_id = TypeAdapter(ExtId)


def revision_conflict(current: int) -> WorkforceError:
    return WorkforceError("REVISION_CONFLICT", 409, "Revision does not match the current one.",
                          {"current_revision": current})


def route_conflict(message: str, **details) -> WorkforceError:
    return WorkforceError("ROUTE_CONFLICT", 409, message, details)


def build_onboarding(r: APIRouter, ctx: Any) -> None:
    db = ctx.db

    def allowed(p: PartnerPrincipal) -> list[str]:
        return [op for op in RUNTIME_OPS if op in p.operations]

    def confirmed(route, p: PartnerPrincipal) -> dict:
        return {"route_id": route["id"], "external_management_ref": route["external_management_ref"],
                "status": route["status"], "revision": route["revision"],
                "allowed_operations": allowed(p)}

    @r.post("/partner/routes/{route_id}/confirm")
    async def confirm_route(route_id: str, request: Request,
                            p: PartnerPrincipal = Depends(require("confirm_route"))):
        body = await json_body(request, ConfirmRouteIn)
        async with db.engine.begin() as conn:
            route = (await conn.execute(select(t.routes).where(
                t.routes.c.id == route_id, t.routes.c.client_id == p.client.id))).mappings().first()
            # A route of another client answers like one that does not exist.
            if route is None or not p.covers(route_id):
                raise route_denied()
            if body.external_management_ref != route["external_management_ref"]:
                raise route_conflict("external_management_ref does not match this route.",
                                     reason="ref_mismatch")
            if route["status"] == "active":
                if body.expected_revision == route["revision"] - 1:  # the confirmation seen again
                    return confirmed(route, p)
                raise revision_conflict(route["revision"])
            if route["status"] != "pending":
                raise route_conflict("Route cannot be confirmed in its current state.",
                                     status=route["status"])
            if body.expected_revision != route["revision"]:
                raise revision_conflict(route["revision"])
            other = (await conn.execute(select(t.routes.c.id).where(
                t.routes.c.client_id == p.client.id, t.routes.c.status == "active",
                t.routes.c.id != route_id,
                t.routes.c.external_management_ref == route["external_management_ref"]))).first()
            if other is not None:
                raise route_conflict("Another active route already uses this external_management_ref.")
            try:
                done = await conn.execute(update(t.routes).where(
                    t.routes.c.id == route_id, t.routes.c.status == "pending",
                    t.routes.c.revision == route["revision"]).values(
                    status="active", revision=route["revision"] + 1))
            except IntegrityError:
                raise route_conflict("Another active route already uses this external_management_ref.")
            route = (await conn.execute(select(t.routes).where(t.routes.c.id == route_id))).mappings().one()
            if done.rowcount != 1:  # a parallel request moved it first: if it was the same confirmation, replay it
                if route["status"] == "active" and body.expected_revision == route["revision"] - 1:
                    return confirmed(route, p)
                raise revision_conflict(route["revision"])
        return confirmed(route, p)

    @r.put("/partner/residences/{residence_id}")
    async def sync_residence(residence_id: str, request: Request,
                             p: PartnerPrincipal = Depends(require("sync_residence"))):
        try:
            _ext_id.validate_python(residence_id)
        except ValidationError as e:
            raise failed("residence_id is not valid.", field_errors([{**x, "loc": ("residence_id",)}
                                                               for x in e.errors()]))
        body = await json_body(request, ResidenceIn)
        client = p.client.id
        async with db.engine.begin() as conn:
            refs = (await conn.execute(select(t.routes).where(
                t.routes.c.client_id == client,
                t.routes.c.external_management_ref == body.external_management_ref)
                .order_by(t.routes.c.created_at.desc()))).mappings().all()
            route = next((x for x in refs if x["status"] == "active"), None)
            if route is None:
                # The reason only goes to a key that covers one of these routes; any other key
                # gets the answer for an unknown ref, so it cannot probe other offices.
                known = any(p.covers(x["id"]) for x in refs)
                raise route_denied(**({"reason": "route_not_active"} if known else {}))
            if not p.covers(route["id"]):
                raise route_denied()

            key = and_(t.residences.c.client_id == client, t.residences.c.residence_id == residence_id,
                       t.residences.c.external_user_id == body.external_user_id)
            cur = (await conn.execute(select(t.residences).where(key))).mappings().first()
            stamp, created = now(), False
            if cur is None:
                if body.expected_revision not in (None, 0):
                    raise revision_conflict(0)
                row = dict(client_id=client, residence_id=residence_id, route_id=route["id"],
                           external_user_id=body.external_user_id, status=body.status,
                           revision=1, updated_at=stamp)
                try:
                    async with conn.begin_nested():
                        await conn.execute(insert(t.residences).values(**row))
                    created = True
                except IntegrityError:  # a parallel create won: judge the row it left, as a later call would
                    cur = (await conn.execute(select(t.residences).where(key))).mappings().one()
            if not created:
                if cur["route_id"] != route["id"] and not p.covers(cur["route_id"]):
                    raise route_denied()  # the residence lives on a route this key does not cover
                if cur["route_id"] == route["id"] and cur["status"] == body.status:
                    row = dict(cur)  # same content: nothing changes, nothing is bumped
                else:
                    if body.expected_revision != cur["revision"]:
                        raise revision_conflict(cur["revision"])
                    row = {**cur, "route_id": route["id"], "status": body.status,
                           "revision": cur["revision"] + 1, "updated_at": stamp}
                    done = await conn.execute(update(t.residences).where(
                        key, t.residences.c.revision == cur["revision"]).values(
                        route_id=route["id"], status=body.status, revision=row["revision"],
                        updated_at=stamp))
                    if done.rowcount != 1:
                        raise revision_conflict(cur["revision"])
        return JSONResponse(
            {"residence_id": residence_id, "external_user_id": body.external_user_id,
             "external_management_ref": body.external_management_ref, "status": row["status"],
             "revision": row["revision"], "updated_at": iso(row["updated_at"])},
            status_code=201 if created else 200)
