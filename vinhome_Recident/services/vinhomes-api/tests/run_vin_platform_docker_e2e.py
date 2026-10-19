"""Own disposable Domain/IdP/data + real Platform stack. No deployment env files.

python tests/run_vin_platform_docker_e2e.py up --source <merged-checkout> --output <ignored-artifact-dir>
python tests/run_vin_platform_docker_e2e.py down --output <same-dir>
Fixed loopback ports 18101..18106 and 15459 must be free. Never targets an existing stack.
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx

QA = "agentscope-op2-offline-qa:20261017"
DOMAIN = "vinhomes-op2-offline-qa:20261017"
FIXTURE = Path(__file__).with_name("vin_platform_local_fixture.py")
OWN_ROOT = Path(__file__).resolve().parents[4]


def docker(*args):
    result = subprocess.run(["docker", *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if result.returncode:
        raise RuntimeError("Docker command failed: " + result.stderr[-2000:] + result.stdout[-2000:])
    return result.stdout.strip()


def wait_ready(url):
    for _ in range(80):
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.25)
    raise RuntimeError("Fixture readiness failed: " + url)


def up(source, output):
    if (output / "state.json").exists():
        raise RuntimeError("Use a new artifact directory or explicitly down the previous fixture")
    prefix = "vin-n1-r04-e2e-" + uuid4().hex[:8]
    state = {"prefix": prefix, "containers": [], "network": prefix, "source": str(source), "fixture_source": str(OWN_ROOT)}
    state["provenance"] = {}
    for label, path in (("integration", source), ("n1_fixture", OWN_ROOT)):
        revision = subprocess.check_output(["git", "-c", "safe.directory=" + path.as_posix(), "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-c", "safe.directory=" + path.as_posix(), "-C", str(path), "status", "--porcelain"], text=True).splitlines()
        state["provenance"][label] = {"revision": revision, "dirty": dirty}
    state["provenance"]["fixture_sha256"] = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    state["provenance"]["images"] = {name: docker("image", "inspect", "--format", "{{.Id}}", name)
        for name in (QA, DOMAIN, "pgvector/pgvector:pg17", "redis:7-alpine", "nginx:1.27-alpine")}
    def save():
        (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    save()
    docker("network", "create", "--label", "vin.fixture=" + prefix, prefix)
    pg = prefix + "-postgres"
    state["containers"].append(pg)
    save()
    args = ["run", "-d", "--name", pg, "--label", "vin.fixture=" + prefix, "--network", prefix]
    for port in (18101, 18102, 18103, 18104, 18105, 18106):
        args += ["-p", f"127.0.0.1:{port}:{port}"]
    docker(*args, "-p", "127.0.0.1:15459:5432", "-e", "POSTGRES_USER=vinfixture", "-e",
           "POSTGRES_PASSWORD=offline-vin-fixture-only", "-e", "POSTGRES_DB=vinfixture", "pgvector/pgvector:pg17")
    for _ in range(80):
        try:
            # The image briefly starts a Unix-socket-only init server, then
            # stops it. Wait for TCP so CREATE DATABASE cannot hit that window.
            docker("exec", pg, "pg_isready", "-h", "127.0.0.1", "-U", "vinfixture")
            break
        except RuntimeError:
            time.sleep(.25)
    else:
        raise RuntimeError("Fixture PostgreSQL did not accept TCP connections")
    for name in ("domain_e2e", "platform_e2e"):
        docker("exec", pg, "psql", "-U", "vinfixture", "-d", "vinfixture", "-c", "CREATE DATABASE " + name)
    redis = prefix + "-redis"
    state["containers"].append(redis)
    save()
    docker("run", "-d", "--name", redis, "--label", "vin.fixture=" + prefix, "--network", "container:" + pg,
           "redis:7-alpine", "redis-server", "--port", "18106", "--save", "")
    owner = "postgresql://vinfixture:offline-vin-fixture-only@127.0.0.1:5432/"
    domain_env = {"FIXTURE_DOMAIN_OWNER_URL": owner + "domain_e2e", "VINHOMES_CUSTOMER_PLATFORM_ENABLED": "true",
        "VINHOMES_API_DATABASE_URL": "postgresql+asyncpg://vin_runtime:offline-runtime-only@127.0.0.1:5432/domain_e2e",
        "VINHOMES_API_HOST": "127.0.0.1", "VINHOMES_API_PORT": "18101", "VINHOMES_API_TENANT_ID": "11111111-1111-5111-a111-111111111111",
        "VINHOMES_API_PASSWORD_AUTH": "1", "VINHOMES_API_VOLUME_FILE_STORAGE": "1", "VINHOMES_RESIDENT_FILE_ROOT": "/tmp/fixture-files",
        "VINHOMES_API_PLATFORM_MCP_TOKEN": "offline-e2e-mcp-control-token-0123456789",
        "VINHOMES_API_RESIDENT_SIGNING_KEY": "ab" * 32, "VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED": "false"}
    platform_env = {"VIN_PLATFORM_ENABLED": "true", "AGENTSCOPE_SQL_URL": owner.replace("postgresql:", "postgresql+asyncpg:") + "platform_e2e",
        "VIN_PLATFORM_ENCRYPTION_KEY": "ZmFrZS1maXh0dXJlLWZlcm5ldC1rZXktMDAwMDAwMDA=",
        "WORKFORCE_PLATFORM_OPENAI_API_KEY": "offline-scripted-model-no-real-key",
        "WORKFORCE_PLATFORM_OPENAI_BASE_URL": "http://127.0.0.1:18103/v1"}
    def run(mode, image, env, background=False):
        args = ["run", "--network", "container:" + pg, "--mount", f"type=bind,source={source},target=/workspace,readonly",
                "--mount", f"type=bind,source={OWN_ROOT / 'vinhome_Recident/services/vinhomes-api/src'},target=/workspace/vinhome_Recident/services/vinhomes-api/src,readonly",
                "--mount", f"type=bind,source={FIXTURE},target=/fixture.py,readonly",
                "-e", "PYTHONPATH=/workspace/platform_VP/agentscope/src:/workspace/vinhome_Recident/services/vinhomes-api/src"]
        for key, value in env.items():
            args += ["-e", key + "=" + value]
        if background:
            name = prefix + "-" + mode
            state["containers"].append(name)
            save()
            args += ["-d", "--name", name, "--label", "vin.fixture=" + prefix]
        else:
            args += ["--rm"]
        return docker(*args, "--entrypoint", "python", image, "/fixture.py", mode)
    state["domain_users"] = json.loads(run("seed-domain", DOMAIN, domain_env).splitlines()[-1])
    state["platform_seed"] = json.loads(run("seed-platform", QA, platform_env).splitlines()[-1])
    save()
    # Server containers share one isolated loopback namespace, matching registered browser URLs.
    run("model", QA, {}, background=True)
    run("domain", DOMAIN, domain_env, background=True)
    run("platform", QA, platform_env, background=True)
    wait_ready("http://127.0.0.1:18101/ready")
    wait_ready("http://127.0.0.1:18102/health")
    state["status"] = "READY"
    save()
    print("Disposable fixture ready; no real provider credentials; state at " + str(output / "state.json"))


def down(output):
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    prefix = state["prefix"]
    if not prefix.startswith("vin-n1-r04-e2e-"):
        raise RuntimeError("Refuse non-fixture cleanup")
    for name in reversed(state["containers"]):
        try:
            label = docker("inspect", "--format", '{{index .Config.Labels "vin.fixture"}}', name)
            if label != prefix:
                raise RuntimeError("Refuse foreign container " + name)
            (output / (name + ".log")).write_text(docker("logs", name), encoding="utf-8")
            docker("rm", "-f", "-v", name)
        except RuntimeError as exc:
            if "No such" not in str(exc):
                raise
    label = docker("network", "inspect", "--format", '{{index .Labels "vin.fixture"}}', state["network"])
    if label != prefix:
        raise RuntimeError("Refuse foreign network cleanup")
    docker("network", "rm", state["network"])
    state["status"] = "STOPPED"
    (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def web(output, platform_dist, staff_dist):
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    for path in (platform_dist, staff_dist):
        if not path or not (path / "index.html").is_file():
            raise RuntimeError("Pass existing Platform Vin-enabled and Domain staff build directories")
    config = output / "nginx.conf"
    config.write_text('''events {}
http {
 include /etc/nginx/mime.types;
 server {
  listen 18104; root /platform; index index.html;
  location /api/ {
   proxy_pass http://127.0.0.1:18102/; proxy_set_header Host $http_host;
   proxy_http_version 1.1; proxy_buffering off; proxy_read_timeout 300s;
   proxy_cookie_path /auth /api/auth;
  }
  location / { try_files $uri /index.html; }
 }
 server {
  listen 18105; root /staff; index index.html;
  client_max_body_size 25m;
  location /api/business/ {
   proxy_pass http://127.0.0.1:18101/; proxy_set_header Host $http_host;
   proxy_set_header X-Vinhomes-Surface "";
  }
  location / { try_files $uri /index.html; }
 }
}
''', encoding="utf-8")
    prefix = state["prefix"]
    name = prefix + "-web"
    state["containers"].append(name)
    state["web_builds"] = {"platform": str(platform_dist), "staff": str(staff_dist)}
    state["provenance"]["web_builds_sha256"] = {}
    for label, path in (("platform", platform_dist), ("staff", staff_dist)):
        checksum = hashlib.sha256()
        for file in sorted(path.rglob("*")):
            if file.is_file():
                checksum.update(file.relative_to(path).as_posix().encode())
                checksum.update(file.read_bytes())
        state["provenance"]["web_builds_sha256"][label] = checksum.hexdigest()
    (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    docker("run", "-d", "--name", name, "--label", "vin.fixture=" + prefix, "--network", "container:" + prefix + "-postgres",
        "--mount", f"type=bind,source={config},target=/etc/nginx/nginx.conf,readonly",
        "--mount", f"type=bind,source={platform_dist},target=/platform,readonly",
        "--mount", f"type=bind,source={staff_dist},target=/staff,readonly", "nginx:1.27-alpine")
    wait_ready("http://127.0.0.1:18104/login")
    wait_ready("http://127.0.0.1:18105/operations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "web", "down"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform-dist", type=Path)
    parser.add_argument("--staff-dist", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.action == "up":
        up(args.source.resolve(), args.output.resolve())
    elif args.action == "web":
        web(args.output.resolve(), args.platform_dist.resolve(), args.staff_dist.resolve())
    else:
        down(args.output.resolve())
