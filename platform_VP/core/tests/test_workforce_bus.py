"""Prove SDK Redis delivery between independent processes, using only the test Redis DB."""
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

pytestmark = pytest.mark.skipif(os.getenv("AWP_TEST_INFRA") != "1", reason="Requires isolated Redis")


def test_two_processes_initialize_fresh_postgres_schema(tmp_path):
    import asyncpg
    local = dict(line.split("=", 1) for line in (Path(__file__).parents[1] / ".env").read_text().splitlines()
                 if line and not line.startswith("#"))
    name = "awp_test_" + uuid.uuid4().hex[:12]
    script = """
import asyncio, os
from awp.app import build_app
from awp.config import Settings
async def run():
    url = os.environ['AWP_TEST_BOOTSTRAP_URL']
    app = build_app(Settings(db_url=url, agentscope_db_url=url, workforce_workers=0,
        workspace_dir=os.environ['AWP_TEST_BOOTSTRAP_WORKSPACE'], redis_url='redis://127.0.0.1:6389/15'))
    async with app.router.lifespan_context(app):
        print('BOOTSTRAPPED', flush=True)
        await asyncio.sleep(.1)
asyncio.run(run())
"""
    async def run():
        db = await asyncpg.connect(host="127.0.0.1", port=5589, user="awp", database="awp", password=local["AWP_POSTGRES_PASSWORD"])
        assert name.startswith("awp_test_") and name[9:].isalnum()
        await db.execute(f'CREATE DATABASE "{name}"')
        try:
            env = {**os.environ, "AWP_TEST_BOOTSTRAP_URL": "postgresql+asyncpg://awp:" + quote(local["AWP_POSTGRES_PASSWORD"], safe="") + f"@127.0.0.1:5589/{name}"}
            processes = []
            for i in range(2):
                processes.append(await asyncio.create_subprocess_exec(sys.executable, "-c", script,
                    env={**env, "AWP_TEST_BOOTSTRAP_WORKSPACE": str(tmp_path / str(i))},
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
            results = await asyncio.gather(*(process.communicate() for process in processes))
            for process, (stdout, stderr) in zip(processes, results, strict=True):
                assert process.returncode == 0, stderr.decode()
                assert b"BOOTSTRAPPED" in stdout
        finally:
            await db.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
            await db.close()
    asyncio.run(run())


def test_cross_process_queue_drains_once():
    from agentscope.app.message_bus import RedisMessageBus

    script = """
import asyncio, json, sys, time
from agentscope.app.message_bus import RedisMessageBus
async def run():
    async with RedisMessageBus(host='127.0.0.1', port=6389, db=15) as bus:
        while time.time() < float(sys.argv[2]):
            await asyncio.sleep(.02)
        items = []
        while batch := await bus.queue_drain(sys.argv[1], max_count=1):
            items.extend(payload['index'] for _, payload in batch)
            await asyncio.sleep(.001)
        print(json.dumps(items))
asyncio.run(run())
"""
    async def run():
        key = "awp:test:cross-process:" + uuid.uuid4().hex
        async with RedisMessageBus(host="127.0.0.1", port=6389, db=15) as bus:
            for index in range(200):
                await bus.queue_push(key, {"index": index}, ttl_secs=60)
            start = str(time.time() + 8)
            processes = [await asyncio.create_subprocess_exec(sys.executable, "-c", script, key, start,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE) for _ in range(2)]
            results = await asyncio.gather(*(process.communicate() for process in processes))
            values = []
            for process, (stdout, stderr) in zip(processes, results, strict=True):
                assert process.returncode == 0, stderr.decode()
                consumed = json.loads(stdout)
                assert consumed  # Both separate processes participated.
                values.extend(consumed)
            assert sorted(values) == list(range(200))
            assert await bus.queue_drain(key) == []
            await bus.queue_delete(key)
    asyncio.run(run())
