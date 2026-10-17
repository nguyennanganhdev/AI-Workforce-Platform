"""Asset routes mounted into existing customer and provider API groups."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ..execution._utils import ExecutionError


def create_customer_asset_router(
    service: Any,
    customer_dependency: Any,
    *,
    max_request_bytes: int = 65_536,
) -> Any:
    if max_request_bytes < 1:
        raise ValueError("max_request_bytes must be positive")
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import JSONResponse

    globals()["Request"] = Request
    router = APIRouter(prefix="/partner/assets", tags=["workforce-assets"])
    customer_principal = Depends(customer_dependency)

    async def body(request: Request) -> Any:
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > max_request_bytes:
                raise ExecutionError("PAYLOAD_TOO_LARGE", 413)
        return json.loads(raw)

    async def respond(action: Any) -> Any:
        try:
            result = await action()
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="json")
            return result
        except ExecutionError as exc:
            return JSONResponse(exc.public(), status_code=exc.status)
        except PermissionError:
            error = ExecutionError("AUTHORIZATION_DENIED", 403)
            return JSONResponse(error.public(), status_code=error.status)
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError):
            return JSONResponse(
                {"error": {"code": "REQUEST_BODY_INVALID"}},
                status_code=422,
            )

    @router.post("/upload-sessions", status_code=201)
    async def upload_session(
        request: Request, principal: Any = customer_principal
    ) -> Any:
        async def action() -> Any:
            return await service.create_customer_upload(principal, await body(request))

        return await respond(action)

    @router.post("/{asset_id}/complete")
    async def complete(
        asset_id: str,
        external_user_id: str = Query(min_length=1),
        external_conversation_id: str = Query(min_length=1),
        external_ticket_id: str | None = Query(default=None, min_length=1),
        principal: Any = customer_principal,
    ) -> Any:
        return await respond(
            lambda: service.complete_customer(
                principal,
                asset_id,
                external_user_id=external_user_id,
                external_conversation_id=external_conversation_id,
                external_ticket_id=external_ticket_id,
            )
        )

    @router.post("/{asset_id}/download-url")
    async def download_url(
        asset_id: str,
        external_user_id: str = Query(min_length=1),
        external_conversation_id: str = Query(min_length=1),
        external_ticket_id: str | None = Query(default=None, min_length=1),
        principal: Any = customer_principal,
    ) -> Any:
        return await respond(
            lambda: service.customer_download(
                principal,
                asset_id,
                external_user_id=external_user_id,
                external_conversation_id=external_conversation_id,
                external_ticket_id=external_ticket_id,
            )
        )

    return router


def create_provider_asset_router(
    service: Any,
    provider_auth: Any,
    *,
    max_request_bytes: int = 65_536,
) -> Any:
    if max_request_bytes < 1:
        raise ValueError("max_request_bytes must be positive")
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    globals()["Request"] = Request
    router = APIRouter(prefix="/provider/assets", tags=["workforce-assets"])

    async def authenticated(request: Request) -> tuple[Any, bytes]:
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > max_request_bytes:
                raise ExecutionError("PAYLOAD_TOO_LARGE", 413)
        raw = bytes(payload)
        try:
            principal = await provider_auth.authenticate(raw, dict(request.headers))
        except PermissionError:
            raise ExecutionError("PROVIDER_UNAUTHENTICATED", 401) from None
        try:
            await provider_auth.authorize_integration(principal, "publish_job_event")
        except PermissionError:
            raise ExecutionError("AUTHORIZATION_DENIED", 403) from None
        return principal, raw

    async def respond(action: Any) -> Any:
        try:
            result = await action()
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="json")
            return result
        except ExecutionError as exc:
            return JSONResponse(exc.public(), status_code=exc.status)
        except PermissionError:
            error = ExecutionError("AUTHORIZATION_DENIED", 403)
            return JSONResponse(error.public(), status_code=error.status)
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError):
            return JSONResponse(
                {"error": {"code": "REQUEST_BODY_INVALID"}},
                status_code=422,
            )

    @router.post("/upload-sessions", status_code=201)
    async def upload_session(request: Request) -> Any:
        async def action() -> Any:
            principal, raw = await authenticated(request)
            return await service.create_provider_upload(principal, json.loads(raw))

        return await respond(action)

    @router.post("/{asset_id}/complete")
    async def complete(asset_id: str, request: Request) -> Any:
        async def action() -> Any:
            principal, _ = await authenticated(request)
            return await service.complete_provider(principal, asset_id)

        return await respond(action)

    return router


__all__ = ["create_customer_asset_router", "create_provider_asset_router"]
