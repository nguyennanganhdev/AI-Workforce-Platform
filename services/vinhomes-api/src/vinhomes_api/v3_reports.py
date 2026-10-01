"""Scoped management incident report data and direct DOCX export."""

from datetime import date
from io import BytesIO
from typing import Annotated
from uuid import UUID
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection


router = APIRouter(tags=["Vinhomes V3 reports"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]


async def _management_building(scope: Scope, building_id: UUID) -> None:
    db, actor_id, _ = scope
    result = await db.execute(text("""
        select 1 from buildings b
        join scoped_user_roles r on r.tenant_id=b.tenant_id and r.role_code='management'
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where b.id=:building_id and b.status='active' and m.user_id=:actor_id
          and m.status='active' and r.valid_from<=now()
          and (r.valid_to is null or r.valid_to>now())
          and b.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
          and (s.kind='tenant'
            or (s.kind='building' and s.building_id=b.id)
            or (s.kind='site' and s.site_id=b.site_id)
            or (s.kind='zone' and s.zone_id=b.zone_id)
            or (s.kind='management' and exists (
                select 1 from management_coverage mc
                join access_scopes cs on cs.id=mc.scope_id and cs.tenant_id=mc.tenant_id
                where mc.management_unit_id=s.management_unit_id
                  and mc.tenant_id=b.tenant_id and mc.valid_from<=now()
                  and (mc.valid_to is null or mc.valid_to>now())
                  and (cs.kind='tenant'
                    or (cs.kind='building' and cs.building_id=b.id)
                    or (cs.kind='site' and cs.site_id=b.site_id)
                    or (cs.kind='zone' and cs.zone_id=b.zone_id)))))
        limit 1
    """), {"building_id": building_id, "actor_id": actor_id})
    if result.first() is None:
        raise HTTPException(403, "Responsible management scope required")


async def _frequency(scope: Scope, building_id: UUID,
                     from_date: date, to_date: date) -> list[dict[str, object]]:
    if from_date >= to_date:
        raise HTTPException(422, "fromDate must be earlier than toDate")
    await _management_building(scope, building_id)
    result = await scope[0].execute(text("""
        select date_trunc('month', t.created_at)::date as month,
               coalesce(it.name, 'Không phân loại') as incident_type,
               count(*) as incident_count
        from tickets t
        left join incident_types it on it.id=t.incident_type_id and it.tenant_id=t.tenant_id
        where t.building_id=:building_id and t.request_kind='incident'
          and t.created_at>=:from_date and t.created_at<:to_date
          and t.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        group by 1, 2 order by 1, 2
    """), {"building_id": building_id, "from_date": from_date,
           "to_date": to_date})
    return [dict(row) for row in result.mappings()]


async def _issued_revenue(scope: Scope, building_id: UUID, category_id: UUID,
                          from_date: date, to_date: date) -> list[dict[str, object]]:
    if from_date >= to_date:
        raise HTTPException(422, "fromDate must be earlier than toDate")
    await _management_building(scope, building_id)
    category = await scope[0].execute(text("""
        select id from service_categories where id=:category_id and enabled
          and tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
    """), {"category_id": category_id})
    if category.first() is None:
        raise HTTPException(404, "Service category not found")
    result = await scope[0].execute(text("""
        select date_trunc('month', i.issued_at)::date as month,
               count(distinct i.id) as invoice_count,
               coalesce(sum(il.net_amount), 0) as net_amount,
               coalesce(sum(il.tax_amount), 0) as tax_amount,
               coalesce(sum(il.total_amount), 0) as billed_amount,
               i.currency
        from invoice_lines il
        join invoices i on i.id=il.invoice_id and i.tenant_id=il.tenant_id
        join tickets t on t.id=i.ticket_id and t.tenant_id=i.tenant_id
        where t.building_id=:building_id and il.category_id=:category_id
          and i.status='issued' and i.issued_at>=:from_date and i.issued_at<:to_date
          and i.tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        group by 1, i.currency order by 1, i.currency
    """), {"building_id": building_id, "category_id": category_id,
           "from_date": from_date, "to_date": to_date})
    return [dict(row) for row in result.mappings()]


def _docx(lines: list[str]) -> bytes:
    paragraphs = "".join(
        '<w:p><w:r><w:t xml:space="preserve">' + escape(line) + '</w:t></w:r></w:p>'
        for line in lines
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + paragraphs + '<w:sectPr/></w:body></w:document>'
    )
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
                         '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                         '</Types>')
        archive.writestr("_rels/.rels",
                         '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                         '</Relationships>')
        archive.writestr("word/document.xml", document)
    return stream.getvalue()


@router.get("/reports/incident-frequency", summary="Incident frequency for a building")
async def incident_frequency(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
) -> dict[str, object]:
    items = await _frequency(scope, building_id, from_date, to_date)
    return {"buildingId": building_id, "fromDate": from_date, "toDate": to_date,
            "items": items}


@router.get("/reports/incident-frequency.docx", summary="Export incident frequency as DOCX")
async def incident_frequency_docx(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
) -> Response:
    items = await _frequency(scope, building_id, from_date, to_date)
    lines = ["Báo cáo tần suất sự cố", f"Tòa: {building_id}",
             f"Từ {from_date} đến trước {to_date}", ""]
    lines.extend(f"{row['month']} | {row['incident_type']} | {row['incident_count']} sự cố"
                 for row in items)
    if not items:
        lines.append("Không có sự cố trong kỳ.")
    return Response(
        content=_docx(lines),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="incident-frequency.docx"',
                 "Cache-Control": "private, no-store"},
    )


@router.get("/reports/issued-revenue", summary="Issued invoice revenue by category")
async def issued_revenue(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    category_id: UUID = Query(..., alias="categoryId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
) -> dict[str, object]:
    items = await _issued_revenue(scope, building_id, category_id, from_date, to_date)
    return {"basis": "issued_invoices", "buildingId": building_id,
            "categoryId": category_id, "fromDate": from_date, "toDate": to_date,
            "items": items}


@router.get("/reports/issued-revenue.docx", summary="Export issued invoice revenue as DOCX")
async def issued_revenue_docx(
    scope: Scope,
    building_id: UUID = Query(..., alias="buildingId"),
    category_id: UUID = Query(..., alias="categoryId"),
    from_date: date = Query(..., alias="fromDate"),
    to_date: date = Query(..., alias="toDate"),
) -> Response:
    items = await _issued_revenue(scope, building_id, category_id, from_date, to_date)
    lines = ["Báo cáo giá trị hóa đơn đã phát hành", f"Tòa: {building_id}",
             f"Loại dịch vụ: {category_id}", f"Từ {from_date} đến trước {to_date}", ""]
    lines.extend(
        f"{row['month']} | {row['invoice_count']} hóa đơn | "
        f"Trước thuế {row['net_amount']} | Thuế {row['tax_amount']} | "
        f"Tổng {row['billed_amount']} {row['currency']}"
        for row in items
    )
    if not items:
        lines.append("Không có hóa đơn đã phát hành trong kỳ.")
    return Response(
        content=_docx(lines),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="issued-revenue.docx"',
                 "Cache-Control": "private, no-store"},
    )
