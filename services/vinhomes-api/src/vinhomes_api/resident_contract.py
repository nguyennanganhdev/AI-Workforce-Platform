"""Resident v0.1 public DTOs and HTTP boundary. No internal SQL rows escape here."""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

BASE = "/api/domains/vinhomes/resident"
OPERATIONS_BASE = "/api/domains/vinhomes/operations/resident-cases"
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
PHOTO_LIMIT = 10 * 1024 * 1024
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
Status = Literal["received", "processing", "confirmation", "completed"]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=5000)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Location(ContractModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CreateRequest(ContractModel):
    apartmentId: UUID
    description: Description
    location: Location
    photoIds: list[UUID] = Field(max_length=3)

    @field_validator("photoIds")
    @classmethod
    def unique_photos(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("photoIds must be unique")
        return value


class ResolutionCommand(ContractModel):
    expectedVersion: Annotated[StrictInt, Field(ge=1)]
    resolutionRevision: UUID


class ReworkCommand(ResolutionCommand):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2000)]


class Apartment(ContractModel):
    id: str
    label: str
    projectId: str
    projectName: str
    towerId: str


class ProfileUser(ContractModel):
    id: str
    displayName: str


class UploadLimits(ContractModel):
    maxPhotosPerRequest: int = 3
    maxPhotoBytes: int = PHOTO_LIMIT
    allowedPhotoTypes: list[str] = Field(default_factory=lambda: list(PHOTO_TYPES))


class Profile(ContractModel):
    user: ProfileUser
    apartments: list[Apartment]
    limits: UploadLimits = Field(default_factory=UploadLimits)


class Photo(ContractModel):
    id: str
    name: str
    url: str
    urlExpiresAt: datetime


class UploadedPhoto(Photo):
    status: Literal["ready"] = "ready"


class PhotoPage(ContractModel):
    items: list[Photo]


class RequestSummary(ContractModel):
    id: str
    code: str
    title: str
    status: Status
    createdAt: datetime
    updatedAt: datetime
    version: int


class RequestPage(ContractModel):
    items: list[RequestSummary]
    nextCursor: str | None


class PublicEvent(ContractModel):
    id: str
    label: str
    at: datetime
    note: str | None = None


class Resolution(ContractModel):
    summary: str
    publishedAt: datetime
    photos: list[Photo]


class Permissions(ContractModel):
    canConfirm: bool
    canRequestRework: bool


class RequestView(RequestSummary):
    description: str
    apartmentId: str
    location: str
    photos: list[Photo]
    events: list[PublicEvent]
    eventsNextCursor: str | None
    resolutionRevision: str | None
    resolution: Resolution | None
    permissions: Permissions


class VersionCommand(ContractModel):
    expectedVersion: Annotated[StrictInt, Field(ge=1)]


class LinkTicket(VersionCommand):
    ticketId: UUID


class MaterializeTicket(VersionCommand):
    categoryId: UUID
    requestKind: Literal["incident", "service_request"] = "incident"
    contactPhone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None = None


class PublishResolution(VersionCommand):
    summary: Description
    photoIds: list[UUID] = Field(default_factory=list, max_length=20)

    _unique_photos = field_validator("photoIds")(CreateRequest.unique_photos.__func__)


class ResidentPlanDecision(ContractModel):
    expectedVersion: Annotated[StrictInt, Field(ge=0)]
    decision: Literal['approve', 'reject']
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ResidentPlan(ContractModel):
    id: str
    title: str
    status: Literal['management_pending', 'resident_pending', 'approved', 'rejected']
    version: int
    estimatedAmount: str
    steps: list[str]
    canDecide: bool


class ResidentPlanPage(ContractModel):
    items: list[ResidentPlan]


class StaffCaseSummary(RequestSummary):
    apartmentId: str
    requesterUserId: str


class StaffCasePage(ContractModel):
    items: list[StaffCaseSummary]
    nextCursor: str | None


class ResidentResponse(ContractModel):
    id: str
    resolutionRevision: str
    decision: Literal['confirm', 'reopen']
    reason: str | None
    createdAt: datetime


class StaffCaseDetail(ContractModel):
    request: RequestView
    requesterUserId: str
    requesterDisplayName: str | None = None
    requesterPhone: str | None = None
    apartmentLabel: str | None = None
    tenantId: str | None = None
    ticketIds: list[str]
    responses: list[ResidentResponse]
    ticketId: str | None = None


class ErrorDetail(ContractModel):
    code: str
    message: str
    correlationId: str
    fieldErrors: dict[str, list[str]] = Field(default_factory=dict)
    currentVersion: int | None = None


class ErrorEnvelope(ContractModel):
    error: ErrorDetail


def fail(status: int, code: str, message: str, **details: object) -> None:
    raise HTTPException(status, {"code": code, "message": message, **details})


def is_contract(path: str) -> bool:
    return path == BASE or path.startswith(BASE + "/") or path == OPERATIONS_BASE or path.startswith(OPERATIONS_BASE + "/")


def correlation(request: Request) -> str:
    if not hasattr(request.state, "resident_correlation"):
        request.state.resident_correlation = str(uuid4())
    return request.state.resident_correlation


def error_response(request: Request, status: int, code: str, message: str,
                   headers: dict[str, str] | None = None, **details: object) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorDetail(code=code, message=message,
                         correlationId=correlation(request), **details)).model_dump(mode="json", exclude_none=True)
    return JSONResponse(body, status, headers={"Cache-Control": "no-store", "X-Correlation-ID": correlation(request), **(headers or {})})


async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if not is_contract(request.url.path):
        return JSONResponse({"detail": exc.detail}, exc.status_code, headers=exc.headers)
    default_codes = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "APARTMENT_ACCESS_DENIED",
                     404: "REQUEST_NOT_FOUND", 409: "INVALID_STATE", 413: "PAYLOAD_TOO_LARGE",
                     415: "UNSUPPORTED_MEDIA_TYPE", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED",
                     503: "SERVICE_UNAVAILABLE"}
    detail = exc.detail if isinstance(exc.detail, dict) and "code" in exc.detail else {}
    return error_response(request, exc.status_code, detail.get("code", default_codes.get(exc.status_code, "BAD_REQUEST")),
                          detail.get("message", str(exc.detail) if isinstance(exc.detail, str) else "Request failed"),
                          headers=exc.headers, **{k: v for k, v in detail.items() if k in {"fieldErrors", "currentVersion"}})


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not is_contract(request.url.path):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    fields: dict[str, list[str]] = {}
    malformed = False
    bad_header = False
    for error in exc.errors():
        malformed |= error["type"] == "json_invalid"
        bad_header |= error["loc"][:2] == ("header", "Idempotency-Key")
        name = ".".join(str(p) for p in error["loc"][1:]) or str(error["loc"][0])
        fields.setdefault(name, []).append(error["msg"])
    return error_response(request, 400 if malformed or bad_header else 422,
                          "BAD_REQUEST" if malformed or bad_header else "VALIDATION_ERROR", "Dữ liệu không hợp lệ.", fieldErrors=fields)


def key_header(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(value) <= 128 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        fail(400, "BAD_REQUEST", "Idempotency-Key phải có 8–128 ký tự ASCII không chứa khoảng trắng.")
    return value


def require_key(request: Request, value: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]) -> str:
    return key_header(request)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def encode_cursor(request: Request, scope: object, at: datetime, row_id: object) -> str:
    payload = json.dumps({"scope": digest(scope), "at": at.isoformat(), "id": str(row_id)}, separators=(",", ":")).encode()
    tag = hmac.new(request.app.state.image_access_key, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + tag).decode().rstrip("=")


def decode_cursor(request: Request, scope: object, value: str | None) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        if len(value) > 1024:
            raise ValueError()
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        payload, tag = raw[:-32], raw[-32:]
        if not hmac.compare_digest(tag, hmac.new(request.app.state.image_access_key, payload, hashlib.sha256).digest()):
            raise ValueError()
        data = json.loads(payload)
        at = datetime.fromisoformat(data["at"])
        if data["scope"] != digest(scope) or at.tzinfo is None:
            raise ValueError()
        return at, UUID(data["id"])
    except (ValueError, KeyError, TypeError, UnicodeError):
        fail(400, "BAD_REQUEST", "Cursor không hợp lệ hoặc thuộc truy vấn khác.")


class ResidentBoundary:
    """Enforce byte limits before Starlette parses/spools a multipart request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not is_contract(scope["path"]):
            return await self.app(scope, receive, send)
        scope.setdefault("state", {})["resident_correlation"] = str(uuid4())
        request = Request(scope)
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            settings = scope["app"].state.settings
            origin = request.headers.get("origin")
            trusted = {*settings.resident_allowed_origins, str(request.base_url).rstrip("/")}
            if (origin and origin not in trusted) or (not origin and not (settings.demo_mode or settings.dev_user_id)):
                response = error_response(request, 403, "ORIGIN_DENIED", "Origin không được phép thực hiện thao tác.")
                return await response(scope, receive, send)
            limit = 12 * 1024 * 1024 if scope["path"] == BASE + "/photos" else 64 * 1024
            chunks, size = [], 0
            while True:
                item = await receive()
                if item["type"] == "http.disconnect":
                    return
                size += len(item.get("body", b""))
                if size > limit:
                    response = error_response(request, 413, "PAYLOAD_TOO_LARGE", "Nội dung gửi vượt giới hạn.")
                    return await response(scope, receive, send)
                chunks.append(item)
                if not item.get("more_body", False):
                    break
            iterator = iter(chunks)

            async def bounded_receive():
                return next(iterator, {"type": "http.request", "body": b"", "more_body": False})

            receive = bounded_receive

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in {b"cache-control", b"x-correlation-id"}]
                message["headers"] = [*headers, (b"cache-control", b"no-store"),
                                      (b"x-correlation-id", correlation(request).encode())]
            await send(message)

        await self.app(scope, receive, private_send)
