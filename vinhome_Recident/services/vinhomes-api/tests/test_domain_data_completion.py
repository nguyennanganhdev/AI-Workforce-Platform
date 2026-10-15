"""Sourced data can improve reference retrieval without fabricating an operational pilot."""

import asyncio
import gzip
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_owner_data_handoff import script
from test_resident_contract import TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture re-export
)
from vinhomes_api import knowledge
from vinhomes_api.owner_bundle import inspect_bundle

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"
CATALOG = DEPLOY / "reference-data/owner-public-catalog-20261014.json"
TECHNICAL = DEPLOY / "reference-data/op1-technical-public-20261015.json"
SUPPORT = DEPLOY / "reference-data/resident-support-public-20261015.json"


def test_candidate_prefills_geography_and_workflow_but_never_people_or_owner_approval(
    tmp_path,
):
    module = script("prepare-owner-pilot")
    report = module.prepare_candidate(tmp_path, CATALOG)
    assert report["candidate_rows"] == {
        "operators": 0,
        "zones": 1,
        "buildings": 1,
        "units": 0,
        "coverage": 1,
        "residents": 0,
        "staff": 0,
        "shifts": 0,
        "services": 3,
        "sops": 6,
    }
    assert report["personal_records"] == 0 and not report["operational_ready"]
    assert report["source_catalog_sha256"] == hashlib.sha256(
        CATALOG.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    validation, rows, manifest = inspect_bundle(tmp_path)
    assert not validation["valid"]
    assert manifest["pilot"]["building_code"] == "S1.01"
    assert manifest["prefill"]["zone_code_kind"] == "internal_reference"
    assert manifest["data_owner"] == ""
    for source in manifest["source_documents"]:
        evidence = (tmp_path / source["file"]).read_bytes()
        assert b"\r" not in evidence  # Git normalizes JSON to LF; approval hashes must survive checkout.
        assert hashlib.sha256(evidence).hexdigest() == source["sha256"]
    for records in rows.values():
        assert all(
            not r["approved_by"] and not r["approved_at"] and not r["effective_from"]
            for r in records
        )
    assert all(
        not r["fee_policy"] and not r["fee_amount"] and not r["operating_hours"]
        for r in rows["services"]
    )
    assert all(
        not r["response_minutes"]
        and not r["resolution_minutes"]
        and not r["safety_policy"]
        for r in rows["sops"]
    )
    assert "owner_records" in (tmp_path / "missing-data.csv").read_text(
        encoding="utf-8-sig"
    )
    original = (tmp_path / "buildings.csv").read_bytes()
    with pytest.raises(ValueError, match="empty"):
        module.prepare_candidate(tmp_path, CATALOG)
    assert (tmp_path / "buildings.csv").read_bytes() == original


def test_unknown_building_cannot_be_invented_by_the_candidate_generator(tmp_path):
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="building"):
        script("prepare-owner-pilot").prepare_candidate(output, CATALOG, "UNSOURCED")
    assert not output.exists()


@pytest.mark.parametrize(
    "source",
    [
        "https://play.google.com/store/apps/details?id=com.other.resident",
        "https://play.google.com/store/apps/details?id=com.vinhomes.resident&redirect=https://example.invalid",
        "https://vinhomes.vn.example.invalid/data",
        "https://user:password@vinhomes.vn/data",
        "http://vinhomes.vn/data",
    ],
)
def test_reference_compiler_rejects_untrusted_or_credentialled_sources(source):
    assert not script("prepare-reference-pack").official_source(source)


def test_new_technical_data_is_undated_reference_not_a_safety_manual_or_fee_schedule():
    records = json.loads(TECHNICAL.read_text(encoding="utf-8"))
    compiled = script("prepare-reference-pack").compile_records(records)
    assert len(compiled) == 4 and len({d["id"] for d in compiled}) == 4
    assert all(d["site"] == "ocean-park-1" and d["unverified"] for d in compiled)
    for document in compiled:
        assert document["metadata"]["operational_approval"] == "pending"
        assert document["metadata"]["fee_policy"] is None
        assert document["metadata"]["source_published_at"] is None
        assert document["metadata"]["applicability"]
        assert (
            knowledge.provenance(document["metadata"], document["unverified"])["status"]
            == "reference"
        )


def test_import_and_retrieval_are_idempotent_site_scoped_and_do_not_activate_business_data(
    database, monkeypatch, tmp_path
):
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY", raising=False)
    documents = script("prepare-reference-pack").compile_records(
        json.loads(TECHNICAL.read_text(encoding="utf-8"))
    )
    pack = tmp_path / "reference.jsonl.gz"
    pack.write_bytes(
        gzip.compress(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in documents).encode()
        )
    )
    tables = [
        "users",
        "accounts",
        "units",
        "unit_residents",
        "staff_profiles",
        "staff_shifts",
        "tickets",
        "domain_service_catalog",
        "owner_operational_batches",
    ]
    before = {t: sql(database, "select count(*) n from " + t)[0]["n"] for t in tables}
    op1 = sql(
        database,
        "select id from sites where tenant_id=$1 and code='ocean-park-1'",
        TENANT,
    )[0]["id"]
    op2 = uuid4()
    domain = sql(database, "select domain_id from sites where id=$1", op1)[0][
        "domain_id"
    ]
    sql(
        database,
        "insert into sites(id,tenant_id,domain_id,code,name,address,status) values($1,$2,$3,'isolated-op2-test','Isolated scope','Test database only','active')",
        op2,
        TENANT,
        domain,
    )

    async def check():
        first = await knowledge.load(database["admin"], pack, str(TENANT))
        second = await knowledge.load(database["admin"], pack, str(TENANT))
        assert first["documents"] == 4 and first["embedded"] == 0
        assert second["changed"] == 0
        engine = create_async_engine(
            database["runtime"].replace("postgresql:", "postgresql+asyncpg:", 1)
        )
        try:
            async with engine.begin() as db:
                await db.execute(
                    text("select set_config('app.tenant_id',:tenant,true)"),
                    {"tenant": str(TENANT)},
                )
                query = "Sapphire cơ bản bếp bình nước nóng intercom"
                found = await knowledge.search(
                    db, TENANT, "resident", None, None, query, 5, site_id=op1
                )
                assert any(h["documentId"] == documents[0]["id"] for h in found["hits"])
                assert all(
                    h["provenance"]["status"] == "reference"
                    for h in found["hits"]
                    if h["documentId"] in {d["id"] for d in documents}
                )
                other = await knowledge.search(
                    db, TENANT, "resident", None, None, query, 5, site_id=op2
                )
                assert other["hits"] == []
        finally:
            await engine.dispose()

    asyncio.run(check())
    assert {
        t: sql(database, "select count(*) n from " + t)[0]["n"] for t in tables
    } == before

def test_support_references_have_distinct_scopes_and_no_operational_approval():
    compiler = script("prepare-reference-pack")
    records = json.loads(SUPPORT.read_text(encoding="utf-8"))
    documents = compiler.compile_records(records)
    assert len(documents) == 6
    assert {
        site: sum(d["site"] == site for d in documents)
        for site in ("ocean-park-1", "ocean-park-2", "ocean-park-3")
    } == {"ocean-park-1": 2, "ocean-park-2": 2, "ocean-park-3": 2}
    old_ids = {
        d["id"]
        for d in compiler.compile_records(
            json.loads(CATALOG.read_text(encoding="utf-8"))
            + json.loads(TECHNICAL.read_text(encoding="utf-8"))
        )
    }
    assert len({d["id"] for d in documents}) == 6
    assert not old_ids.intersection(d["id"] for d in documents)
    for document in documents:
        metadata = document["metadata"]
        assert metadata["operational_approval"] == "pending"
        assert metadata["operator"] is None and metadata["fee_policy"] is None
        assert metadata["operating_hours"] is None
        assert metadata["source_published_at"] is None
        assert len(metadata["source_snapshot_sha256"]) == 64
        assert metadata["applicability"]
        assert document["unverified"]
    assert all("care-workflow" not in d["code"] for d in documents)


def test_support_import_and_retrieval_preserve_site_boundaries_and_business_data(
    database, monkeypatch, tmp_path
):
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY", raising=False)
    domain = sql(
        database, "select domain_id from sites where tenant_id=$1 limit 1", TENANT
    )[0]["domain_id"]
    sites = {}
    for code in ["ocean-park-1", "ocean-park-2", "ocean-park-3"]:
        rows = sql(
            database,
            "select id from sites where tenant_id=$1 and code=$2",
            TENANT,
            code,
        )
        sites[code] = rows[0]["id"] if rows else uuid4()
        if not rows:
            sql(
                database,
                "insert into sites(id,tenant_id,domain_id,code,name,address,status) values($1,$2,$3,$4,'Test scope','Test database only','active')",
                sites[code],
                TENANT,
                domain,
                code,
            )
    tables = [
        "users",
        "accounts",
        "units",
        "unit_residents",
        "staff_profiles",
        "staff_shifts",
        "domain_service_catalog",
        "management_coverage",
        "tickets",
        "work_orders",
        "owner_operational_batches",
    ]
    before = {t: sql(database, "select count(*) n from " + t)[0]["n"] for t in tables}
    documents = script("prepare-reference-pack").compile_records(
        json.loads(SUPPORT.read_text(encoding="utf-8"))
    )
    pack = tmp_path / "support.jsonl.gz"
    pack.write_bytes(
        gzip.compress(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in documents).encode()
        )
    )
    queries = [
        (
            "ocean-park-1",
            "hotline liên hệ Ocean Park 1",
            "resident/public-project-contact",
        ),
        (
            "ocean-park-1",
            "sửa điện nước điều hòa M&E",
            "technical/me-capability-reference",
        ),
        (
            "ocean-park-2",
            "hotline The Empire liên hệ",
            "resident/public-project-contact",
        ),
        (
            "ocean-park-2",
            "Empire Park Khải Hoàn Silk Park",
            "amenity/parks-activity-reference",
        ),
        (
            "ocean-park-3",
            "hồ bơi trong nhà Four Seasons",
            "amenity/aquatic-activity-reference",
        ),
        (
            "ocean-park-3",
            "Aquarium trẻ em BBQ Garden",
            "amenity/family-activity-reference",
        ),
    ]

    async def check():
        first = await knowledge.load(database["admin"], pack, str(TENANT))
        second = await knowledge.load(database["admin"], pack, str(TENANT))
        assert first["documents"] == 6 and first["embedded"] == 0
        assert second["changed"] == 0
        engine = create_async_engine(
            database["runtime"].replace("postgresql:", "postgresql+asyncpg:", 1)
        )
        try:
            async with engine.begin() as db:
                await db.execute(
                    text("select set_config('app.tenant_id',:tenant,true)"),
                    {"tenant": str(TENANT)},
                )
                for code, query, suffix in queries:
                    expected = next(
                        d["id"]
                        for d in documents
                        if d["site"] == code and d["code"].endswith(suffix)
                    )
                    for target, site_id in sites.items():
                        found = await knowledge.search(
                            db,
                            TENANT,
                            "resident",
                            None,
                            None,
                            query,
                            20,
                            site_id=site_id,
                        )
                        ids = {h["documentId"] for h in found["hits"]}
                        if target == code:
                            assert expected in ids, (code, query)
                        else:
                            assert expected not in ids
                        assert not ids.intersection(
                            d["id"] for d in documents if d["site"] != target
                        )
                        assert all(
                            h["provenance"]["status"] == "reference"
                            for h in found["hits"]
                        )
        finally:
            await engine.dispose()

    asyncio.run(check())
    assert {
        t: sql(database, "select count(*) n from " + t)[0]["n"] for t in tables
    } == before
