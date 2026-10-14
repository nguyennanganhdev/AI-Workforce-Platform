"""Minimal production organisation and public project references, with no synthetic people or business history."""
import json
import hashlib
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

import asyncpg

from .database import TENANT, _url

DOMAIN = UUID("22222222-2222-5222-a222-222222222222")
OP1 = UUID("66666666-6666-5666-a666-666666666666")
REFERENCES = Path(__file__).parent / "schema" / "reference" / "ocean-parks.json"


def site_id(code: str) -> UUID:
    return OP1 if code == "ocean-park-1" else uuid5(NAMESPACE_URL, "vinhomes-domain/site/" + code)


async def bootstrap(url: str) -> dict:
    connection = await asyncpg.connect(_url(url))
    try:
        async with connection.transaction():
            tenant = UUID(TENANT)
            await connection.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            await connection.execute("""insert into tenants(id,code,name,status)
                values($1,'vinhomes-domain','Vinhomes Domain','active') on conflict(id) do nothing""", tenant)
            await connection.execute("""insert into domains(id,tenant_id,code,name,status)
                values($1,$2,'vinhomes','Vinhomes','active') on conflict(id) do nothing""", DOMAIN, tenant)
            for code, name, identifier in [
                ("technical", "Kỹ thuật", UUID("33333333-3333-5333-a333-333333333333")),
                ("security", "An ninh", UUID("33333333-3333-5333-a333-333333333334")),
                ("sanitation", "Vệ sinh", uuid5(NAMESPACE_URL, "vinhomes-domain/category/sanitation")),
            ]:
                await connection.execute("""insert into service_categories(id,tenant_id,code,name)
                    select $1,$2,$3,$4 where not exists(select 1 from service_categories where tenant_id=$2 and code=$3)
                    on conflict(id) do nothing""", identifier, tenant, code, name)
            references = json.loads(REFERENCES.read_text(encoding="utf-8"))
            for row in references:
                metadata = {"sources": [row["source_url"]], "checked_at": row["checked_at"],
                            "source_kind": "official_public_reference", "operational_approval": "pending",
                            "note": row["note"]}
                await connection.execute("""insert into sites(id,tenant_id,domain_id,code,name,address,status,metadata)
                    values($1,$2,$3,$4,$5,$6,'active',$7::jsonb) on conflict(id) do nothing""",
                    site_id(row["code"]), tenant, DOMAIN, row["code"], row["name"], row["region"], json.dumps(metadata))
                document = uuid5(NAMESPACE_URL, 'vinhomes-domain/public-reference/' + row['code'])
                body = (f"{row['name']} là dự án tại {row['region']}. "
                        "Đây là thông tin nhận diện dự án từ nguồn công khai của Vinhomes. "
                        "Chưa có danh mục dịch vụ vận hành, phí, giờ phục vụ, đầu mối BQL hoặc phạm vi nhân sự được xác nhận cho khu này. "
                        + row['note'])
                version = uuid5(document, hashlib.sha256(body.encode()).hexdigest())
                await connection.execute("""insert into vh_knowledge_documents
                    (id,tenant_id,code,version_id,title,category,audience,site_id,unverified,metadata)
                    values($1,$2,$3,$4,$5,'project-reference','resident',$6,true,$7::jsonb) on conflict(id) do nothing""",
                    document,tenant,'public/'+row['code'],version,row['name'],site_id(row['code']),json.dumps(metadata))
                await connection.execute("""insert into vh_knowledge_chunks
                    (id,tenant_id,document_id,ordinal,heading_path,text_content,text_hash,token_count,search_tsv)
                    values($1,$2,$3,0,'Thông tin dự án',$4,$5,$6,to_tsvector('simple',$4)) on conflict(id) do nothing""",
                    uuid5(document,'intro'),tenant,document,body,hashlib.sha256(body.encode()).hexdigest(),len(body.split()))
            return {"site_references": len(references), "synthetic_users": 0, "synthetic_transactions": 0}
    finally:
        await connection.close()
