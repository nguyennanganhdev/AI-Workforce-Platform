# -*- coding: utf-8 -*-
"""Skill router — the user's own library of installed skills.

The skill counterpart of :mod:`._mcp`: this is the user-level collection
an install lands in, distinct from ``/workspace/skill``, which manages
the skills present in one session's workspace.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal
import hashlib

from ..deps import get_current_user_id, get_storage, get_current_principal
from ..storage import SkillRecord, StorageBase
from ._schema import SkillView

skill_router = APIRouter(prefix="/skill", tags=["skill"])


class LocalSkillRequest(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    description: str = Field(min_length=1, max_length=1000)
    markdown: str = Field(min_length=40, max_length=100000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SkillReviewRequest(BaseModel):
    status: Literal["approved", "revoked"]


@skill_router.post("", status_code=201)
async def create_local_skill(body: LocalSkillRequest, user_id=Depends(get_current_user_id), storage=Depends(get_storage)):
    if await storage.get_skill_by_name(user_id, body.name):
        raise HTTPException(409, "Tên skill đã có; dùng tên/version mới để giữ bản cũ.")
    digest = hashlib.sha256(body.markdown.encode()).hexdigest()
    record = SkillRecord(user_id=user_id, name=body.name, description=body.description, markdown=body.markdown,
                         tags=body.tags, version=digest[:16], review_status="candidate", enabled=False)
    await storage.upsert_skill(user_id, record)
    return SkillView.from_record(record)


@skill_router.post("/{skill_id}/review")
async def review_skill(skill_id: str, body: SkillReviewRequest, principal=Depends(get_current_principal), storage=Depends(get_storage)):
    from .._service._catalog_resources import require_catalog_management
    await require_catalog_management(storage, principal.user_id, private_kind="skill")
    record = await storage.get_skill(principal.user_id, skill_id)
    if record is None:
        raise HTTPException(404, "Không có skill trong thư viện của bạn.")
    record.review_status = body.status
    record.enabled = body.status == "approved"
    record.reviewed_by = principal.user_id
    await storage.upsert_skill(principal.user_id, record)
    return SkillView.from_record(record)


@skill_router.get("")
async def list_skills(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[SkillView]:
    """Return every skill the user has installed, ordered by name."""
    authority = getattr(storage, "vin_platform_service", None)
    if authority is not None and (await authority.context(user_id)).role == "VIN_USER":
        from ..vin_platform._resources import catalog_records
        granted = [SkillView.from_record(record).model_copy(update={"editable": False, "url": None})
            for _, record in await catalog_records(authority, user_id, "skill")]
        ids = {view.id for view in granted}
        own = [SkillView.from_record(record) for record in await storage.list_skills(user_id)
               if record.id not in ids and record.user_id == user_id]
        return granted + sorted(own, key=lambda view: view.name)
    records = await storage.list_skills(user_id)
    return sorted(
        (SkillView.from_record(r) for r in records),
        key=lambda view: view.name,
    )


@skill_router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> SkillRecord:
    """Return one installed skill, including its ``SKILL.md`` body."""
    authority = getattr(storage, "vin_platform_service", None)
    own = await storage.get_skill(user_id, skill_id)
    if own is not None and own.user_id == user_id:
        return own
    if authority is not None and (await authority.context(user_id)).role == "VIN_USER":
        context = await authority.context(user_id)
        _, record = await authority.resolve_catalog(context, "skill", skill_id, permission="view")
        # No archive/auth/source metadata is needed to view an approved skill.
        return record.model_copy(update={"archive_base64": None, "url": None})
    record = await storage.get_skill(user_id, skill_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No installed skill with id {skill_id!r}.",
        )
    return record


@skill_router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> None:
    """Remove a skill from the user's library.

    Workspaces that already hold this skill keep their copy — the files
    were extracted into the workspace, and this record was only where
    they came from.
    """
    if not await storage.delete_skill(user_id, skill_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No installed skill with id {skill_id!r}.",
        )
