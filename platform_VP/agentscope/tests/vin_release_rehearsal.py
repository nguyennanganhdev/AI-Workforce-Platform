"""Disposable C10 four-store rehearsal; no restored application/model is started.

Host: python tests/vin_release_rehearsal.py --output .artifacts/n1-c10
Requires local QA/infra images plus docker:27-cli. Only generated fixture names
and volumes are mutated. Deploy scripts are copied unchanged (LF normalized).
"""

import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

QA_IMAGE = "agentscope-op2-offline-qa:20261017"
INFRA = {"postgres": "pgvector/pgvector:pg17", "redis": "redis:7-alpine",
    "minio": "cgr.dev/chainguard/minio:latest"}
TABLES = ["auth_users", "vin_accounts", "vin_quota_policies", "vin_catalog", "vin_grants",
    "vin_attempts", "vin_subject_usage", "vin_usage_buckets", "vin_secrets", "vin_domain_links", "vin_cases", "vin_audit", "wf_durable_jobs"]
OBJECTS = {"private/fixture-customer/request.txt": "fixture-private-request-v1", "library/policy.txt": "fixture-vin-policy-v2"}
FIXTURE_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"f" * 32).decode()
REPO = Path(__file__).resolve().parents[3]
SERVICE = REPO / "platform_VP" / "agentscope"


def call(*args, data=None, check=True):
    result = subprocess.run(args, input=data, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"Fixture command failed ({args[0:3]}): " + result.stderr.decode(errors="replace")[-4000:])
    return result.stdout.decode().strip() if check else result


def docker(*args, **kwargs):
    return call("docker", *args, **kwargs)


async def seed_sql():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import insert, text
    from sqlalchemy.ext.asyncio import create_async_engine
    from agentscope.app.vin_platform import VinPlatformService, QuotaPolicy
    from agentscope.app.vin_platform import _tables as t
    from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
    url = "postgresql+asyncpg://vinfixture:offline-vin-fixture-only@127.0.0.1:5432/vinfixture"
    config = Config(str(SERVICE / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    await asyncio.to_thread(command.upgrade, config, "head")
    engine = create_async_engine(url)
    authority = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(), encryption_key=FIXTURE_ENCRYPTION_KEY)
    try:
        async with engine.begin() as db:
            for user, role in (("fixture-admin", "PLATFORM_ADMIN"), ("fixture-customer", "VIN_USER")):
                await db.execute(text("""INSERT INTO auth_users(id,tenant_id,email,username,password_hash,status,role,created_at,updated_at)
                    VALUES(:u,'fixture',:email,:u,'not-a-login-hash','active',:r,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                    {"u": user, "r": role, "email": user + "@fixture.invalid"})
                await db.execute(insert(t.accounts).values(user_id=user, tenant_id="fixture", eligible=True, revision=1))
        admin, customer = await authority.context("fixture-admin"), await authority.context("fixture-customer")
        secret = await authority.secret_put(admin, "offline-link-material-for-restore", "domain-link")
        async with engine.begin() as db:
            await db.execute(insert(t.links).values(id="fixture-link", tenant_id="fixture", user_id="fixture-customer",
                provider_id="fixture-domain", issuer="https://domain.invalid", subject="fixture-resident",
                status="active", secret_ref=secret, scopes=["self", "requests"], revision=1, data={}))
            await db.execute(insert(t.cases).values(id="fixture-case", tenant_id="fixture", user_id="fixture-customer",
                link_id="fixture-link", idempotency_key="fixture-case-create-key", payload_hash="a" * 64,
                state="applied", data={"domain": {"id": "00000000-0000-4000-8000-000000000001"}}, revision=2))
        await authority.set_policy(admin, "role:VIN_USER", QuotaPolicy(daily_tokens=10000, monthly_tokens=100000,
            max_concurrency=2, models=["fixture-model"], enabled=True))
        catalog = await authority.publish_catalog(admin, CatalogEntry(kind="credential", resource_id="vin-platform-openai",
            owner_id="fixture-admin", name="Fixture provider reference", model_names=["fixture-model"]))
        await authority.grant(admin, ResourceGrant(catalog_id=catalog, subject_kind="user", subject_id="fixture-customer",
            permissions=["view", "bind", "execute"]))
        attempt = await authority.quota.reserve(customer, budget=600, purpose="chat", model="fixture-model")
        await authority.quota.settle("fixture", attempt, 15)
        await authority.jobs.enqueue(customer, kind="delivery", key="fixture-case-result-v1",
            payload={"case_id": "fixture-case", "body": "saved fixture response"})
    finally:
        await engine.dispose()


async def verify_sql():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine
    from agentscope.app.vin_platform import VinPlatformService
    from agentscope.app.vin_platform import _tables as t
    engine = create_async_engine("postgresql+asyncpg://vinfixture@127.0.0.1:5432/vinfixture")
    authority = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(), encryption_key=FIXTURE_ENCRYPTION_KEY)
    try:
        await authority.check_schema()
        async with engine.connect() as db:
            secret = (await db.execute(select(t.links.c.secret_ref).where(t.links.c.id == "fixture-link"))).scalar_one()
        assert await authority.secret_get("fixture", secret, "domain-link") == "offline-link-material-for-restore"
        customer = await authority.context("fixture-customer")
        jobs = await authority.jobs.list(customer, "delivery")
        assert len(jobs) == 1 and jobs[0].payload["body"]["case_id"] == "fixture-case"
        assert (await authority.jobs.context_for(jobs[0])).billing_subject_id == "fixture-customer"
        assert all(b["used"] == 15 for b in (await authority.quota.usage(customer))["buckets"])
        return {"encrypted_fixture_secret_recovered": True, "job_owner_context_match": True, "quota_ledger_match": True}
    finally:
        await engine.dispose()


def workspace(path, verify=False):
    from qdrant_client import QdrantClient, models
    base = Path(path)
    if not verify:
        (base / "fixture-customer").mkdir(parents=True)
        (base / "fixture-customer/case.json").write_text(json.dumps({"owner": "fixture-customer", "case": "fixture-case"}))
    client = QdrantClient(path=str(base / "qdrant"))
    try:
        if not verify:
            client.create_collection("vin-fixture", vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
            client.upsert("vin-fixture", points=[models.PointStruct(id=1, vector=[1.0, 0.0],
                payload={"owner": "fixture-customer", "document": "fixture-document-v1"})])
        points, _ = client.scroll("vin-fixture", with_vectors=True)
        assert len(points) == 1 and points[0].payload["owner"] == "fixture-customer"
        assert json.loads((base / "fixture-customer/case.json").read_text())["case"] == "fixture-case"
        return {"points": len(points), "private_manifest_match": True}
    finally:
        client.close()


def fingerprints(container):
    query = " UNION ALL ".join("SELECT '" + name + "' AS name, count(*) AS n, md5(coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb)::text) AS hash FROM " + name + " x" for name in TABLES)
    return json.loads(docker("exec", container, "psql", "-U", "vinfixture", "-d", "vinfixture", "-Atc",
        "SELECT json_agg(row_to_json(t)) FROM (" + query + ") t"))


def rehearse(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    prefix = "vin-n1-c10-" + uuid4().hex[:10]
    orchestrator, cli_source = prefix + "-runner", prefix + "-cli"
    source = output / "source"
    scripts = source / "deploy/vps"
    scripts.mkdir(parents=True)
    hashes = {}
    for name in ("backup.sh", "verify-restore.sh"):
        content = (SERVICE / "deploy/vps" / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        (scripts / name).write_bytes(content.encode())
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
    (output / "bin").mkdir()
    (output / "docker-config/cli-plugins").mkdir(parents=True)
    compose = {"services": {}, "volumes": {k: {} for k in ("postgres", "redis", "minio", "workspaces")}}
    for name in ("app", "web", "demo-mcp"):
        compose["services"][name] = {"image": QA_IMAGE, "network_mode": "none", "entrypoint": ["python", "-c", "import signal,sys,time; signal.signal(signal.SIGTERM,lambda *_:sys.exit(0)); time.sleep(1000000)"],
            "environment": {"S3_BUCKET": "agentscope"}}
    compose["services"]["app"]["volumes"] = ["workspaces:/app/examples/agent_service/workspaces"]
    compose["services"]["postgres"] = {"image": INFRA["postgres"], "network_mode": "none",
        "environment": {"POSTGRES_USER": "vinfixture", "POSTGRES_DB": "vinfixture", "POSTGRES_PASSWORD": "offline-vin-fixture-only"},
        "volumes": ["postgres:/var/lib/postgresql/data"]}
    compose["services"]["redis"] = {"image": INFRA["redis"], "network_mode": "none", "command": ["redis-server", "--appendonly", "yes"], "volumes": ["redis:/data"]}
    compose["services"]["minio"] = {"image": INFRA["minio"], "network_mode": "none", "command": ["server", "/data"],
        "environment": {"MINIO_ROOT_USER": "vinfixture", "MINIO_ROOT_PASSWORD": "offline-vin-fixture-only"}, "volumes": ["minio:/data"]}
    (source / "compose.yaml").write_text(json.dumps(compose))
    (source / "fixture.env").write_text("FIXTURE_ONLY=true\nVIN_PLATFORM_ENCRYPTION_KEY=" + FIXTURE_ENCRYPTION_KEY + "\n")
    revision = call("git", "-c", "safe.directory=" + REPO.as_posix(), "-C", str(REPO), "rev-parse", "HEAD")
    restored = []
    volumes = []
    created = False
    try:
        docker("create", "--name", cli_source, "docker:27-cli")
        docker("cp", cli_source + ":/usr/local/bin/docker", str(output / "bin/docker"))
        docker("cp", cli_source + ":/usr/local/libexec/docker/cli-plugins/docker-compose", str(output / "docker-config/cli-plugins/docker-compose"))
        docker("run", "-d", "--pull", "never", "--network", "none", "--name", orchestrator,
            "--mount", "type=bind,src=" + output.as_posix() + ",dst=/fixture",
            "--mount", "type=bind,src=" + REPO.as_posix() + ",dst=/workspace,readonly",
            "--mount", "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock",
            "-e", "PATH=/fixture/bin:/usr/local/bin:/usr/bin:/bin", "-e", "DOCKER_CONFIG=/fixture/docker-config",
            "--entrypoint", "python", QA_IMAGE, "-c", "import time; time.sleep(1000000)")
        created = True
        comp = ["exec", orchestrator, "docker", "compose", "-p", prefix, "--env-file", "/fixture/source/fixture.env", "-f", "/fixture/source/compose.yaml"]
        docker(*comp, "up", "-d", "--pull", "never")
        pg, redis, minio, app = [prefix + "-" + s + "-1" for s in ("postgres", "redis", "minio", "app")]
        for _ in range(60):
            if docker("exec", pg, "pg_isready", "-U", "vinfixture", check=False).returncode == 0:
                break
            time.sleep(1)
        docker("run", "--rm", "--pull", "never", "--network", "container:" + pg,
            "--mount", "type=bind,src=" + REPO.as_posix() + ",dst=/workspace,readonly", "-e", "PYTHONPATH=/workspace/platform_VP/agentscope/src",
            "--entrypoint", "python", QA_IMAGE, "/workspace/platform_VP/agentscope/tests/vin_release_rehearsal.py", "--seed")
        docker("exec", redis, "redis-cli", "SET", "fixture:credential", "server-managed:vin-platform-openai")
        docker("exec", redis, "redis-cli", "SET", "fixture:delivery", "immutable-response-v1")
        docker("exec", redis, "redis-cli", "SET", "fixture:lease", "owner:fixture-customer", "EX", "3600")
        ready = 'mc --config-dir /tmp/fixture-mc alias set self http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc --config-dir /tmp/fixture-mc ready self >/dev/null'
        for _ in range(60):
            if docker("exec", minio, "sh", "-c", ready, check=False).returncode == 0:
                break
            time.sleep(1)
        docker("exec", minio, "mc", "--config-dir", "/tmp/fixture-mc", "mb", "self/agentscope")
        for key, value in OBJECTS.items():
            docker("exec", "-i", minio, "mc", "--config-dir", "/tmp/fixture-mc", "pipe", "self/agentscope/" + key, data=value.encode())
        docker("exec", "-e", "PYTHONPATH=/workspace/platform_VP/agentscope/src", orchestrator, "docker", "run", "--rm", "--pull", "never", "--network", "none",
            "--mount", "type=volume,src=" + prefix + "_workspaces,dst=/data", "--entrypoint", "python", QA_IMAGE, "-c",
            "import json; from pathlib import Path; from qdrant_client import QdrantClient,models; p=Path('/data/fixture-customer');p.mkdir();(p/'case.json').write_text(json.dumps({'owner':'fixture-customer','case':'fixture-case'}));c=QdrantClient(path='/data/qdrant');c.create_collection('vin-fixture',vectors_config=models.VectorParams(size=2,distance=models.Distance.COSINE));c.upsert('vin-fixture',points=[models.PointStruct(id=1,vector=[1.0,0.0],payload={'owner':'fixture-customer','document':'fixture-document-v1'})]);c.close()")
        expected = fingerprints(pg)
        env = ["exec", "-e", "COMPOSE_FILES=compose.yaml", "-e", "ENV_FILE=/fixture/source/fixture.env", "-e", "INCLUDE_IMAGES=false",
            "-e", "DEPLOY_ENVIRONMENT=disposable_fixture", "-e", "SOURCE_REVISION=" + revision]
        print(docker(*env, orchestrator, "bash", "/fixture/source/deploy/vps/backup.sh", prefix, "/fixture/backups"), flush=True)
        backups = list((output / "backups").glob("*/COMPLETE"))
        assert len(backups) == 1
        backup = backups[0].parent
        inside = "/fixture/backups/" + backup.name
        print(docker("exec", "-e", "RESTORE_EVIDENCE=/fixture/restore-script.json", "-e", "DEPLOY_ENVIRONMENT=disposable_fixture", "-e", "SOURCE_REVISION=" + revision,
            orchestrator, "bash", "/fixture/source/deploy/vps/verify-restore.sh", inside), flush=True)
        # Second isolated restore verifies actual contents beyond readiness/counts.
        for store in ("postgres", "redis", "minio", "workspaces"):
            volume = prefix + "-deep-" + store
            docker("volume", "create", volume)
            volumes.append(volume)
            if store != "postgres":
                with (backup / (store + ".tar.gz")).open("rb") as stream:
                    docker("run", "--rm", "-i", "--pull", "never", "--network", "none", "--mount", "type=volume,src=" + volume + ",dst=/target", "--entrypoint", "tar", QA_IMAGE, "-C", "/target", "-xzf", "-", data=stream.read())
        for store in ("postgres", "redis", "minio"):
            name = prefix + "-deep-" + store
            args = ["run", "-d", "--pull", "never", "--network", "none", "--name", name, "--mount", "type=volume,src=" + name + ",dst=" + ("/var/lib/postgresql/data" if store == "postgres" else "/data")]
            if store == "postgres":
                args += ["-e", "POSTGRES_USER=vinfixture", "-e", "POSTGRES_DB=vinfixture", "-e", "POSTGRES_HOST_AUTH_METHOD=trust"]
            if store == "minio":
                args += ["--env-file", str(backup / "minio.env")]
            docker(*args, INFRA[store], *({"postgres": [], "redis": ["redis-server", "--appendonly", "yes"], "minio": ["server", "/data"]}[store]))
            restored.append(name)
        for _ in range(60):
            if docker("exec", restored[0], "pg_isready", "-U", "vinfixture", check=False).returncode == 0:
                break
            time.sleep(1)
        docker("exec", "-i", restored[0], "pg_restore", "-U", "vinfixture", "-d", "vinfixture", "--exit-on-error", "--no-owner", "--no-privileges", data=(backup / "postgres.dump").read_bytes())
        assert fingerprints(restored[0]) == expected
        sql_checks = json.loads(docker("run", "--rm", "--pull", "never", "--network", "container:" + restored[0],
            "--mount", "type=bind,src=" + REPO.as_posix() + ",dst=/workspace,readonly", "-e", "PYTHONPATH=/workspace/platform_VP/agentscope/src",
            "--entrypoint", "python", QA_IMAGE, "/workspace/platform_VP/agentscope/tests/vin_release_rehearsal.py", "--verify-sql"))
        assert docker("exec", restored[1], "redis-cli", "DBSIZE") == "3"
        assert docker("exec", restored[1], "redis-cli", "GET", "fixture:credential") == "server-managed:vin-platform-openai"
        assert docker("exec", restored[1], "redis-cli", "GET", "fixture:delivery") == "immutable-response-v1"
        assert int(docker("exec", restored[1], "redis-cli", "TTL", "fixture:lease")) > 0
        for _ in range(60):
            if docker("exec", restored[2], "sh", "-c", ready, check=False).returncode == 0:
                break
            time.sleep(1)
        for key, value in OBJECTS.items():
            assert docker("exec", restored[2], "mc", "--config-dir", "/tmp/fixture-mc", "cat", "self/agentscope/" + key) == value
        result = json.loads(docker("run", "--rm", "--pull", "never", "--network", "none", "--mount", "type=volume,src=" + prefix + "-deep-workspaces,dst=/data",
            "--mount", "type=bind,src=" + REPO.as_posix() + ",dst=/workspace,readonly", "--entrypoint", "python", QA_IMAGE,
            "/workspace/platform_VP/agentscope/tests/vin_release_rehearsal.py", "--verify-workspace", "/data"))
        report = {"status": "PASS", "source_revision": revision, "scope": "disposable_four_store_restore",
            "deploy_scripts_sha256_lf": hashes, "postgres_tables": expected, "postgres_semantics": sql_checks,
            "redis": {"keys": 3, "values_match": True, "ttl_preserved": True},
            "minio": {"objects": len(OBJECTS), "bytes_match": True}, "workspace_qdrant": result,
            "restored_app_started": False, "model_calls": 0, "production_cutover_verified": False}
        (output / "deep-restore.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"status": "PASS", "stores_passed": 4, "stores_skipped": 0, "evidence": str(output / "deep-restore.json")}), flush=True)
    finally:
        for name in restored:
            docker("rm", "-f", name, check=False)
        for name in volumes:
            docker("volume", "rm", name, check=False)
        if created:
            docker(*comp, "down", "--volumes", check=False)
            docker("rm", "-f", orchestrator, check=False)
        docker("rm", "-f", cli_source, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--verify-sql", action="store_true")
    parser.add_argument("--verify-workspace")
    args = parser.parse_args()
    if args.seed:
        asyncio.run(seed_sql())
    elif args.verify_sql:
        print(json.dumps(asyncio.run(verify_sql())))
    elif args.verify_workspace:
        print(json.dumps(workspace(args.verify_workspace, verify=True)))
    elif args.output:
        rehearse(args.output)
    else:
        parser.error("Choose --output, --seed or --verify-workspace")
