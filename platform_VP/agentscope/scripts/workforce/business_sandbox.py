"""Prepare an isolated Platform + Domain business sandbox, without model keys.

prepare only writes a NEW private directory outside Git. It never starts Docker.
Each run owns a new project, databases and volumes; reset means preparing a new
run, so no existing data is deleted. Runtime has an internal network without an
external gateway. Local service credentials are newly generated, never copied
from .env, deployment.env, process credentials or existing containers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

REPOSITORY = Path(__file__).resolve().parents[4]
PLATFORM = REPOSITORY / "platform_VP" / "agentscope"
DOMAIN = REPOSITORY / "vinhome_Recident" / "services" / "vinhomes-api"
DECLARATION = REPOSITORY / "vinhome_Recident" / "deploy" / "platform" / "vinhomes-declaration.json"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPOSITORY), *args], text=True).strip()


def _hash_files(folder: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path = folder / relative
        if path.is_file():
            digest.update(relative.replace("\\", "/").encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def source_snapshot() -> dict:
    roots = [str(PLATFORM.relative_to(REPOSITORY)), str(DOMAIN.relative_to(REPOSITORY))]
    names = _git("ls-files", "--cached", "--others", "--exclude-standard", "--", *roots).splitlines()
    # Source fingerprints must not read credentials, artifacts or dependency caches.
    names = [name for name in names if not any(
        part.startswith((".env", ".artifacts", ".local")) or part in
        {"node_modules", "__pycache__", ".venv", "workspaces"} or ".secret." in part
        for part in Path(name).parts
    )]
    return {"commit": _git("rev-parse", "HEAD"), "branch": _git("branch", "--show-current"),
            "worktree_sha256": _hash_files(REPOSITORY, names),
            "dirty": bool(_git("status", "--porcelain", "--", *roots))}


def _write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _postgres(password: str, user: str, database: str, volume: str):
    return {
        "image": "pgvector/pgvector:pg17", "environment": {
            "POSTGRES_USER": user, "POSTGRES_PASSWORD": password, "POSTGRES_DB": database,
        }, "volumes": [f"{volume}:/var/lib/postgresql/data"],
        "healthcheck": {"test": ["CMD", "pg_isready", "-U", user, "-d", database],
                        "interval": "3s", "timeout": "3s", "retries": 30},
    }


def prepare(output: Path, run_id: str | None = None, seed: int = 42,
            platform_port: int = 18100, domain_port: int = 18098) -> dict:
    run_id = run_id or uuid4().hex[:12]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", run_id):
        raise ValueError("run_id must be 1-48 lower-case letters, digits, '-' or '_'")
    if platform_port == domain_port or any(not 1024 <= port <= 65535 for port in (platform_port, domain_port)):
        raise ValueError("Use distinct unprivileged loopback ports")
    output = Path(output).resolve()
    if output == REPOSITORY or REPOSITORY in output.parents:
        raise ValueError("Sandbox credentials/data must stay outside the repository")
    if output.exists():
        raise ValueError("Use a new output directory; existing runs are never overwritten")
    source = source_snapshot()
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    schema_dir = DOMAIN / "src" / "vinhomes_api" / "schema"
    schema_hash = _hash_files(schema_dir, [str(p.relative_to(schema_dir)) for p in schema_dir.rglob("*.sql")])
    output.mkdir(parents=True)
    os.chmod(output, 0o700)
    (output / "domain-private").mkdir()
    project = "workforce-sandbox-" + run_id.replace("_", "-") + "-" + uuid4().hex[:8]
    database = "owner_pilot_test_" + uuid5(NAMESPACE_URL, f"{project}/{seed}").hex
    local = {key: secrets.token_hex(32) for key in (
        "DOMAIN_OWNER_PASSWORD", "DOMAIN_RUNTIME_PASSWORD", "DOMAIN_SIGNING_KEY", "MCP_TOKEN",
        "CONFIG_ENCRYPTION_KEY", "PLATFORM_DB_PASSWORD", "AUTH_JWT_SECRET", "AUTH_REFRESH_PEPPER",
        "PARTNER_API_KEY_PEPPER", "PARTNER_API_PROVISIONING_SECRET", "MINIO_PASSWORD",
    )}
    platform_image = f"workforce-business-sandbox-platform:{run_id}"
    domain_image = f"workforce-business-sandbox-domain:{run_id}"
    domain_env = {
        "DATABASE_URL": f"postgresql+asyncpg://sandbox_runtime:{local['DOMAIN_RUNTIME_PASSWORD']}@domain-postgres:5432/{database}",
        "VINHOMES_API_DATABASE_URL": f"postgresql+asyncpg://sandbox_runtime:{local['DOMAIN_RUNTIME_PASSWORD']}@domain-postgres:5432/{database}",
        "VINHOMES_API_TENANT_ID": "11111111-1111-5111-a111-111111111111",
        "VINHOMES_API_PASSWORD_AUTH": "1", "VINHOMES_API_SESSION_NAMESPACE": project,
        "VINHOMES_API_VOLUME_FILE_STORAGE": "1", "VINHOMES_API_SECURE_COOKIES": "0",
        "VINHOMES_API_RESIDENT_SIGNING_KEY": local["DOMAIN_SIGNING_KEY"],
        "VINHOMES_API_PLATFORM_MCP_TOKEN": local["MCP_TOKEN"],
        "VINHOMES_API_CONFIG_ENCRYPTION_KEY": local["CONFIG_ENCRYPTION_KEY"],
        "VINHOMES_API_MCP_ALLOWED_HOSTS": f"domain-api:8000,localhost:{domain_port},127.0.0.1:{domain_port}",
        "VINHOMES_PLATFORM_ALLOWED_HOSTS": "platform",
        "VINHOMES_API_PLATFORM_URL": "", "VINHOMES_API_RECEPTION_URL": "",
        "VINHOMES_API_EMBEDDING_API_KEY": "", "VINHOMES_API_S3_ENDPOINT": "",
        "VINHOMES_TRAVEL_MOCK_ENABLED": "1",
        "VINHOMES_API_RESIDENT_ALLOWED_ORIGINS": f"http://localhost:{domain_port},http://127.0.0.1:{domain_port}",
        "VINHOMES_API_ALLOWED_ORIGINS": f"http://localhost:{domain_port},http://127.0.0.1:{domain_port}",
    }
    services = {
        "domain-postgres": _postgres(local["DOMAIN_OWNER_PASSWORD"], "sandbox_owner", "postgres", "domain-db"),
        "domain-init": {
            "image": domain_image, "build": {"context": str(DOMAIN)}, "user": "0:0",
            "network_mode": "service:domain-postgres",
            "depends_on": {"domain-postgres": {"condition": "service_healthy"}},
            "environment": {
                "DATABASE_URL": f"postgresql://sandbox_owner:{local['DOMAIN_OWNER_PASSWORD']}@127.0.0.1:5432/{database}",
                "SANDBOX_RUNTIME_PASSWORD": local["DOMAIN_RUNTIME_PASSWORD"],
                "SANDBOX_PRIVATE_DIR": "/sandbox", "SANDBOX_RUN_ID": run_id,
                "SANDBOX_SEED": str(seed), "VINHOMES_API_EMBEDDING_API_KEY": "",
            }, "volumes": [{"type": "bind", "source": str(output / "domain-private"), "target": "/sandbox"}],
            "command": ["python", "-m", "vinhomes_api.business_sandbox_fixture"], "restart": "no",
        },
        "domain-api": {
            "image": domain_image, "environment": domain_env,
            "depends_on": {"domain-init": {"condition": "service_completed_successfully"}},
            "ports": [f"127.0.0.1:{domain_port}:8000"],
            "volumes": ["domain-files:/var/lib/vinhomes/files"],
            "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=5)"],
                            "interval": "5s", "timeout": "6s", "retries": 30},
        },
        "platform-postgres": _postgres(local["PLATFORM_DB_PASSWORD"], "sandbox_platform", "sandbox_platform", "platform-db"),
        "redis": {"image": "redis:7-alpine", "command": ["redis-server", "--appendonly", "yes"],
                  "volumes": ["redis:/data"], "healthcheck": {"test": ["CMD", "redis-cli", "ping"],
                                                           "interval": "3s", "timeout": "3s", "retries": 20}},
        "minio": {"image": "cgr.dev/chainguard/minio:latest", "command": ["server", "/data"],
                  "environment": {"MINIO_ROOT_USER": "sandboxminio", "MINIO_ROOT_PASSWORD": local["MINIO_PASSWORD"]},
                  "volumes": ["minio:/data"]},
        "minio-init": {"image": platform_image, "depends_on": ["minio"],
                       "environment": {"AWS_ACCESS_KEY_ID": "sandboxminio", "AWS_SECRET_ACCESS_KEY": local["MINIO_PASSWORD"]},
                       "entrypoint": ["python", "-c"], "command": [
                           ("import boto3,time\n"
                           "s=boto3.client('s3',endpoint_url='http://minio:9000',region_name='us-east-1')\n"
                           "for attempt in range(60):\n"
                           " try:\n"
                           "  if not any(b['Name']=='sandbox' for b in s.list_buckets()['Buckets']): s.create_bucket(Bucket='sandbox')\n"
                           "  break\n"
                           " except Exception:\n"
                           "  if attempt==59: raise\n"
                           "  time.sleep(1)\n")
                       ], "restart": "no"},
        "platform": {
            "image": platform_image, "build": {"context": str(PLATFORM), "dockerfile": "Dockerfile"},
            "environment": {
                "AGENTSCOPE_SQL_URL": f"postgresql+asyncpg://sandbox_platform:{local['PLATFORM_DB_PASSWORD']}@platform-postgres:5432/sandbox_platform",
                **{key: local[key] for key in ("AUTH_JWT_SECRET", "AUTH_REFRESH_PEPPER", "PARTNER_API_KEY_PEPPER", "PARTNER_API_PROVISIONING_SECRET")},
                "AUTH_ENABLED": "true", "AUTH_DEFAULT_TENANT_ID": "default", "AUTH_COOKIE_SECURE": "false",
                "REDIS_HOST": "redis", "REDIS_PORT": "6379", "REDIS_DB": "0", "WORKFORCE_PARTNER_API": "true",
                "S3_ENABLED": "true", "S3_ENDPOINT": "http://minio:9000", "S3_BUCKET": "sandbox",
                "AWS_ACCESS_KEY_ID": "sandboxminio", "AWS_SECRET_ACCESS_KEY": local["MINIO_PASSWORD"],
                "AWS_DEFAULT_REGION": "us-east-1", "OPENAI_API_KEY": "", "DASHSCOPE_API_KEY": "",
                "MEMORY_EMBEDDING_API_KEY": "", "WORKFORCE_PLATFORM_OPENAI_API_KEY": "",
                "WORKFORCE_MODEL_NAME": "", "WORKFORCE_LEARNING": "false",
            }, "ports": [f"127.0.0.1:{platform_port}:8000"],
            "volumes": ["platform-workspaces:/app/examples/agent_service/workspaces"],
            "depends_on": {"platform-postgres": {"condition": "service_healthy"}, "redis": {"condition": "service_healthy"},
                           "minio-init": {"condition": "service_completed_successfully"}},
        },
    }
    for service in services.values():
        service["labels"] = {"workforce.data_mode": "synthetic_test", "workforce.run_id": run_id}
    compose = {"name": project, "services": services,
               "networks": {"default": {"internal": True}},
               "volumes": {name: {} for name in ("domain-db", "domain-files", "platform-db", "redis", "minio", "platform-workspaces")}}
    _write_json(output / "compose.json", compose)
    _write_json(output / "local-credentials.secret.json", local)
    _write_json(output / "declaration.json", declaration)
    manifest = {
        "manifest_version": 1, "run_id": run_id, "seed": seed, "data_mode": "synthetic_test",
        "prepared_at": datetime.now(UTC).isoformat(), "source": source,
        "project": project, "database": database,
        "images": {"platform": platform_image, "domain": domain_image}, "runtime_images": {},
        "model": {"mode": "unconfigured", "provider_calls": 0, "reason": "No provider keys loaded; operator supplies test model later"},
        "declaration_sha256": hashlib.sha256((output / "declaration.json").read_bytes()).hexdigest(),
        "schema_sha256": schema_hash,
        "compose_sha256": hashlib.sha256((output / "compose.json").read_bytes()).hexdigest(),
        "endpoints": {"platform": f"http://127.0.0.1:{platform_port}", "domain": f"http://127.0.0.1:{domain_port}",
                      "internal_platform": "http://platform:8000", "internal_mcp": "http://domain-api:8000/mcp"},
        "fixture": "domain-private/fixture.json", "scenario_count": 24, "repetitions": 3,
        "connection_status": "not_onboarded", "runtime_status": "prepared_only",
        "reset_policy": "prepare a new output/run/project; existing databases and volumes are retained",
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def record_runtime(output: Path) -> dict:
    """Read image IDs after startup; never starts, stops or deletes a container."""
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    compose = json.loads((output / "compose.json").read_text(encoding="utf-8"))
    if not compose.get("networks", {}).get("default", {}).get("internal"):
        raise ValueError("Sandbox network must stay internal")
    if hashlib.sha256((output / "compose.json").read_bytes()).hexdigest() != manifest["compose_sha256"]:
        raise ValueError("Compose changed since preparation; prepare a fresh run")
    if source_snapshot() != manifest["source"]:
        raise ValueError("Source changed since preparation; prepare a fresh run")
    rows = {}
    for name in compose["services"]:
        ids = subprocess.check_output(["docker", "compose", "-f", str(output / "compose.json"),
                                       "ps", "--all", "--quiet", name], text=True).split()
        if len(ids) != 1:
            raise ValueError(f"Expected one sandbox container for {name}")
        value = json.loads(subprocess.check_output(["docker", "inspect", "--format",
                                                   '{{json .}}', ids[0]], text=True))
        labels = value["Config"].get("Labels") or {}
        if labels.get("workforce.run_id") != manifest["run_id"] or labels.get("workforce.data_mode") != "synthetic_test":
            raise ValueError("Container does not belong to this synthetic run")
        rows[name] = {"image_id": value["Image"], "container_id": value["Id"],
                      "status": value["State"]["Status"], "exit_code": value["State"]["ExitCode"]}
    fixture = output / manifest["fixture"]
    if not fixture.is_file():
        raise ValueError("Domain fixture was not materialized")
    manifest["runtime_images"] = rows
    manifest["fixture_sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    manifest["runtime_status"] = "recorded"
    manifest["recorded_at"] = datetime.now(UTC).isoformat()
    _write_json(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("prepare")
    new.add_argument("--output", type=Path, required=True)
    new.add_argument("--run-id")
    new.add_argument("--seed", type=int, default=42)
    new.add_argument("--platform-port", type=int, default=18100)
    new.add_argument("--domain-port", type=int, default=18098)
    capture = sub.add_parser("record-runtime")
    capture.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output, args.run_id, args.seed, args.platform_port, args.domain_port)
    else:
        result = record_runtime(args.output)
    # Never print compose or credentials; only public provenance and test status.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
