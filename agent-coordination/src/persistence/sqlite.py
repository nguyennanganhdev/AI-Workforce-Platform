"""SQLite storage for isolated development; never a production fallback."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .sql import Claim, DurableSQLStore, scope_key

class DevelopmentStore(DurableSQLStore):
    def __init__(self, path, *, mode='development', clock=time.time):
        if mode != 'development' or str(path) == ':memory:':
            raise ValueError('isolated development framework file storage required')
        super().__init__(clock=clock)
        self.path = str(Path(path))
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS checkpoints (kind TEXT, scope TEXT, version INTEGER,
                body TEXT NOT NULL, PRIMARY KEY(kind,scope));
            CREATE TABLE IF NOT EXISTS acknowledgements (tenant TEXT, id TEXT, PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS inbox (key TEXT PRIMARY KEY, digest TEXT NOT NULL,
                body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', owner TEXT,
                fence INTEGER NOT NULL DEFAULT 0, expires REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ledger (scope TEXT, id TEXT, bound INTEGER NOT NULL,
                used INTEGER, cost TEXT, status TEXT NOT NULL, PRIMARY KEY(scope,id));
            CREATE TABLE IF NOT EXISTS records (namespace TEXT, key TEXT, body TEXT NOT NULL,
                PRIMARY KEY(namespace,key));
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def atomic(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
