"""Private asset transfer contracts for customer/provider workflows."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from ._base import OpaqueId, ShortCode, WorkforceModel


class AssetOrigin(StrEnum):
    CUSTOMER = "customer"
    PROVIDER = "provider"


class AssetStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    ACTIVE = "active"
    REJECTED = "rejected"
    DELETED = "deleted"


class AssetReferenceInput(WorkforceModel):
    """Stable reference carried by chat/events; never accepts an arbitrary URL."""

    asset_id: OpaqueId


class CustomerAssetUploadRequest(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    external_management_ref: ShortCode
    external_user_id: OpaqueId
    external_ticket_id: OpaqueId | None = None
    external_conversation_id: OpaqueId
    residence_id: OpaqueId | None = None
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(gt=0, le=20 * 1024 * 1024, strict=True)


class ProviderAssetUploadRequest(WorkforceModel):
    schema_version: str = Field(pattern="^1$")
    client_reference: OpaqueId | None = None
    external_job_id: OpaqueId | None = None
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(gt=0, le=20 * 1024 * 1024, strict=True)

    @model_validator(mode="after")
    def require_correlation(self) -> "ProviderAssetUploadRequest":
        if self.client_reference is None and self.external_job_id is None:
            raise ValueError("client_reference or external_job_id is required")
        return self


class AssetUploadSession(WorkforceModel):
    asset_id: OpaqueId
    upload_method: str = Field(default="PUT", pattern="^PUT$")
    upload_url: str = Field(min_length=1)
    required_headers: dict[str, str]
    expires_at: datetime
    complete_url: str = Field(min_length=1)


class AssetProjection(WorkforceModel):
    asset_id: OpaqueId
    origin: AssetOrigin
    status: AssetStatus
    filename: str
    content_type: str
    byte_size: int = Field(gt=0)
    workflow_id: OpaqueId | None = None
    created_at: datetime


class AssetDownloadGrant(WorkforceModel):
    asset_id: OpaqueId
    filename: str
    content_type: str
    byte_size: int = Field(gt=0)
    download_url: str = Field(min_length=1)
    expires_at: datetime


__all__ = [
    "AssetDownloadGrant",
    "AssetOrigin",
    "AssetProjection",
    "AssetReferenceInput",
    "AssetStatus",
    "AssetUploadSession",
    "CustomerAssetUploadRequest",
    "ProviderAssetUploadRequest",
]
