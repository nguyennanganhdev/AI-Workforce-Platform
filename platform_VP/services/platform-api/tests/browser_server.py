"""Isolated browser acceptance server. Real API/SDK/DB, fixture provider I/O only.

Run from platform-api: uv run python tests/browser_server.py
Never imported by production vp.worker. Only listens on loopback port 8099.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[3]
test_path = root / ".local" / "ui-acceptance.db"
test_path.parent.mkdir(exist_ok=True)
os.environ.update(
    {
        "VP_DATABASE_URL": f"sqlite+aiosqlite:///{test_path.as_posix()}",
        "VP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "VP_BOOTSTRAP_EMAIL": "browser@test.local",
        "VP_BOOTSTRAP_PASSWORD": "Ui-acceptance-only-123!",
        "VP_COOKIE_SECURE": "false",
        "VP_ALLOW_PRIVATE_ENDPOINTS": "true",
        "VP_TRUSTED_ORIGINS": "http://127.0.0.1:3081",
        "VP_REDIS_URL": "",
    }
)

import uvicorn
from test_runtime import FixtureModel

from vp import db, runtime
from vp.api import app, lifespan
from vp.knowledge import execute_index
from vp.queue import worker_loop

runtime.create_model = lambda *args: FixtureModel()


@asynccontextmanager
async def test_lifespan(app):
    async with db.engine.begin() as conn:
        await conn.run_sync(db.Base.metadata.drop_all)
    async with lifespan(app):
        stop = asyncio.Event()
        workers = [
            asyncio.create_task(worker_loop(0, stop, runtime.execute_agent)),
            asyncio.create_task(worker_loop(1, stop, execute_index, "index")),
        ]
        try:
            yield
        finally:
            stop.set()
            await asyncio.gather(*workers)


app.router.lifespan_context = test_lifespan
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099, access_log=False)
