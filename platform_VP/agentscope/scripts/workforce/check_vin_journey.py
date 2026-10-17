"""Offline browser/runtime journey using real ASGI apps and disposable Domain PG."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-url", required=True, help="Disposable loopback PostgreSQL only")
    parser.add_argument("--ui-dir", help="Frontend dist built with Vin enabled and API /api; defaults to the repo frontend dist")
    parser.add_argument("--scenario", choices=["customer", "customer-runtime", "admin", "builder", "automation"], help="Run just one independent journey")
    options = parser.parse_args()
    postgres = urlsplit(options.admin_url)
    if (postgres.scheme != "postgresql" or postgres.hostname not in {"127.0.0.1", "localhost", "::1"}
            or postgres.query):
        parser.error("Only an explicit loopback fixture PostgreSQL URL is allowed")
    root = Path(__file__).resolve().parents[2]
    domain = root.parents[1] / "vinhome_Recident/services/vinhomes-api"
    ui_dir = Path(options.ui_dir).resolve() if options.ui_dir else root / "examples/web_ui/frontend/dist"
    if not (ui_dir / "index.html").is_file():
        parser.error("Build the Vin-enabled frontend before running this journey")
    os.chdir(root)
    for path in (root / "src", root / "tests", root / "tests/workforce/console", domain / "src", domain / "tests"):
        sys.path.insert(0, str(path))
    for name in list(os.environ):
        if name != "TIKTOKEN_CACHE_DIR" and (
            any(part in name for part in ("API_KEY", "TOKEN", "SECRET"))
            or name.endswith(("_DATABASE_URL", "_POSTGRES_URL", "_ADMIN_URL", "_RUNTIME_URL"))
        ):
            os.environ.pop(name, None)
    role, password = "vin_n2_journey_" + uuid4().hex, uuid4().hex
    runtime = postgres._replace(netloc=role + ":" + password + "@" + postgres.netloc.rsplit("@", 1)[-1])
    os.environ.update(RESIDENT_TEST_ADMIN_URL=options.admin_url, RESIDENT_TEST_RUNTIME_URL=urlunsplit(runtime),
        VIN_UI_DIST=str(ui_dir))
    original_connect, original_resolve = socket.socket.connect, socket.getaddrinfo
    forbidden = []

    def deny(*args, **kwargs):
        forbidden.append(1)
        raise RuntimeError("OFFLINE_TEST: only the disposable PostgreSQL and preview ports are allowed")

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"} and address[1] == (postgres.port or 5432):
            return original_connect(sock, address)
        return deny()

    def resolve(host, *args, **kwargs):
        if host not in {"127.0.0.1", "localhost", "::1", None}:
            return deny()
        return original_resolve(host, *args, **kwargs)

    if sys.platform == "win32":
        def socketpair(*args, **kwargs):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                original_connect(client, listener.getsockname())
                server, _ = listener.accept()
            return server, client
        socket.socketpair = socketpair
    socket.socket.connect, socket.getaddrinfo = connect, resolve
    socket.socket.connect_ex = deny
    socket.socket.sendto = deny
    import asyncpg
    import pytest

    async def provision():
        db = await asyncpg.connect(options.admin_url)
        try:
            await db.execute(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\' NOSUPERUSER NOBYPASSRLS')
        finally:
            await db.close()

    async def cleanup():
        assert role.startswith("vin_n2_journey_") and len(role) == 47
        db = await asyncpg.connect(options.admin_url)
        try:
            await db.execute(f'DROP ROLE "{role}"')
        finally:
            await db.close()

    folder = root / ".artifacts/vin-journey"
    folder.mkdir(parents=True, exist_ok=True)
    asyncio.run(provision())
    try:
        selection = 'customer and http-link' if options.scenario == 'customer-runtime' else options.scenario
        result = pytest.main(["tests/vin_journey_browser_test.py", *(["-k", selection] if selection else []), "-q", "--tb=short", "-p", "no:cacheprovider", "-o", "faulthandler_timeout=45",
            f"--junitxml={folder / 'pytest.xml'}"])
        totals = ET.parse(folder / "pytest.xml").getroot().find("testsuite")
        summary = {key: int(totals.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")}
        summary.update(external_network_attempts=len(forbidden), paid_model_calls=0, model_mode="scripted")
        (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))
        return result or int(bool(forbidden) or summary["skipped"] != 0)
    finally:
        asyncio.run(cleanup())


if __name__ == "__main__":
    raise SystemExit(main())
