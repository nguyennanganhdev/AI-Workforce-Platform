"""Administrator onboarding on existing residency and staff tables, in the account transaction."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from .v3_audit import audit


class Residency(BaseModel):
    unit_id: UUID
    relation: Literal["owner", "tenant", "household"]


class Shift(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_interval(self):
        if self.starts_at.utcoffset() is None or self.ends_at.utcoffset() is None or self.ends_at <= self.starts_at:
            raise ValueError("Ca làm cần múi giờ và giờ kết thúc sau giờ bắt đầu.")
        return self


class StaffProfile(BaseModel):
    management_unit_id: UUID
    employee_code: str = Field(min_length=1, max_length=80, pattern=r"\S")
    category_ids: list[UUID] = Field(min_length=1, max_length=20)
    max_concurrent_jobs: int = Field(default=1, ge=1, le=20)
    availability: Literal["available", "busy", "offline", "on_leave"] = "available"
    shifts: list[Shift] = Field(default_factory=list, max_length=31)

    @model_validator(mode="after")
    def no_overlapping_shifts(self):
        ordered = sorted(self.shifts, key=lambda s: s.starts_at)
        if any(right.starts_at < left.ends_at for left, right in zip(ordered, ordered[1:])):
            raise ValueError("Các ca làm không được chồng lấn.")
        return self


async def complete(db, tenant: str, actor: str, user: str, role: str, status: str,
                   residency: Residency | None, staff: StaffProfile | None):
    """The caller holds the membership lock. A failure rolls back access and onboarding together."""
    params = {"tenant": tenant, "user": user}
    if residency is not None:
        if role != "customer" or status != "active":
            raise HTTPException(422, "Chỉ xác minh căn hộ cho cư dân đang hoạt động.")
        unit = (await db.execute(text("""select id from units where tenant_id=cast(:tenant as uuid)
            and id=:unit and status='active'"""), {**params, "unit": residency.unit_id})).first()
        if not unit:
            raise HTTPException(404, "Căn hộ không tồn tại hoặc không hoạt động trong tenant này.")
        old = (await db.execute(text("""select id,relation,verification_status from unit_residents
            where tenant_id=cast(:tenant as uuid) and user_id=:user and unit_id=:unit
              and valid_from<=now() and (valid_to is null or valid_to>now()) for update"""),
            {**params, "unit": residency.unit_id})).mappings().all()
        if len(old) > 1:
            raise HTTPException(409, "Căn hộ có nhiều quan hệ cư trú đang hiệu lực; cần rà soát trước khi xác minh.")
        if old and old[0]["verification_status"] == "verified" and old[0]["relation"] != residency.relation:
            raise HTTPException(409, "Quan hệ đã xác minh khác dữ liệu mới. Thu hồi quan hệ cũ trước khi xác minh lại.")
        if not old or old[0]["verification_status"] != "verified":
            values = {**params, "unit": residency.unit_id, "relation": residency.relation, "actor": actor}
            if old:
                await db.execute(text("""update unit_residents set relation=:relation,verification_status='verified',
                    verified_by=:actor,verified_at=now(),updated_at=now() where id=:id and tenant_id=cast(:tenant as uuid)"""),
                    {**values, "id": old[0]["id"]})
            else:
                await db.execute(text("""insert into unit_residents(tenant_id,user_id,unit_id,relation,verification_status,
                    valid_from,verified_by,verified_at) values(cast(:tenant as uuid),:user,:unit,:relation,'verified',now(),:actor,now())"""), values)
            await audit(db, actor, "account.residency_verified", "user", user,
                        {"unit_id": str(residency.unit_id), "relation": residency.relation})
    if staff is not None:
        if role != "staff" or status != "active":
            raise HTTPException(422, "Chỉ cập nhật hồ sơ nhân viên đang hoạt động.")
        mu = (await db.execute(text("""select id from management_units where tenant_id=cast(:tenant as uuid)
            and id=:unit and status='active'"""), {**params, "unit": staff.management_unit_id})).first()
        if not mu:
            raise HTTPException(404, "Đơn vị nhân viên không tồn tại hoặc không hoạt động.")
        categories = set((await db.execute(text("""select id from service_categories
            where tenant_id=cast(:tenant as uuid) and id=any(cast(:ids as uuid[])) and enabled"""),
            {**params, "ids": [str(c) for c in staff.category_ids]})).scalars())
        if categories != set(staff.category_ids):
            raise HTTPException(422, "Chuyên môn không hợp lệ trong tenant này.")
        # Serialize employee-code checks even for two different accounts.
        await db.execute(text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
                         {"key": f"employee:{tenant}:{staff.employee_code.strip()}"})
        collision = (await db.execute(text("""select 1 from staff_profiles where tenant_id=cast(:tenant as uuid)
            and employee_code=:code and user_id<>:user"""), {**params, "code": staff.employee_code.strip()})).first()
        if collision:
            raise HTTPException(409, "Mã nhân viên đã được sử dụng.")
        profile = (await db.execute(text("select id,management_unit_id from staff_profiles where tenant_id=cast(:tenant as uuid) and user_id=:user for update"), params)).mappings().first()
        if profile and profile["management_unit_id"] != staff.management_unit_id:
            busy = (await db.execute(text("""select 1 from work_assignments a join work_orders w
                on w.id=a.work_order_id and w.tenant_id=a.tenant_id where a.tenant_id=cast(:tenant as uuid)
                and a.staff_id=:id and (a.status='accepted' or (a.status='offered' and a.offer_expires_at>now()))
                and w.status not in ('completed','cancelled','rejected') limit 1"""),
                {**params, "id": profile["id"]})).first()
            if busy:
                raise HTTPException(409, "Nhân viên còn việc đang xử lý; chưa thể chuyển đơn vị.")
        profile_id = (await db.execute(text("""insert into staff_profiles(tenant_id,user_id,management_unit_id,employee_code,
            availability,max_concurrent_jobs,active) values(cast(:tenant as uuid),:user,:unit,:code,:availability,:capacity,true)
            on conflict(tenant_id,user_id) do update set management_unit_id=excluded.management_unit_id,
              employee_code=excluded.employee_code,availability=excluded.availability,
              max_concurrent_jobs=excluded.max_concurrent_jobs,active=true,updated_at=now() returning id"""),
            {**params, "unit": staff.management_unit_id, "code": staff.employee_code.strip(),
             "availability": staff.availability, "capacity": staff.max_concurrent_jobs})).scalar_one()
        await db.execute(text("update staff_specialties set active=false where tenant_id=cast(:tenant as uuid) and staff_id=:staff"),
                         {**params, "staff": profile_id})
        for category in categories:
            await db.execute(text("""insert into staff_specialties(tenant_id,staff_id,category_id,proficiency,active)
                values(cast(:tenant as uuid),:staff,:category,'standard',true)
                on conflict(tenant_id,staff_id,category_id) do update set active=true"""),
                {**params, "staff": profile_id, "category": category})
        for shift in staff.shifts:
            old = (await db.execute(text("""select starts_at,ends_at,status from staff_shifts
                where tenant_id=cast(:tenant as uuid) and staff_id=:staff and status in ('scheduled','available')
                and starts_at<:end and ends_at>:start for update"""),
                {**params, "staff": profile_id, "start": shift.starts_at, "end": shift.ends_at})).mappings().all()
            if old:
                if len(old) == 1 and old[0]["starts_at"] == shift.starts_at and old[0]["ends_at"] == shift.ends_at:
                    continue
                raise HTTPException(409, "Ca làm chồng lấn với ca đã có.")
            await db.execute(text("""insert into staff_shifts(tenant_id,staff_id,starts_at,ends_at,status)
                values(cast(:tenant as uuid),:staff,:start,:end,'available')"""),
                {**params, "staff": profile_id, "start": shift.starts_at, "end": shift.ends_at})
        await audit(db, actor, "account.staff_profile_saved", "user", user,
                    {"staff_id": str(profile_id), "management_unit_id": str(staff.management_unit_id)})
    if role != "staff" or status != "active":
        await db.execute(text("update staff_profiles set active=false,updated_at=now() where tenant_id=cast(:tenant as uuid) and user_id=:user and active"), params)


async def detail(db, tenant: str, user: str):
    params = {"tenant": tenant, "user": user}
    residencies = (await db.execute(text("""select ur.id,ur.unit_id,ur.relation,ur.verification_status,
        u.code,b.code as building_code from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        where ur.tenant_id=cast(:tenant as uuid) and ur.user_id=:user and ur.valid_from<=now()
          and (ur.valid_to is null or ur.valid_to>now()) order by b.code,u.code"""), params)).mappings().all()
    staff = (await db.execute(text("select * from staff_profiles where tenant_id=cast(:tenant as uuid) and user_id=:user"), params)).mappings().first()
    profile = dict(staff) if staff else None
    if profile:
        profile["category_ids"] = list((await db.execute(text("select category_id from staff_specialties where tenant_id=cast(:tenant as uuid) and staff_id=:staff and active"),
            {**params, "staff": profile["id"]})).scalars())
        profile["shifts"] = [dict(s) for s in (await db.execute(text("""select id,starts_at,ends_at,status from staff_shifts
            where tenant_id=cast(:tenant as uuid) and staff_id=:staff and ends_at>now() and status in ('scheduled','available')
            order by starts_at"""), {**params, "staff": profile["id"]})).mappings()]
    return {"residencies": [dict(r) for r in residencies], "staff_profile": profile}
