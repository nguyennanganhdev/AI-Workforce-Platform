"""Ordered PostgreSQL migrations; applied files cannot be silently rewritten."""
import hashlib
import time
from pathlib import Path

from sqlalchemy import insert, select

from . import schema as s


async def migrate(conn):
    await conn.run_sync(s.versions.create, checkfirst=True)
    files = sorted((Path(__file__).parent / "migrations").glob("*.sql"))
    if not files:
        raise RuntimeError("Workforce migrations are missing from the installation")
    applied = dict((await conn.execute(select(s.versions.c.id, s.versions.c.checksum))).all())
    known = {f.stem for f in files}
    if set(applied) - known:
        raise RuntimeError("Database schema is newer than this application")
    for path in files:
        raw = path.read_text(encoding="utf-8").encode("utf-8")
        checksum = hashlib.sha256(raw).hexdigest()
        if path.stem in applied:
            if applied[path.stem] != checksum:
                raise RuntimeError(f"Applied migration checksum changed: {path.name}")
            continue
        if conn.dialect.name == "postgresql":
            for statement in raw.decode("utf-8").split(";\n"):
                if statement.strip():
                    await conn.exec_driver_sql(statement)
        else:
            await conn.run_sync(lambda sync: s.metadata.create_all(sync, tables=[t for t in s.metadata.sorted_tables
                if t.name.startswith("awp_wf_")]))
        await conn.execute(insert(s.versions).values(id=path.stem, checksum=checksum, applied=time.time()))
