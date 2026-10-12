"""The public error model (contract 6.3) and the route class that applies it.

`WorkforceRoute` handles errors for the /workforce router only. The global
handlers of AgentScope and of the admin API stay as they are.
"""
from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError

from . import crypto
from .tables import new_id

log = logging.getLogger("awp.workforce")
M = TypeVar("M", bound=BaseModel)


class WorkforceError(Exception):
    """An error the partner sees: {"error": {code, message, details, request_id, retryable}}."""

    def __init__(self, code: str, http: int, message: str, details: dict | None = None,
                 retryable: bool = False, headers: dict[str, str] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.http, self.message = code, http, message
        self.details, self.retryable, self.headers = details or {}, retryable, headers or {}

    def response(self, request_id: str) -> JSONResponse:
        body = {"error": {"code": self.code, "message": self.message, "details": self.details,
                          "request_id": request_id, "retryable": self.retryable}}
        return JSONResponse(body, status_code=self.http, headers=self.headers)


def unauthenticated(reason: str | None = None) -> WorkforceError:
    return WorkforceError("UNAUTHENTICATED", 401, "Credential is missing, invalid, expired or revoked.",
                          {"reason": reason} if reason else {})


def too_large(limit: int) -> WorkforceError:
    return WorkforceError("PAYLOAD_TOO_LARGE", 413, f"Request body is larger than {limit} bytes.",
                          {"limit_bytes": limit})


def invalid(message: str, **details: Any) -> WorkforceError:
    return WorkforceError("INVALID_REQUEST", 400, message, details)


def failed(message: str, errors: list[dict] | None = None) -> WorkforceError:
    return WorkforceError("VALIDATION_FAILED", 422, message, {"errors": errors or []})


def field_errors(items: list[dict]) -> list[dict]:
    """Field and reason only: never echo the submitted value back."""
    return [{"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
             "reason": e.get("msg", "invalid")} for e in items[:20]]


async def load_body(request: Request, limit: int | None = None) -> bytes:
    """Read the body, refusing as soon as it passes the limit (not after it is all in memory)."""
    limit = request.app.state.wf.settings.wf_body_limit if limit is None else limit
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large(limit)
    size, chunks = 0, []
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_large(limit)
        chunks.append(chunk)
    raw = b"".join(chunks)
    request._body = raw  # what Request.body() returns from now on
    return raw


def _is_json(content_type: str) -> bool:
    media, _, params = content_type.partition(";")
    params = params.strip().lower().replace(" ", "")
    return media.strip().lower() == "application/json" and params in ("", "charset=utf-8", 'charset="utf-8"')


def _no_constant(name: str):
    raise ValueError(f"{name} is not JSON")


def _finite(text: str) -> float:
    value = float(text)
    if value in (float("inf"), float("-inf")):
        raise ValueError("a number too large for JSON")
    return value


def strict_loads(text: str) -> Any:
    """json.loads as RFC 8259 has it: NaN, Infinity and numbers that overflow to it are not JSON. A database JSON
    column would take them on SQLite and refuse them on PostgreSQL, for ever, on every retry."""
    return json.loads(text, parse_constant=_no_constant, parse_float=_finite)


async def json_object(request: Request) -> dict:
    """The JSON body as a dict: 400 when it is not a JSON object."""
    if not _is_json(request.headers.get("content-type", "")):
        raise invalid("Content-Type must be application/json (UTF-8).")
    raw = await request.body()
    try:
        data = strict_loads(raw.decode("utf-8"))
    except Exception:  # ValueError, UnicodeDecodeError, and RecursionError on deep nesting
        raise invalid("Body is not valid UTF-8 JSON.")
    if not isinstance(data, dict):
        raise invalid("Body must be a JSON object.")
    return data


def validated(data: dict, model: type[M]) -> M:
    try:
        # strict: "1", true and 1.0 are not integers (contract 6.3 puts type errors in 422)
        return model.model_validate(data, strict=True)
    except ValidationError as e:
        raise failed("Request does not match the schema.", field_errors(e.errors()))


async def json_body(request: Request, model: type[M]) -> M:
    """The JSON body as `model`: 400 when it is not a JSON object, 422 when it breaks the schema."""
    return validated(await json_object(request), model)


def correlation_id(request: Request) -> str | None:
    """X-Correlation-Id is for the logs only (contract 6.1): cut short and stripped of control characters."""
    raw = request.headers.get("x-correlation-id", "")[:128]
    return "".join(c for c in raw if c.isprintable()) or None


class WorkforceRoute(APIRoute):
    """Applies the error model. A credential-less call is refused before its body is read."""
    authenticated = True
    body_limit: str | None = "wf_body_limit"  # the setting that caps the body; None: the endpoint reads the body itself

    def get_route_handler(self):
        inner = super().get_route_handler()
        authenticated, body_limit = self.authenticated, self.body_limit

        async def handler(request: Request) -> Response:
            rid = request.state.request_id = new_id("req")
            request.state.correlation_id = cid = correlation_id(request)
            log.info("workforce %s %s request=%s correlation=%s", request.method,
                     request.url.path, rid, cid)
            try:
                if authenticated and crypto.parse_authorization(request.headers.get("authorization")) is None:
                    raise unauthenticated()
                if body_limit:
                    await load_body(request, getattr(request.app.state.wf.settings, body_limit))
                return await inner(request)
            except WorkforceError as e:
                return e.response(rid)
            except RequestValidationError as e:
                errs = e.errors()
                if any(str(x.get("type", "")).startswith("json") for x in errs):
                    return invalid("Body is not valid UTF-8 JSON.").response(rid)
                return failed("Request does not match the schema.", field_errors(errs)).response(rid)
            except HTTPException as e:
                code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(e.status_code, "INVALID_REQUEST")
                return WorkforceError(code, e.status_code, "Request cannot be served.").response(rid)
            except Exception:
                log.exception("workforce request failed (%s, correlation %s)", rid, cid)
                return WorkforceError("INTERNAL_ERROR", 500, "The request could not be processed.",
                                      retryable=True).response(rid)

        return handler


class UploadRoute(WorkforceRoute):
    """A route whose body is an image, not JSON. Its limit is larger (AWP_ASSET_MAX_BYTES), so nothing of the body is
    read here: the endpoint reads it (load_body) after it has checked the key, the operation and the capability."""
    body_limit = None


class OpenRoute(WorkforceRoute):
    """For paths that need no credential (the 404 catch-all)."""
    authenticated = False
