"""Validate Domain package/compose with fake config; never load deployment.env.

python tests/vin_domain_rc_check.py --output <ignored-artifact-dir> [--image <tag>]
This does not start a service, run a model, migrate an app DB or deploy.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[4]
SERVICE = Path(__file__).resolve().parents[1]


def run(*args, env=None):
    result = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:] + result.stdout[-1500:])
    return result.stdout


def check(output, image, source_revision=None):
    report = {"status": "RUNNING", "paid_model_calls": 0, "app_db_migrations": 0, "deployed": False}
    output.mkdir(parents=True, exist_ok=True)
    try:
        # A minimal process environment and explicit fake --env-file prevent
        # host model keys/config or implicit Compose .env from taking effect.
        process_env = {key: value for key, value in os.environ.items() if key.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA", "DOCKER_HOST", "DOCKER_CONTEXT",
            "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "SYSTEMDRIVE", "PROCESSOR_ARCHITECTURE"}}
        fake = {key: "offline-compose-only-no-service-started" for key in (
            "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "API_DB_PASSWORD", "S3_ACCESS_KEY", "S3_SECRET_KEY",
            "RECEPTION_SERVICE_TOKEN", "OPENAI_API_KEY")}
        fake.update(RESIDENT_SIGNING_KEY="12" * 32, RECEPTION_DELEGATION_KEY="34" * 32)
        with tempfile.TemporaryDirectory(prefix="vin-domain-compose-") as directory:
            env_file = Path(directory) / "fixture.env"
            env_file.write_text("\n".join(key + "=" + value for key, value in fake.items()), encoding="utf-8")
            for active in (False, True):
                env = {**process_env, "VINHOMES_CUSTOMER_PLATFORM_ENABLED": str(active).lower()}
                raw = run("docker", "compose", "--env-file", str(env_file), "-f", str(ROOT / "vinhome_Recident/deploy/compose.yml"),
                    "config", "--format", "json", env=env)
                services = json.loads(raw)["services"]
                for name in ("api", "platform-sync"):
                    flags = services[name]["environment"]
                    assert flags["VINHOMES_CUSTOMER_PLATFORM_ENABLED"] == str(active).lower()
                    assert flags["VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED"] == "false"
                    assert json.loads(flags["VINHOMES_CHATBOT_PLATFORM_COHORTS"]) == []
        report["compose_flag_wiring"] = "PASS; linked-customer false/true, cohort cutover always off"
        if image:
            inspect = json.loads(run("docker", "image", "inspect", image))[0]
            revision = source_revision or run("git", "-c", "safe.directory=" + ROOT.as_posix(), "-C", str(ROOT), "rev-parse", "HEAD").strip()
            assert inspect["Config"]["Labels"]["org.opencontainers.image.revision"] == revision
            assert inspect["Config"]["Cmd"] == ["python", "-m", "vinhomes_api"]
            run("docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image, "-m", "pip", "check")
            script = """import hashlib,json,os
from pathlib import Path
import vinhomes_api
root=Path(vinhomes_api.__file__).parent
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in root.rglob('*') if p.is_file() and p.suffix in {'.py','.sql'}}
bad=[str(p) for p in Path('/opt/vinhomes-api').rglob('*')
    if p.name=='.artifacts' or p.name=='deployment.env' or p.name.startswith('.env') or '.secret.' in p.name]
print(json.dumps({'uid':os.getuid(),'files':files,'excluded_file_violations':bad}))"""
            actual = json.loads(run("docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image, "-c", script))
            source = SERVICE / "src/vinhomes_api"
            expected = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source.rglob("*") if p.is_file() and p.suffix in {".py", ".sql"}}
            assert actual["uid"] != 0 and not actual["excluded_file_violations"]
            assert actual["files"] == expected, "Installed Python/SQL package differs from source"
            report["image"] = {"tag": image, "id": inspect["Id"], "revision": revision,
                "python_sql_files_matched": len(expected), "pip_check": "PASS", "uid": actual["uid"],
                "cmd": inspect["Config"]["Cmd"], "secret_artifact_files": 0}
        report["status"] = "PASS"
    except BaseException as exc:
        report.update(status="FAIL", error=type(exc).__name__ + ": " + str(exc)[:1500])
        raise
    finally:
        (output / "domain-package.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image")
    parser.add_argument("--source-revision", help="Pinned image revision; current Python/SQL files must still match")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    check(options.output.resolve(), options.image, options.source_revision)
