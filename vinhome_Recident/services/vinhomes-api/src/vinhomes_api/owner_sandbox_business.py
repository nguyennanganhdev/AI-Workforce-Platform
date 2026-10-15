"""Idempotent, labelled business fixtures for the isolated OP1 sandbox, never production."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg

from .bootstrap import DOMAIN, OP1
from .database import TENANT, _url
from .owner_sandbox import ADMIN, MARKER, guard, uid
from .password_auth import password_hash

PROFILE = "op1-business-simulation-v1"


async def extend(url, now=None):
    guard(url)
    now = now or datetime.now(UTC)
    today = now.date()
    tenant = UUID(TENANT)
    conn = await asyncpg.connect(_url(url))
    credentials = []
    try:
        async with conn.transaction():
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended(current_database(),0))"
            )
            if (
                await conn.fetchval(
                    "select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"
                )
                != MARKER
            ):
                raise ValueError(
                    "Business fixtures require the synthetic sandbox marker"
                )
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            zone, building, scope = (
                uid("zone", "SIM-OP1-ZONE"),
                uid("building", "SIM-OP1-TOWER"),
                uid("scope", "SIM-OP1-TOWER"),
            )
            metadata = await conn.fetchval(
                "select metadata from zones where id=$1", zone
            )
            if metadata is None:
                raise ValueError("Materialize the complete technical sandbox first")
            metadata = json.loads(metadata)
            if metadata.get("business_profile") == PROFILE:
                return {
                    "profile": PROFILE,
                    "idempotent_replay": True,
                    "credentials": [],
                }
            # Refuse to overlap manually supplied data or silently rewrite business history.
            for table in (
                "vehicles",
                "access_cards",
                "visitor_passes",
                "debit_notes",
                "amenities",
                "construction_permits",
                "service_requests",
            ):
                if await conn.fetchval("select count(*) from " + table):
                    raise ValueError(
                        "Business extension requires empty service datasets"
                    )
            operator = uid("operator", "SIM-TECH-OPERATOR")
            categories = {
                r["code"]: r["id"]
                for r in await conn.fetch(
                    "select id,code from service_categories where tenant_id=$1", tenant
                )
            }
            for code, name in (
                ("access", "Thẻ cư dân"),
                ("visitors", "Khách ra vào"),
                ("billing", "Công nợ"),
                ("amenities", "Tiện ích/booking"),
                ("renovation", "Cải tạo"),
            ):
                categories[code] = uid("category", code)
                await conn.execute(
                    "insert into service_categories(id,tenant_id,code,name) values($1,$2,$3,$4)",
                    categories[code],
                    tenant,
                    code,
                    name,
                )
            for code in (
                "security",
                "sanitation",
                "access",
                "visitors",
                "billing",
                "amenities",
                "renovation",
            ):
                await conn.execute(
                    "insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from) values($1,$2,$3,$4,$5,$6)",
                    uid("coverage", code),
                    tenant,
                    operator,
                    scope,
                    categories[code],
                    now - timedelta(days=1),
                )
                for kind in ("incident", "service_request"):
                    await conn.execute(
                        """insert into sla_policies(id,tenant_id,management_unit_id,category_id,domain_id,request_kind,priority,response_minutes,resolution_minutes,effective_from,version_no)
                        values($1,$2,$3,$4,$5,$6,'normal',30,240,$7,1)""",
                        uid("business-sla", code + kind),
                        tenant,
                        operator,
                        categories[code],
                        DOMAIN,
                        kind,
                        now - timedelta(days=1),
                    )
            for team, specialties in (
                ("security", ("security", "access", "visitors")),
                ("sanitation", ("sanitation",)),
                ("desk", ("billing", "amenities", "renovation")),
            ):
                for index in (1, 2):
                    user = f"sim-{team}-{index}"
                    staff = uid("staff", user)
                    password = secrets.token_urlsafe(24)
                    email = f"{team}{index}@op1-sandbox.test"
                    name = f"[MÔ PHỎNG] {team} {index}"
                    await conn.execute(
                        "insert into users(id,email,name,status,email_verified) values($1,$2,$3,'active',true)",
                        user,
                        email,
                        name,
                    )
                    await conn.execute(
                        "insert into tenant_memberships(id,tenant_id,user_id,status) values($1,$2,$3,'active')",
                        uid("membership", user),
                        tenant,
                        user,
                    )
                    await conn.execute(
                        "insert into accounts(id,account_id,provider_id,user_id,password) values($1,$2,'vinhomes-password-v1',$2,$3)",
                        str(uid("account", user)),
                        user,
                        password_hash(password),
                    )
                    await conn.execute(
                        "insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,'staff',$5,$6)",
                        uid("role", user),
                        tenant,
                        uid("membership", user),
                        scope,
                        ADMIN,
                        now - timedelta(days=1),
                    )
                    await conn.execute(
                        "insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability,max_concurrent_jobs) values($1,$2,$3,$4,$5,'available',1)",
                        staff,
                        tenant,
                        user,
                        operator,
                        user.upper(),
                    )
                    for code in specialties:
                        await conn.execute(
                            "insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard')",
                            tenant,
                            staff,
                            categories[code],
                        )
                    for day in range(3):
                        start = now - timedelta(minutes=30) + timedelta(days=day)
                        await conn.execute(
                            "insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) values($1,$2,$3,$4,$5,'available')",
                            uid("shift", user + str(day)),
                            tenant,
                            staff,
                            start,
                            start + timedelta(hours=8),
                        )
                    credentials.append(
                        {
                            "user_id": user,
                            "email": email,
                            "password": password,
                            "role": "staff",
                            "specialties": list(specialties),
                            "backup_user_id": f"sim-{team}-{3 - index}",
                            "data_mode": "synthetic_test",
                        }
                    )
            await conn.execute(
                """insert into zone_settings(tenant_id,zone_id,visit_max_waiting,visit_max_days_ahead,visit_max_hours,visit_auto_approve_purposes,visit_auto_approve_max_guests,card_limit_resident,card_limit_vehicle,amenity_payment_hold_minutes,note)
                values($1,$2,5,7,12,array['family_visit','delivery'],5,4,2,15,'MÔ PHỎNG: chính sách sandbox, không phải quy định Vinhomes')""",
                tenant,
                zone,
            )
            for index in (1, 2):
                unit, user = (
                    uid("unit", f"SIM-UNIT-{index:03d}"),
                    f"sim-resident-{index}",
                )
                vehicle = uid("vehicle", str(index))
                await conn.execute(
                    "insert into vehicles(id,tenant_id,unit_id,owner_user_id,owner_name,kind,plate_no,status) values($1,$2,$3,$4,$5,'motorbike',$6,'active')",
                    vehicle,
                    tenant,
                    unit,
                    user,
                    f"[MÔ PHỎNG] Cư dân {index}",
                    f"SIM-PLATE-{index}",
                )
                for kind in ("resident", "vehicle"):
                    await conn.execute(
                        """insert into access_cards(id,tenant_id,card_no,kind,holder_user_id,holder_name,unit_id,vehicle_id,status,valid_from,valid_to,monthly_fee)
                        values($1,$2,$3,$4,$5,$6,$7,$8,'pending_issue',$9,$10,0)""",
                        uid("card", kind + str(index)),
                        tenant,
                        f"SIM-{kind.upper()}-000{index}",
                        kind,
                        user,
                        f"[MÔ PHỎNG] Cư dân {index}",
                        unit,
                        vehicle if kind == "vehicle" else None,
                        today,
                        today + timedelta(days=30),
                    )
                await conn.execute(
                    """insert into visitor_passes(id,tenant_id,code,unit_id,host_user_id,guest_name,guest_count,purpose,visit_from,visit_to,status)
                    values($1,$2,$3,$4,$5,$6,1,'family_visit',$7,$8,'pending_approval')""",
                    uid("visit", str(index)),
                    tenant,
                    f"SIM-VISIT-{index}",
                    unit,
                    user,
                    f"[MÔ PHỎNG] Khách của căn {index}",
                    now + timedelta(hours=2),
                    now + timedelta(hours=4),
                )
                for part, subtotal in (("monthly", 100000 * index), ("adhoc", 50000)):
                    note = uid("debt", part + str(index))
                    vat = subtotal // 10 if part == "monthly" else 0
                    await conn.execute(
                        """insert into debit_notes(id,tenant_id,doc_no,unit_id,period_month,kind,issue_date,due_date,subtotal,vat_amount,total_amount,status,payer_user_id,note)
                        values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'draft',$12,'MÔ PHỎNG: không thu tiền, không hóa đơn thật')""",
                        note,
                        tenant,
                        f"SIM-DEBT-{index}-{part}",
                        unit,
                        today.replace(day=1),
                        part,
                        today,
                        today + timedelta(days=7),
                        subtotal,
                        vat,
                        subtotal + vat,
                        user,
                    )
                    await conn.execute(
                        "insert into debit_note_lines(tenant_id,debit_note_id,line_no,fee_kind,description,quantity,unit_price,vat_rate,amount) values($1,$2,1,'service','MÔ PHỎNG: phí thử nghiệm',1,$3,$4,$3)",
                        tenant,
                        note,
                        subtotal,
                        10 if vat else 0,
                    )
                await conn.execute(
                    """insert into service_requests(id,tenant_id,code,unit_id,requester_user_id,kind,channel,status,details,submitted_at,sla_due_at)
                    values($1,$2,$3,$4,$5,'card_reissue','app','draft','{"simulation":true,"note":"MÔ PHỎNG: yêu cầu cấp lại thẻ"}',$6,$7)""",
                    uid("desk-request", str(index)),
                    tenant,
                    f"SIM-REQUEST-{index}",
                    unit,
                    user,
                    now,
                    now + timedelta(hours=4),
                )
                await conn.execute(
                    """insert into construction_permits(id,tenant_id,code,unit_id,requester_user_id,contractor_name,category,scope_description,planned_start,planned_end,status,submitted_at)
                    values($1,$2,$3,$4,$5,'MÔ PHỎNG: đội thi công','minor_repair','MÔ PHỎNG: sơn sửa nội thất, không tác động kết cấu',$6,$7,'draft',$8)""",
                    uid("permit", str(index)),
                    tenant,
                    f"SIM-PERMIT-{index}",
                    unit,
                    user,
                    today + timedelta(days=2),
                    today + timedelta(days=4),
                    now,
                )
            # Advance through legal state transitions; do not disable database guards.
            await conn.execute(
                "update access_cards set status='active',issued_at=now(),issued_by_staff_id=$1 where status='pending_issue'",
                uid("staff", "sim-security-1"),
            )
            await conn.execute(
                "update visitor_passes set status='approved',qr_token='sim-'||id::text,approved_by_staff_id=$1 where status='pending_approval'",
                uid("staff", "sim-security-1"),
            )
            await conn.execute(
                "update debit_notes set status='issued' where status='draft'"
            )
            await conn.execute(
                "update service_requests set status='submitted' where status='draft'"
            )
            await conn.execute(
                "update construction_permits set status='submitted' where status='draft'"
            )
            for index, category, price in ((1, "community_room", 0), (2, "bbq", 50000)):
                amenity = uid("amenity", str(index))
                await conn.execute(
                    """insert into amenities(id,tenant_id,code,zone_id,name,category,price,open_time,close_time,max_guests,rules_note)
                    values($1,$2,$3,$4,$5,$6,$7,'08:00','21:00',8,'MÔ PHỎNG: lịch/giá/quy định chỉ dùng sandbox')""",
                    amenity,
                    tenant,
                    f"SIM-AMENITY-{index}",
                    zone,
                    f"[MÔ PHỎNG] {category}",
                    category,
                    price,
                )
                # Free bookings only; do not invent a paid transaction/settlement.
                if index == 1:
                    for resident in (1, 2):
                        start = (now + timedelta(days=resident)).replace(
                            hour=3, minute=0, second=0, microsecond=0
                        )
                        await conn.execute(
                            """insert into amenity_bookings(id,tenant_id,code,amenity_id,unit_id,booked_by_user_id,start_at,end_at,guests,status,total_amount)
                            values($1,$2,$3,$4,$5,$6,$7,$8,2,'confirmed',0)""",
                            uid("booking", str(resident)),
                            tenant,
                            f"SIM-BOOKING-{resident}",
                            amenity,
                            uid("unit", f"SIM-UNIT-{resident:03d}"),
                            f"sim-resident-{resident}",
                            start,
                            start + timedelta(hours=1),
                        )
            await conn.execute(
                """insert into construction_policies(tenant_id,zone_id,applies_to_unit_kind,work_time_from,work_time_to,noisy_time_from,noisy_time_to,no_work_weekdays,deposit_amount,max_workers,max_duration_days,effective_from,note)
                values($1,$2,'apartment','08:00','17:00','09:00','16:00',array[7]::smallint[],1000000,4,14,$3,'MÔ PHỎNG: không phải giấy phép/quy định thi công thật')""",
                tenant,
                zone,
                today,
            )
            for category in (
                "security",
                "sanitation",
                "access",
                "visitors",
                "billing",
                "amenities",
                "renovation",
            ):
                identifier = uid("business-service", category)
                policy = {
                    "service_code": "SIM-" + category.upper(),
                    "site_code": "ocean-park-1",
                    "zone_code": "SIM-OP1-ZONE",
                    "building_code": "SIM-OP1-TOWER",
                    "data_mode": "synthetic_test",
                    "eligibility": "Chỉ hai căn sandbox có cư trú hiệu lực",
                    "fee_policy": "quote",
                    "fee_amount": "",
                    "currency": "VND",
                    "fee_unit": "lượt mô phỏng",
                    "vat_policy": "MÔ PHỎNG: báo rõ trước khi cư dân đồng ý; không hóa đơn thật",
                    "operating_hours": "Theo ca sandbox; tiện ích theo giờ trong amenities",
                    "warranty_policy": "Theo phương án được đồng ý; không cam kết bảo hành thật",
                    "booking_policy": "Theo slot/capacity hiện tại; tra cứu không giữ chỗ",
                    "cancellation_policy": "Theo quy định sandbox và trạng thái công việc, không tự thu/hoàn tiền",
                }
                title = "[MÔ PHỎNG] " + category
                encoded = json.dumps(policy, ensure_ascii=False)
                await conn.execute(
                    """insert into owner_data_records(id,tenant_id,site_id,dataset,proposal_code,title,source_hash,proposal,project_approval)
                    values($1,$2,$3,'services',$4,$5,$6,$7::jsonb,'{"data_mode":"synthetic_test","operator_approval":false}')""",
                    identifier,
                    tenant,
                    OP1,
                    policy["service_code"],
                    title,
                    hashlib.sha256(encoded.encode()).hexdigest(),
                    encoded,
                )
                await conn.execute(
                    "insert into domain_service_catalog(id,tenant_id,site_id,title,category_code,policy,operational_enabled) values($1,$2,$3,$4,$5,$6::jsonb,true)",
                    identifier,
                    tenant,
                    OP1,
                    title,
                    category,
                    encoded,
                )
                for audience in ("resident", "staff"):
                    document = uid("business-sop", category + audience)
                    body = (
                        f"MÔ PHỎNG — {category} — {audience}. Chỉ phạm vi SIM-OP1-TOWER. "
                        "Tiếp nhận theo ticket, Platform quản lý session và phân công đúng chuyên môn/ca. "
                        "Staff nhận với ETA hoặc từ chối có lý do, báo tiến độ và bằng chứng cho Platform. "
                        "Phí/phương án cần cư dân đồng ý trước thực thi; kết quả cần cư dân xác nhận hoặc yêu cầu xử lý lại. "
                        "SLA thử nghiệm 30/240 phút, chưa phải SLA thật. Nguy cơ an toàn phải dừng và chuyển người điều phối; không tự xử lý khẩn cấp. "
                        "Thẻ/khách/booking/cải tạo dùng API đúng quyền, không coi tool tra cứu là thao tác đã thực hiện. "
                        "Công nợ chỉ chủ hộ/người thuê được đọc; không tự thanh toán, xóa nợ hoặc phát hành giấy phép."
                    )
                    digest = hashlib.sha256(body.encode()).hexdigest()
                    await conn.execute(
                        """insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience,site_id,zone_id,building_ids,unverified,metadata)
                        values($1,$2,$3,$4,$5,'synthetic-business-sop',$6,$7,$8,$9,true,'{"data_mode":"synthetic_test","operational_verified":false}')""",
                        document,
                        tenant,
                        category + "-" + audience,
                        uid("business-sop-version", digest),
                        title + " SOP " + audience,
                        audience,
                        OP1,
                        zone,
                        [building],
                    )
                    await conn.execute(
                        """insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,heading_path,text_content,text_hash,token_count,search_tsv)
                        values($1,$2,$3,0,$4,$5,$6,$7,to_tsvector('simple',$5))""",
                        uid("business-chunk", category + audience),
                        tenant,
                        document,
                        title,
                        body,
                        digest,
                        len(body.split()),
                    )
            # Preserve explicit source flags for this separately versioned fixture extension.
            metadata.update(
                business_profile=PROFILE,
                business_data_mode="synthetic_test",
                business_created_at=now.isoformat(),
                backup_pairs={
                    f"sim-{team}-1": f"sim-{team}-2"
                    for team in ("security", "sanitation", "desk")
                },
            )
            await conn.execute(
                "update zones set metadata=$2::jsonb where id=$1",
                zone,
                json.dumps(metadata),
            )
        return {
            "profile": PROFILE,
            "idempotent_replay": False,
            "credentials": credentials,
        }
    finally:
        await conn.close()
