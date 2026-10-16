"""Which database the tests run on.

By default every test gets SQLite files in its temporary directory. With `AWP_TEST_PG_URL` set to a PostgreSQL server
(`postgresql://awp:awp@127.0.0.1:55432/postgres`: a user that may create databases) the same tests run on that server
instead: the first use builds two template databases (the awp tables, and AgentScope's storage tables), and a test that
asks for a database gets a fresh copy of each (`CREATE DATABASE ... TEMPLATE`, a few tens of milliseconds), dropped when
the test is over. Nothing else on the server is touched; the databases are named `awpt_*`.

`urls(key)` returns the pair of URLs for a key (a test's tmp_path): asking twice with the same key gives the same
databases, which is how a test "restarts" the platform on the data it had. `connect(db)` is a bare synchronous
connection to one of them for tests that read or write rows behind the platform's back; its SQL is the portable subset
(`?` placeholders, plain statements) and its integrity errors are `IntegrityError` on both.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PG_URL = os.environ.get("AWP_TEST_PG_URL", "").strip()
IS_PG = bool(PG_URL)

try:  # PostgreSQL's integrity errors, only when its driver is there
    from asyncpg import exceptions as _pgx
    IntegrityError: tuple = (sqlite3.IntegrityError, _pgx.IntegrityConstraintViolationError)
except ImportError:  # pragma: no cover
    _pgx = None
    IntegrityError = (sqlite3.IntegrityError,)


@dataclass(frozen=True)
class Db:
    """One database of a test: the SQLAlchemy URL, and for SQLite the file (a test may open the file itself)."""
    url: str
    path: str | None = None


# ---- a private event loop for everything synchronous that talks to PostgreSQL -----------------------------------
class _Loop:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="dbtest-loop").start()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()


_loop: _Loop | None = None


def _bg() -> _Loop:
    global _loop
    if _loop is None:
        _loop = _Loop()
    return _loop


def _parts() -> tuple[str, int, str, str]:
    u = urlsplit(PG_URL)
    return u.hostname or "127.0.0.1", u.port or 5432, u.username or "postgres", u.password or ""


def _dsn(database: str) -> str:
    host, port, user, password = _parts()
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _sa_url(database: str) -> str:
    host, port, user, password = _parts()
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def _admin(*statements: str) -> None:
    import asyncpg
    conn = await asyncpg.connect(_dsn(urlsplit(PG_URL).path.lstrip("/") or "postgres"))
    try:
        for s in statements:
            await conn.execute(s)
    finally:
        await conn.close()


async def _names(prefix: str) -> list[str]:
    import asyncpg
    conn = await asyncpg.connect(_dsn(urlsplit(PG_URL).path.lstrip("/") or "postgres"))
    try:
        return [r[0] for r in await conn.fetch("select datname from pg_database where datname like $1", prefix + "%")]
    finally:
        await conn.close()


# ---- the templates and the databases cloned from them ------------------------------------------------------------
_TPL = ("awpt_tpl_awp", "awpt_tpl_as")
_ready = False
_made: dict[str, tuple[str, str]] = {}  # key -> the two database names
_lock = threading.Lock()


async def _fill_templates() -> None:
    from agentscope.app.storage import AsyncSQLAlchemyStorage

    from awp.db import Database

    db = Database(_sa_url(_TPL[0]))
    await db.create_all()
    await db.dispose()
    storage = AsyncSQLAlchemyStorage(_sa_url(_TPL[1]))
    await storage.__aenter__()
    await storage.aclose()


def _prepare() -> None:
    global _ready
    with _lock:
        if _ready:
            return
        old = _bg().run(_names("awpt_"))
        _bg().run(_admin(*[f'drop database if exists "{n}" with (force)' for n in old]))
        _bg().run(_admin(*[f'create database "{n}"' for n in _TPL]))
        _bg().run(_fill_templates())
        _ready = True


def _name(key: Path | str) -> str:
    return "awpt_" + hashlib.md5(str(key).encode()).hexdigest()[:12]


def urls(key: Path | str) -> tuple[Db, Db]:
    """The awp database and the AgentScope storage database of `key`: files on SQLite, fresh clones on PostgreSQL."""
    if not IS_PG:
        base = Path(key)
        return (Db(f"sqlite+aiosqlite:///{(base / 'awp.db').as_posix()}", str(base / "awp.db")),
                Db(f"sqlite+aiosqlite:///{(base / 'as.db').as_posix()}", str(base / "as.db")))
    _prepare()
    with _lock:
        if str(key) not in _made:
            a, s = _name(key) + "_a", _name(key) + "_s"
            _bg().run(_admin(f'create database "{a}" template "{_TPL[0]}"', f'create database "{s}" template "{_TPL[1]}"'))
            _made[str(key)] = (a, s)
        a, s = _made[str(key)]
    return Db(_sa_url(a)), Db(_sa_url(s))


def one(key: Path | str, name: str = "x.db") -> Db:
    """A single database for a unit test that wants only the awp tables (`name` is the SQLite file)."""
    if not IS_PG:
        return Db(f"sqlite+aiosqlite:///{(Path(key) / name).as_posix()}", str(Path(key) / name))
    return urls(f"{key}/{name}")[0]


def empty(key: Path | str, name: str = "m.db") -> Db:
    """A database with no tables at all (for migrations), under a key the cleanup of the test covers."""
    if not IS_PG:
        return Db(f"sqlite+aiosqlite:///{(Path(key) / name).as_posix()}", str(Path(key) / name))
    _prepare()
    full = f"{key}/{name}"
    with _lock:
        if full not in _made:
            n = _name(full)
            _bg().run(_admin(f'create database "{n}_a"'))
            _made[full] = (n + "_a",)
        return Db(_sa_url(_made[full][0]))


def drop(prefix: str | None = None) -> None:
    """Drop the databases made for keys that start with `prefix` (all of them when None)."""
    if not IS_PG:
        return
    with _lock:
        gone = [k for k in _made if prefix is None or k.startswith(prefix)]
        names = [n for k in gone for n in _made.pop(k)]
    if names:
        _bg().run(_admin(*[f'drop database if exists "{n}" with (force)' for n in names]))


def drop_all() -> None:
    if not IS_PG:
        return
    drop()
    if _ready:
        _bg().run(_admin(*[f'drop database if exists "{n}" with (force)' for n in _TPL]))


# ---- bare synchronous connections ---------------------------------------------------------------------------------
def _numbered(query: str) -> str:
    """`?` placeholders to `$1, $2...` (a `?` inside a quoted literal is text)."""
    out, n, quoted = [], 0, False
    for ch in query:
        if ch == "'":
            quoted = not quoted
        if ch == "?" and not quoted:
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
    return "".join(out)


class _SqliteConn:
    def __init__(self, path: str) -> None:
        self.con = sqlite3.connect(path, timeout=30, isolation_level=None)  # every statement commits at once

    def execute(self, query: str, args: Any = ()) -> list[tuple]:
        return self.con.execute(query, list(args)).fetchall()

    def executemany(self, query: str, rows: list) -> None:
        self.con.executemany(query, rows)

    def tables(self) -> set[str]:
        return {r[0] for r in self.execute("select name from sqlite_master where type='table'")}

    def columns(self, table: str) -> set[str]:
        return {r[1] for r in self.execute(f"pragma table_info({table})")}

    def close(self) -> None:
        self.con.close()


class _PgConn:
    def __init__(self, url: str) -> None:
        import asyncpg
        self.lock = threading.Lock()
        self.con = _bg().run(asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://")))

    def execute(self, query: str, args: Any = ()) -> list[tuple]:
        q = _numbered(query)
        with self.lock:
            if query.lstrip().lower().startswith(("select", "with")) or " returning " in query.lower():
                return [tuple(r) for r in _bg().run(self.con.fetch(q, *args))]
            _bg().run(self.con.execute(q, *args))
            return []

    def executemany(self, query: str, rows: list) -> None:
        with self.lock:
            _bg().run(self.con.executemany(_numbered(query), rows))

    def tables(self) -> set[str]:
        return {r[0] for r in self.execute("select table_name from information_schema.tables where table_schema='public'")}

    def columns(self, table: str) -> set[str]:
        return {r[0] for r in self.execute("select column_name from information_schema.columns where table_name = ?",
                                           (table,))}

    def close(self) -> None:
        with self.lock:
            _bg().run(self.con.close())


def connect(db: Db):
    """A bare connection: `execute(query, args) -> rows`, `executemany`, `tables()`, `columns(table)`, `close()`."""
    return _PgConn(db.url) if IS_PG else _SqliteConn(db.path)


def dump(db: Db) -> str:
    """Every row of every table as text, for tests that look for a secret anywhere in the database."""
    if not IS_PG:
        con = sqlite3.connect(db.path)
        try:
            return "\n".join(con.iterdump())
        finally:
            con.close()
    con = _PgConn(db.url)
    try:
        out = []
        for name in sorted(con.tables()):
            out.extend(repr(row) for row in con.execute(f'select * from "{name}"'))
        return "\n".join(out)
    finally:
        con.close()
