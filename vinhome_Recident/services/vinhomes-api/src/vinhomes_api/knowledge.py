"""Knowledge the assistants answer from: load it, search it.

    python -m vinhomes_api.knowledge load [--file F] [--tenant T]     (reads DATABASE_URL, the owner's)

A knowledge file is gzip JSON lines, one document per line with its passages (docs/domain/NAP_DU_LIEU.md).
`load` is safe to repeat: rows are matched by id and a row that did not change is not written.
Search returns passages, never an answer: the assistant writes the answer from them and cites them.
"""

import argparse
import asyncio
import base64
import gzip
import hashlib
import json
import os
import re
import sys
import unicodedata
from array import array
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import asyncpg
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from .database import SCHEMA, TENANT, _url
from .reception_delegation import DelegatedScope

BUNDLED = SCHEMA / "knowledge" / "ocean-park-1.jsonl.gz"
MODEL, DIMENSIONS = "text-embedding-3-large", 1536
# Chosen from 21 real questions against the Ocean Park documents, asked as a resident of Sapphire S1.01.
# Meaning leads and the words adjust: with more weight on the words, a question typed with diacritics ranked worse.
VECTOR_WEIGHT, TEXT_WEIGHT = 0.8, 0.2
# Below these nothing is returned. Blended score: the best passage of an off-topic question ("giá vàng hôm nay",
# "bạn là ai", "thời tiết") reached 0.33 and the weakest useful one 0.39. Words alone: 0.33 against 0.45.
# A passage that passes on its words alone is kept even when the blend is low: a question typed without diacritics
# ("be boi mo cua may gio") embeds poorly. Only from WORDS_ALONE words on: the two words of "giá vàng" all occur
# somewhere, and the share of the question found says nothing then.
BLEND_FLOOR, TEXT_FLOOR, WORDS_ALONE = 0.36, 0.40, 4
# Remove conversational filler only from lexical scoring; keep the original question for embeddings.
QUERY_FILLER = set('cac ben trong la gi cho toi minh ban xin hoi biet ve nhung nhe the nao giup ai muon'.split())

router = APIRouter(tags=["Knowledge"])


def fold(value: str) -> str:
    """Lower case without Vietnamese diacritics: residents type both ways."""
    return "".join(c for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d")) if not unicodedata.combining(c))


def words(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFC", value).lower())


def provenance(metadata: dict, unverified: bool) -> dict:
    """Review evidence is owner-managed metadata, not a model claim or the legacy unverified flag alone."""
    review=metadata.get('review') or {}
    review=review if isinstance(review,dict) else {}
    sources=metadata.get('sources') or []
    sources=[s.strip() for s in sources if isinstance(s,str) and s.strip()] if isinstance(sources,list) else []
    today=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    def day(value):
        try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).date()
        except (ValueError,TypeError):return None
    reviewed=day(review.get('approved_at'));effective=day(review.get('effective_from'))
    until=day(review.get('effective_until'));issues=[]
    if unverified:issues.append('unverified')
    if not review.get('approved_by') or not reviewed or reviewed>today:issues.append('not_reviewed')
    if not sources:issues.append('missing_source')
    if not review.get('document_reference'):issues.append('missing_document_reference')
    if not effective:issues.append('missing_effective_date')
    elif effective>today:issues.append('not_effective_yet')
    if review.get('effective_until') and (not until or until<today):issues.append('expired_or_invalid')
    return {'status':'reference' if issues else 'approved','issues':issues,'sources':sources,
            'document_reference':review.get('document_reference'),'effective_from':review.get('effective_from'),
            'effective_until':review.get('effective_until'),'reviewed_by':review.get('approved_by'),
            'reviewed_at':review.get('approved_at')}


def passage(heading: str | None, body: str) -> str:
    """What is embedded for a passage: its heading says what the lines below are about."""
    return "\n\n".join(filter(None, (heading, body)))


def literal(raw: bytes) -> str:
    """A vector as PostgreSQL reads it: '[0.1,0.2,…]', cast to `vector` in the statement."""
    return "[" + ",".join(map(repr, array("f", raw))) + "]"


async def embed(texts: list[str], timeout: float) -> list[bytes]:
    """One little-endian float32 vector per text, as the provider's base64 answer holds it."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post("https://api.openai.com/v1/embeddings", headers={"Authorization": "Bearer " + os.environ["VINHOMES_API_EMBEDDING_API_KEY"].strip()},
                                     json={"model": MODEL, "dimensions": DIMENSIONS, "input": texts, "encoding_format": "base64"})
    response.raise_for_status()
    vectors = [base64.b64decode(row["embedding"]) for row in sorted(response.json()["data"], key=lambda row: row["index"])]
    if len(vectors) != len(texts) or any(len(v) != DIMENSIONS * 4 for v in vectors):
        raise ValueError("The embedding provider answered with another shape")
    return vectors


async def search(db, tenant, audience: str, zone_id, building_id, query: str, top_k: int, *, site_id=None) -> dict:
    """The passages of the tenant written for this audience and this place that best match the question.

    Place: documents of the whole site always, plus those of `zone_id`, plus those of `building_id` in it.
    The tenant, the place and the audience are applied first, then every passage left is scored and ranked, all in
    one statement. Every one of them, not the neighbours the HNSW index would propose: the score blends the words
    with the meaning, so the best passage need not be among the nearest, and an index scan filtered afterwards can
    come back short. `db` is a SQLAlchemy connection.
    """
    result = {"retrievalRunId": str(uuid4()), "insufficientSources": True, "hits": []}
    # Some keyboards send a letter and its marks apart; the passages were embedded with them joined.
    query = unicodedata.normalize("NFC", query)
    typed = [word for word in words(query) if fold(word) not in QUERY_FILLER]
    plain = [fold(word) for word in typed]
    if not typed:
        return result
    # Single words as typed and without diacritics, and pairs of neighbours: a Vietnamese word is mostly two syllables.
    terms = list(dict.fromkeys(typed + plain + [a + " <-> " + b for a, b in zip(plain, plain[1:])]))
    vector = None
    if os.getenv("VINHOMES_API_EMBEDDING_API_KEY", "").strip():
        try:
            vector = literal((await embed([query], 4))[0])
        except Exception:
            vector = None  # the provider is down or slow: the words alone still answer
    # text_score: the share of the question found in the passage, a rare term counting more than a common one.
    # ts_rank was tried first: over syllables every passage matches something and "bạn là ai" outranks a real question.
    # Meaning: 1 - cosine distance; no number when the question or the passage has no vector, and the words answer.
    rows = (await db.execute(text("""
        with scope as materialized (
            select k.id,k.document_id,d.version_id,d.title,k.heading_path,k.text_content,d.unverified,d.metadata,k.search_tsv,
                   1-(k.embedding <=> cast(cast(:vector as text) as vector)) as meaning
            from vh_knowledge_chunks k join vh_knowledge_documents d on d.id=k.document_id and d.tenant_id=k.tenant_id
            where k.tenant_id=:tenant and d.audience=:audience
              and d.site_id=coalesce(cast(:site as uuid),
                    (select site_id from zones where tenant_id=:tenant and id=cast(:zone as uuid)),
                    (select site_id from buildings where tenant_id=:tenant and id=cast(:building as uuid)),
                    (select (array_agg(id))[1] from sites where tenant_id=:tenant having count(*)=1))
              and coalesce(d.metadata->>'retrieval_status','reference') <> 'quarantined'
              and (d.zone_id is null or (d.zone_id=cast(:zone as uuid)
                   and (d.building_ids is null or cast(:building as uuid)=any(d.building_ids))))),
        terms as (select term from unnest(cast(:terms as text[])) term),
        matches as (select s.id,t.term from scope s join terms t on s.search_tsv @@ to_tsquery('simple',t.term)),
        weights as (select t.term,ln(1+(select count(*) from scope)::float8/greatest(count(m.id),1)) as weight
                    from terms t left join matches m on m.term=t.term group by t.term),
        scored as (select s.*,coalesce((select sum(w.weight) from matches m join weights w on w.term=m.term where m.id=s.id),0)
                              /(select sum(weight) from weights) as text_score from scope s)
        select id,document_id,version_id,title,heading_path,text_content,unverified,metadata,
               coalesce(:vector_weight*meaning+:text_weight*text_score,text_score) as score
        from scored
        where :vector_weight*meaning+:text_weight*text_score>=:blend_floor or (text_score>=:text_floor and (meaning is null or :many_words))
        order by score desc,id limit :top
    """), {"tenant": tenant, "audience": audience, "site": site_id, "zone": zone_id, "building": building_id, "terms": terms, "vector": vector,
           "vector_weight": VECTOR_WEIGHT, "text_weight": TEXT_WEIGHT, "blend_floor": BLEND_FLOOR, "text_floor": TEXT_FLOOR,
           "many_words": len(set(plain)) >= WORDS_ALONE, "top": top_k})).mappings().all()
    result["hits"] = [{"rank": rank, "chunkId": str(row["id"]), "documentId": str(row["document_id"]), "versionId": str(row["version_id"]),
                       "title": row["title"], "section": row["heading_path"], "text": row["text_content"],
                       "unverified": row["unverified"], "score": round(float(row["score"]), 4),
                       "provenance": provenance(row['metadata'],row['unverified'])}
                      for rank, row in enumerate(rows, 1)]
    result["insufficientSources"] = not result["hits"]
    return result


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    topK: int = Field(default=5, ge=1, le=20)


@router.post("/internal/knowledge/search")
async def search_for_resident(body: SearchBody, scope: DelegatedScope):
    """What Reception may quote to the resident of this turn: resident documents of the place they live in."""
    db, run = scope
    homes = {(row["site_id"], row["zone_id"], row["building_id"]) for row in (await db.execute(text("""
        select u.site_id,u.zone_id,u.building_id from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        where ur.tenant_id=:tenant and ur.user_id=:user and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
    """), {"tenant": run["tenant_id"], "user": run["user_id"]})).mappings()}
    if len({(site,zone) for site, zone, _ in homes}) > 1:
        # Homes in several zones: the request filed from this conversation says which one is meant. Until there
        # is one, only what holds for the whole site is safe to quote.
        filed = (await db.execute(text("""
            select site_id,zone_id,building_id from tickets where tenant_id=:tenant and channel_id=:channel and unit_id is not null
            order by created_at desc limit 1
        """), {"tenant": run["tenant_id"], "channel": run["channel_id"]})).first()
        sites = {home[0] for home in homes}
        common_site = next(iter(sites)) if len(sites)==1 else None
        homes = {tuple(filed)} if filed is not None and tuple(filed) in homes else {(common_site, None, None)}
    site = next(iter(homes))[0] if homes else None
    zone = next(iter(homes))[1] if homes else None
    # Several buildings of one zone: only what holds for the whole zone is safe to quote.
    building = next(iter(homes))[2] if len(homes) == 1 else None
    return await search(db, run["tenant_id"], "resident", zone, building, body.query, body.topK, site_id=site)


def read(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


async def load(url: str, path: Path, tenant: str) -> dict:
    """Write the file's documents and passages into the tenant. Returns the counts and the documents left out."""
    documents = read(path)
    counts = {"documents": 0, "chunks": 0, "embedded": 0, "skipped": 0, "changed": 0}
    problems: list[str] = []
    connection = await asyncpg.connect(_url(url))
    try:
        async with connection.transaction():
            await connection.execute("select set_config('app.tenant_id',$1,true)", tenant)
            sites = {row["code"]:row["id"] for row in await connection.fetch("select code,id from sites where tenant_id=$1", UUID(tenant))}
            zones = {row["code"]: row["id"] for row in await connection.fetch("select code,id from zones where tenant_id=$1", UUID(tenant))}
            buildings = {row["code"]: row for row in await connection.fetch("select code,id,zone_id from buildings where tenant_id=$1", UUID(tenant))}
            loaded = []
            for document in documents:
                zone, towers = document.get("zone"), document.get("buildings") or []
                # A place this database does not have: leave the document out. Loading it for the whole site would show it to everyone.
                missing = ([] if document["site"] in sites else [f"site {document['site']}"]) + ([f"zone {zone}"] if zone and zone not in zones else []) \
                    + [f"building {code}" for code in towers if code not in buildings or buildings[code]["zone_id"] != zones.get(zone)]
                if missing:
                    problems.append(f"{document['code']}: no {', '.join(missing)}")
                    continue
                chunks = document["chunks"]
                # Ids are one space for the whole database and this role is not held to its tenant: the same file
                # loaded for a second tenant would rewrite the first one's rows.
                if await connection.fetchval("""select exists(select 1 from vh_knowledge_documents where id=$1 and tenant_id<>$3)
                        or exists(select 1 from vh_knowledge_chunks where id=any($2::uuid[]) and tenant_id<>$3)""",
                                             UUID(document["id"]), [UUID(c["id"]) for c in chunks], UUID(tenant)):
                    raise SystemExit(f"{document['code']}: its ids already belong to another tenant's knowledge. Nothing was loaded; give this tenant's copy its own ids.")
                loaded.append(UUID(document["id"]))
                counts["changed"] += len(await connection.fetch("""
                    insert into vh_knowledge_documents as d(id,tenant_id,code,version_id,title,category,audience,zone_id,building_ids,unverified,metadata,site_id)
                    values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
                    on conflict (id) do update set code=excluded.code,version_id=excluded.version_id,title=excluded.title,category=excluded.category,
                        audience=excluded.audience,zone_id=excluded.zone_id,building_ids=excluded.building_ids,unverified=excluded.unverified,metadata=excluded.metadata,site_id=excluded.site_id
                    where d.tenant_id=excluded.tenant_id and (d.code,d.version_id,d.title,d.category,d.audience,d.zone_id,d.building_ids,d.unverified,d.metadata,d.site_id)
                        is distinct from (excluded.code,excluded.version_id,excluded.title,excluded.category,excluded.audience,excluded.zone_id,excluded.building_ids,excluded.unverified,excluded.metadata,excluded.site_id)
                    returning id
                """, UUID(document["id"]), UUID(tenant), document["code"], UUID(document["version_id"]), document["title"], document["category"], document["audience"],
                    zones[zone] if zone else None, [buildings[code]["id"] for code in towers] or None, bool(document.get("unverified")),
                    json.dumps(document.get("metadata") or {}, ensure_ascii=False), sites[document["site"]]))
                await connection.execute("delete from vh_knowledge_chunks where tenant_id=$3 and document_id=$1 and id<>all($2::uuid[])",
                                         UUID(document["id"]), [UUID(c["id"]) for c in chunks], UUID(tenant))
                for chunk in chunks:
                    body, heading = chunk["text"], chunk.get("heading_path")
                    # The words as written and without diacritics, so "bể bơi" and "be boi" both find the passage.
                    indexed = " ".join(words(" ".join(filter(None, (document["title"], heading, body)))))
                    counts["changed"] += len(await connection.fetch("""
                        insert into vh_knowledge_chunks as k(id,tenant_id,document_id,ordinal,heading_path,text_content,text_hash,token_count,search_tsv,embedding)
                        values($1,$2,$3,$4,$5,$6,$7,$8,to_tsvector('simple',$9),$10::text::vector)
                        on conflict (id) do update set document_id=excluded.document_id,ordinal=excluded.ordinal,heading_path=excluded.heading_path,
                            text_content=excluded.text_content,text_hash=excluded.text_hash,token_count=excluded.token_count,search_tsv=excluded.search_tsv,
                            embedding=case when excluded.embedding is not null then excluded.embedding
                                when (k.heading_path,k.text_hash) is not distinct from (excluded.heading_path,excluded.text_hash) then k.embedding end
                        where k.tenant_id=excluded.tenant_id and ((k.document_id,k.ordinal,k.heading_path,k.text_content,k.token_count,k.search_tsv)
                            is distinct from (excluded.document_id,excluded.ordinal,excluded.heading_path,excluded.text_content,excluded.token_count,excluded.search_tsv)
                            or (excluded.embedding is not null and k.embedding is distinct from excluded.embedding))
                        returning id
                    """, UUID(chunk["id"]), UUID(tenant), UUID(document["id"]), chunk["ordinal"], heading, body, hashlib.sha256(body.encode()).hexdigest(),
                        chunk["token_count"], indexed + " " + fold(indexed), literal(base64.b64decode(chunk["embedding"])) if chunk.get("embedding") else None))
                counts["documents"] += 1
                counts["chunks"] += len(chunks)
            counts["skipped"] = len(problems)
            if os.getenv("VINHOMES_API_EMBEDDING_API_KEY", "").strip():
                bare = await connection.fetch("select id,heading_path,text_content from vh_knowledge_chunks where document_id=any($1::uuid[]) and embedding is null order by id", loaded)
                for start in range(0, len(bare), 64):
                    batch = bare[start:start + 64]
                    vectors = await embed([passage(row["heading_path"], row["text_content"]) for row in batch], 60)
                    await connection.executemany("update vh_knowledge_chunks set embedding=$2::text::vector where id=$1", [(row["id"], literal(vector)) for row, vector in zip(batch, vectors)])
                    counts["embedded"] += len(batch)
    finally:
        await connection.close()
    return {**counts, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vinhomes_api.knowledge", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    from_env = os.environ.get("DATABASE_URL")
    loader = commands.add_parser("load")
    loader.add_argument("--url", default=from_env, required=from_env is None)
    loader.add_argument("--file", type=Path, default=BUNDLED)
    loader.add_argument("--tenant", default=TENANT)
    args = parser.parse_args(argv)
    done = asyncio.run(load(args.url, args.file, args.tenant))
    for line in done.pop("problems"):
        print("SKIPPED " + line)
    print(" ".join(f"{k}={v}" for k, v in done.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
