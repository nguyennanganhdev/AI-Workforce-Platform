"""Create a persistent LOCAL synthetic sandbox. No production/Agent connection.

Run with the Domain Python environment: --output E:/Vinhomes-Deploy/owner-sandbox-<new-name>
Output must be outside Git and empty. The PostgreSQL container/volume are retained.
"""

import argparse
import asyncio
import importlib.util
import json
import secrets
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import asyncpg
from vinhomes_api import database
from vinhomes_api.bootstrap import bootstrap
from vinhomes_api.owner_sandbox import MARKER, materialize


def docker(*args, **kwargs):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, **kwargs
    ).stdout.strip()


def start(output):
    output = output.resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise ValueError(
            "Keep sandbox credentials and generated data outside the repository"
        )
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Use a new empty directory; existing sandboxes are never overwritten"
        )
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        "sandbox_generator", Path(__file__).with_name("prepare-owner-sandbox.py")
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    bundle = output / "bundle"
    generator.prepare(bundle)
    suffix = uuid4().hex
    name = "vinhomes-owner-sandbox-" + suffix[:10]
    volume = name + "-data"
    dbname = "owner_pilot_test_" + suffix
    password, runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    env_file = output / "postgres.secret.env"
    env_file.write_text(
        "POSTGRES_USER=sandbox_owner\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD="
        + password
        + "\n",
        encoding="utf-8",
    )
    state = {
        "data_mode": "synthetic_test",
        "container": name,
        "volume": volume,
        "database": dbname,
        "production_changed": False,
        "status": "creating",
    }

    def save():
        (output / "state.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )

    save()
    docker("volume", "create", "--label", "vinhomes.data_mode=synthetic_test", volume)
    docker(
        "run",
        "-d",
        "--name",
        name,
        "--label",
        "vinhomes.data_mode=synthetic_test",
        "--env-file",
        str(env_file),
        "-p",
        "127.0.0.1::5432",
        "--memory",
        "768m",
        "--cpus",
        "2",
        "--mount",
        "type=volume,source=" + volume + ",target=/var/lib/postgresql/data",
        "--restart",
        "unless-stopped",
        "pgvector/pgvector:pg17",
    )
    for _ in range(45):
        ready = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-U", "sandbox_owner"],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError(
            "Sandbox PostgreSQL did not become ready; inspect state.json"
        )
    inspected = json.loads(docker("inspect", name))[0]
    port = inspected["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
    owner_base = f"postgresql://sandbox_owner:{password}@127.0.0.1:{port}/"
    owner_url = owner_base + dbname
    runtime_url = f"postgresql+asyncpg://sandbox_runtime:{runtime_password}@127.0.0.1:{port}/{dbname}"

    async def setup():
        await database.create(owner_base + "postgres", dbname)
        conn = await asyncpg.connect(owner_url)
        try:
            # dbname is generated here, never an input path or server-provided identifier.
            await conn.execute(f"COMMENT ON DATABASE \"{dbname}\" IS '{MARKER}'")
        finally:
            await conn.close()
        await database.migrate(owner_url)
        await bootstrap(owner_url)
        await database.role(owner_url, "sandbox_runtime", runtime_password)
        return await materialize(owner_url, bundle)

    result = asyncio.run(setup())
    (output / "accounts.secret.json").write_text(
        json.dumps(result["credentials"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "connections.secret.json").write_text(
        json.dumps({"admin": owner_url, "runtime": runtime_url}, indent=2),
        encoding="utf-8",
    )
    (output / "acceptance-data.json").write_text(
        json.dumps(result["report"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    api_env = {
        "VINHOMES_API_HOST": "127.0.0.1",
        "VINHOMES_API_PORT": "8097",
        "VINHOMES_API_DATABASE_URL": runtime_url,
        "VINHOMES_API_TENANT_ID": database.TENANT,
        "VINHOMES_API_PASSWORD_AUTH": "1",
        "VINHOMES_API_LOCAL_FILE_STORAGE": "1",
        "VINHOMES_API_RESIDENT_LOCAL_STORAGE": "1",
        "VINHOMES_API_DEMO_MODE": "0",
        "VINHOMES_API_DEV_USER_ID": "",
        "VINHOMES_API_PLATFORM_URL": "",
        "VINHOMES_API_RECEPTION_URL": "",
        "VINHOMES_API_EMBEDDING_API_KEY": "",
        "VINHOMES_API_PLATFORM_MCP_TOKEN": secrets.token_urlsafe(32),
        "VINHOMES_API_RESIDENT_ALLOWED_ORIGINS": "http://127.0.0.1:8097",
        "VINHOMES_API_SECURE_COOKIES": "0",
        "VINHOMES_API_RESIDENT_SIGNING_KEY": secrets.token_hex(32),
        "VINHOMES_RESIDENT_FILE_ROOT": str(output / "files"),
        "RECEPTION_DELEGATION_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_BASE_URL": "",
        "VINHOMES_API_S3_ENDPOINT": "",
        "VINHOMES_API_S3_ACCESS_KEY": "",
        "VINHOMES_API_S3_SECRET_KEY": "",
    }
    (output / "api.secret.json").write_text(
        json.dumps(api_env, indent=2), encoding="utf-8"
    )
    # Separate process and files directory; never inherit an active production env file.
    (output / "run-api.py").write_text(
        "import json, os\nfrom pathlib import Path\nimport uvicorn\n"
        "root=Path(__file__).resolve().parent\n"
        "os.environ.update(json.loads((root/'api.secret.json').read_text()))\n"
        "os.chdir(root)\nuvicorn.run('vinhomes_api.main:app',host='127.0.0.1',port=8097)\n",
        encoding="utf-8",
    )
    state.update(
        status="ready",
        postgres_port=int(port),
        api_url="http://127.0.0.1:8097",
        counts=result["report"]["counts"],
        accounts_file="accounts.secret.json",
    )
    save()
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(start(args.output), ensure_ascii=False, indent=2))
