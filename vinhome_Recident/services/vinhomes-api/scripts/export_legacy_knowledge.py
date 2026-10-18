"""One-off: read the Ocean Park documents and passages of the old knowledge database into the bundled knowledge file.

    python scripts/export_legacy_knowledge.py --url LEGACY_URL --out src/vinhomes_api/schema/knowledge/ocean-park-1.jsonl.gz

Reads in a read-only transaction; needs VINHOMES_API_EMBEDDING_API_KEY. Kept outside the package: the API never
names the old platform tables (tests/test_schema_contract.py).

The old vectors are not carried over: what was embedded for a passage could not be rebuilt (the passage alone and
the heading with the passage both give a cosine under 0.98 against them), so a passage added later would not be
embedded like the old ones. Every passage is embedded again, the way `knowledge.load` embeds a new one.
"""
import argparse
import asyncio
import base64
import gzip
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import asyncpg
from vinhomes_api.database import _url
from vinhomes_api.knowledge import embed, passage

LEGACY_TENANT = "d360eea1-cd1d-436a-8769-67c7e1598e8b"


async def export_legacy(url: str, out: Path) -> dict:
    connection = await asyncpg.connect(_url(url))
    try:
        async with connection.transaction(readonly=True):
            site = await connection.fetchval("select code from sites where tenant_id=$1", UUID(LEGACY_TENANT))
            documents = await connection.fetch("""
                select d.id,d.active_version_id,d.code,d.title,c.code as category,b.code as base,v.extraction_config
                from knowledge_documents d join knowledge_bases b on b.id=d.knowledge_base_id join knowledge_categories c on c.id=d.category_id
                join document_versions v on v.id=d.active_version_id
                where d.tenant_id=$1 and d.status='published' and b.code in ('ocean-park-1','ocean-park-1-sop') order by d.code
            """, UUID(LEGACY_TENANT))
            scopes: dict = {}
            for row in await connection.fetch("""
                select ds.document_id,s.kind,coalesce(z.code,bz.code) as zone,b.code as building
                from document_scopes ds join access_scopes s on s.id=ds.scope_id left join zones z on z.id=s.zone_id
                left join buildings b on b.id=s.building_id left join zones bz on bz.id=b.zone_id where ds.tenant_id=$1
            """, UUID(LEGACY_TENANT)):
                scopes.setdefault(row["document_id"], []).append(row)
            lines = []
            for document in documents:
                config = json.loads(document["extraction_config"])
                resident = document["base"] == "ocean-park-1" and document["category"] == "resident-care"
                # Staff material was scoped to management units, which the new knowledge tables do not have: it is for the site's staff.
                places = [s for s in scopes.get(document["id"], []) if resident and s["kind"] in ("zone", "building")]
                if resident and not places and not any(s["kind"] == "site" for s in scopes.get(document["id"], [])):
                    raise SystemExit(f"{document['code']} has no place")
                zone = {s["zone"] for s in places}
                if len(zone) > 1 or len({s["kind"] for s in places}) > 1:
                    raise SystemExit(f"{document['code']} is written for several places")
                chunks = await connection.fetch("""
                    select id,ordinal,heading_path,text_content,text_hash,token_count from knowledge_chunks where version_id=$1 order by ordinal
                """, document["active_version_id"])
                lines.append({"id": str(document["id"]), "version_id": str(document["active_version_id"]), "code": document["code"], "title": document["title"],
                              "category": document["category"], "audience": "resident" if resident else "staff", "site": site,
                              "zone": next(iter(zone), None), "buildings": sorted(s["building"] for s in places if s["kind"] == "building"),
                              "unverified": (config.get("metadata") or {}).get("chua_xac_minh") is True,
                              "metadata": {"knowledge_base": document["base"], **{k: config[k] for k in ("metadata", "scopePath", "frontMatter", "sources") if k in config}},
                              "chunks": [{"id": str(c["id"]), "ordinal": c["ordinal"], "heading_path": c["heading_path"], "text": c["text_content"], "text_hash": c["text_hash"],
                                          "token_count": c["token_count"]} for c in chunks]})
    finally:
        await connection.close()
    chunks = [chunk for line in lines for chunk in line["chunks"]]
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start + 64]
        for chunk, vector in zip(batch, await embed([passage(c["heading_path"], c["text"]) for c in batch], 60)):
            chunk["embedding"] = base64.b64encode(vector).decode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed:  # mtime 0: the same data gives the same file
        for line in lines:
            packed.write((json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    return {"documents": len(lines), "chunks": len(chunks)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(" ".join(f"{k}={v}" for k, v in asyncio.run(export_legacy(args.url, args.out)).items()))
