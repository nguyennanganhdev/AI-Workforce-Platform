"""Explicitly provision the isolated travel mock catalog, route and labelled Reception reference documents."""

import argparse
import asyncio
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from .bootstrap import site_id
from .database import TENANT, _url
from .knowledge import fold, words
from .mock_travel import data

CATEGORY = uuid5(NAMESPACE_URL, "vinhomes-domain/category/travel-mock")
MANAGEMENT = uuid5(NAMESPACE_URL, "vinhomes-domain/provider/travel-mock")
SOURCE_CATALOG = deepcopy(
    [
        ("hotel", "hotel_id", data.HOTELS),
        ("bus", "trip_id", data.BUS_TRIPS),
        ("restaurant", "restaurant_id", data.RESTAURANTS),
    ]
)


async def load(url, enable_mock=False):
    if not enable_mock:
        raise ValueError("Explicit mock enablement required")
    tenant = UUID(TENANT)
    provenance = json.loads(
        (Path(__file__).parent / "mock_travel/PROVENANCE.json").read_text(
            encoding="utf-8"
        )
    )
    source_hash = provenance["archive_sha256"]
    catalog = SOURCE_CATALOG
    conn = await asyncpg.connect(_url(url))
    try:
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            await conn.execute(
                """insert into service_categories(id,tenant_id,code,name,enabled)
                values($1,$2,'travel','Du lịch/đặt chỗ (mô phỏng)',true) on conflict(id) do nothing""",
                CATEGORY,
                tenant,
            )
            await conn.execute(
                """insert into management_units(id,tenant_id,code,name,status,metadata)
                values($1,$2,'travel-mock','Nhà cung cấp Travel MÔ PHỎNG','active',$3::jsonb) on conflict(id) do nothing""",
                MANAGEMENT,
                tenant,
                json.dumps(
                    {
                        "provider_mode": "mock",
                        "is_real_operator": False,
                        "source_hash": source_hash,
                    }
                ),
            )
            for kind, identifier, entries in catalog:
                for row in entries:
                    await conn.execute(
                        """insert into travel_mock_catalog(tenant_id,kind,service_id,data,source_hash)
                        values($1,$2,$3,$4::jsonb,$5) on conflict(tenant_id,kind,service_id) do update
                        set data=excluded.data,source_hash=excluded.source_hash""",
                        tenant,
                        kind,
                        row[identifier],
                        json.dumps(row, ensure_ascii=False),
                        source_hash,
                    )
            metadata = json.dumps(
                {
                    "sources": [
                        "attachment:mock_travel_booking_mcp.zip#" + source_hash
                    ],
                    "source_kind": "user_supplied_mock_travel",
                    "data_mode": "mock",
                    "operational_approval": "not_a_real_service",
                },
                ensure_ascii=False,
            )
            document_count = 0
            for site in ("ocean-park-1", "ocean-park-2", "ocean-park-3"):
                scope = uuid5(MANAGEMENT, site)
                await conn.execute(
                    """insert into access_scopes(id,tenant_id,kind,site_id)
                    values($1,$2,'site',$3) on conflict do nothing""",
                    scope,
                    tenant,
                    site_id(site),
                )
                scope = await conn.fetchval(
                    "select id from access_scopes where tenant_id=$1 and kind='site' and site_id=$2",
                    tenant,
                    site_id(site),
                )
                await conn.execute(
                    """insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from)
                    values($1,$2,$3,$4,$5,now()) on conflict(id) do nothing""",
                    uuid5(scope, "travel-route"),
                    tenant,
                    MANAGEMENT,
                    scope,
                    CATEGORY,
                )
                docs = [
                    (
                        "overview",
                        "Travel: khách sạn, chuyến xe, nhà hàng — MÔ PHỎNG",
                        (
                            "Hệ thống hỗ trợ thử luồng du lịch: tìm khách sạn, chuyến xe và nhà hàng; kiểm tra chỗ, xem giá mô phỏng, "
                            "đề nghị đặt hoặc hủy. Reception tiếp nhận nhu cầu nguyên văn thành yêu cầu travel, Platform xử lý và gửi phương án để cư dân tự đồng ý. "
                            "Chưa có API nhà cung cấp thật. Tên, địa chỉ, phí, giờ, tồn chỗ và quy định dưới đây là dữ liệu mô phỏng, "
                            "không phải dịch vụ chính thức hoặc quyền cư dân Vinhomes. Không đặt chỗ, thanh toán, gửi email/SMS hoặc hoàn tiền thật."
                        ),
                    )
                ]
                for kind, identifier, entries in catalog:
                    for row in entries:
                        label = row.get("name") or (
                            row.get("origin", "") + " → " + row.get("destination", "")
                        )
                        docs.append(
                            (
                                kind + "/" + row[identifier],
                                "Travel MÔ PHỎNG: " + label,
                                "DỮ LIỆU MÔ PHỎNG để thử hệ thống; không phải giá/lịch/dịch vụ thật hoặc đối tác đã xác nhận của Vinhomes. "
                                + json.dumps(row, ensure_ascii=False),
                            )
                        )
                for code, title, body in docs:
                    document = uuid5(
                        NAMESPACE_URL, "vinhomes-travel-mock/" + site + "/" + code
                    )
                    version = uuid5(document, hashlib.sha256(body.encode()).hexdigest())
                    await conn.execute(
                        """insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience,site_id,unverified,metadata)
                        values($1,$2,$3,$4,$5,'travel-mock','resident',$6,true,$7::jsonb) on conflict(id) do update
                        set version_id=excluded.version_id,title=excluded.title,unverified=true,metadata=excluded.metadata""",
                        document,
                        tenant,
                        "mock-travel/" + site + "/" + code,
                        version,
                        title,
                        site_id(site),
                        metadata,
                    )
                    indexed = " ".join(words(title + " " + body))
                    await conn.execute(
                        """insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,heading_path,text_content,text_hash,token_count,search_tsv)
                        values($1,$2,$3,0,$4,$5,$6,$7,to_tsvector('simple',$8)) on conflict(id) do update
                        set heading_path=excluded.heading_path,text_content=excluded.text_content,text_hash=excluded.text_hash,
                        token_count=excluded.token_count,search_tsv=excluded.search_tsv,
                        embedding=case when vh_knowledge_chunks.text_hash=excluded.text_hash then vh_knowledge_chunks.embedding end""",
                        uuid5(document, "body"),
                        tenant,
                        document,
                        title,
                        body,
                        hashlib.sha256(body.encode()).hexdigest(),
                        len(body.split()),
                        indexed + " " + fold(indexed),
                    )
                    document_count += 1
        return {
            "provider_mode": "mock",
            "catalog": {kind: len(entries) for kind, _, entries in catalog},
            "knowledge_documents": document_count,
            "mock_routes": 3,
            "users_created": 0,
            "real_bookings": 0,
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-mock", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(load(os.environ["DATABASE_URL"], args.enable_mock))))
