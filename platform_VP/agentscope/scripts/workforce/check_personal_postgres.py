"""Run the real personal-chat SQL concurrency gate in a fresh disposable DB.

No .env is loaded. Only the explicit loopback PostgreSQL server is reachable;
all credentials inherited from the shell are removed before importing the app.
The runner creates and drops only its own randomly named database.
"""

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
    parser.add_argument("--admin-url", required=True, help="Disposable loopback PostgreSQL admin URL; never an application DSN")
    options = parser.parse_args()
    parsed = urlsplit(options.admin_url)
    if parsed.scheme != "postgresql" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.query:
        parser.error("Only an explicit loopback postgresql:// fixture URL without query parameters is allowed")
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    for path in (root, root / "tests", root / "src"):
        sys.path.insert(0, str(path))
    for name in list(os.environ):
        if name != "TIKTOKEN_CACHE_DIR" and (
            any(part in name for part in ("API_KEY", "TOKEN", "SECRET"))
            or name.endswith(("_DATABASE_URL", "_POSTGRES_URL", "_ADMIN_URL"))
        ):
            os.environ.pop(name, None)
    os.environ["VIN_PLATFORM_ENABLED"] = "false"
    os.environ["VIN_AUTH_ENABLED"] = "false"
    database = "vin_n2_concurrency_" + uuid4().hex
    os.environ["GROUP_TEST_POSTGRES_URL"] = urlunsplit(parsed._replace(scheme="postgresql+asyncpg", path="/" + database))
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo
    forbidden = []

    def deny(*args, **kwargs):
        forbidden.append(1)
        raise RuntimeError("OFFLINE_TEST: only the explicit disposable PostgreSQL port is allowed")

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"} and address[1] == (parsed.port or 5432):
            return original_connect(sock, address)
        return deny()

    def resolve(host, *args, **kwargs):
        if host not in {"localhost", "127.0.0.1", "::1", None}:
            return deny()
        return original_getaddrinfo(host, *args, **kwargs)

    if sys.platform == "win32":
        def local_socketpair(*args, **kwargs):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                original_connect(client, listener.getsockname())
                server, _ = listener.accept()
            return server, client
        socket.socketpair = local_socketpair
    socket.socket.connect = connect
    socket.socket.connect_ex = deny
    socket.getaddrinfo = resolve
    socket.socket.sendto = deny

    import asyncpg
    import pytest

    created = False

    async def provision():
        nonlocal created
        control = await asyncpg.connect(options.admin_url)
        try:
            await control.execute('CREATE DATABASE "' + database + '"')
            created = True
        finally:
            await control.close()
        fixture = await asyncpg.connect(urlunsplit(parsed._replace(path="/" + database)))
        try:
            await fixture.execute("CREATE EXTENSION IF NOT EXISTS vector")
        finally:
            await fixture.close()

    async def cleanup():
        assert database.startswith("vin_n2_concurrency_") and len(database) == 51
        control = await asyncpg.connect(options.admin_url)
        try:
            await control.execute('DROP DATABASE "' + database + '" WITH (FORCE)')
        finally:
            await control.close()

    output = root / ".artifacts" / "personal-postgres"
    output.mkdir(parents=True, exist_ok=True)
    # A newly generated name cannot identify an existing application database.
    try:
        asyncio.run(provision())
        result = pytest.main([
            "tests/personal_chat_test.py::test_group_runs_real_agents_and_dispatcher_with_deterministic_provider[sql]",
            "-q", "--tb=short", "-p", "no:cacheprovider", f"--junitxml={output / 'pytest.xml'}",
        ])
        totals = ET.parse(output / "pytest.xml").getroot().find("testsuite")
        summary = {key: int(totals.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")}
        summary.update(external_network_attempts=len(forbidden), paid_model_calls=0, model_mode="scripted",
            database="fresh_disposable_postgresql", python=sys.version.split()[0])
        (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))
        return result or int(bool(forbidden) or summary["skipped"] != 0 or summary["tests"] != 1)
    finally:
        if created:
            asyncio.run(cleanup())


if __name__ == "__main__":
    raise SystemExit(main())
