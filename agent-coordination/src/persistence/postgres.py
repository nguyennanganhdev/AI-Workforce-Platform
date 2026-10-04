"""PostgreSQL coordination state, in a dedicated database with an application-owned schema.

Short transactions share one advisory lock, matching SQLite's serialized writes.
This keeps CAS, lease fences and tenant budgets atomic across runtime processes.
The database must be provisioned separately; the runtime never creates databases
and never falls back to a file if PostgreSQL is unavailable.
"""
import time
from contextlib import contextmanager

import psycopg

from .sql import DurableSQLStore


class _Connection:
    """The shared store uses DB-API qmark parameters; psycopg uses format parameters."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=None):
        return self.connection.execute(query.replace('?', '%s'), parameters)


class PostgreSQLStore(DurableSQLStore):
    def __init__(self, url, *, clock=time.time):
        super().__init__(clock=clock)
        if not url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('COORDINATION_DATABASE_URL must be a PostgreSQL connection URL')
        self.url = url
        with self.atomic() as db:
            for statement in (
                "CREATE SCHEMA IF NOT EXISTS coordination",
                """CREATE TABLE IF NOT EXISTS checkpoints (
                    rowid BIGINT GENERATED ALWAYS AS IDENTITY, kind TEXT NOT NULL, scope TEXT NOT NULL,
                    version INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(kind,scope))""",
                "CREATE TABLE IF NOT EXISTS acknowledgements (tenant TEXT, id TEXT, PRIMARY KEY(tenant,id))",
                """CREATE TABLE IF NOT EXISTS inbox (
                    rowid BIGINT GENERATED ALWAYS AS IDENTITY, key TEXT PRIMARY KEY, digest TEXT NOT NULL,
                    body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', owner TEXT,
                    fence BIGINT NOT NULL DEFAULT 0, expires DOUBLE PRECISION NOT NULL DEFAULT 0)""",
                """CREATE TABLE IF NOT EXISTS ledger (scope TEXT, id TEXT, bound BIGINT NOT NULL,
                    used BIGINT, cost TEXT, status TEXT NOT NULL, PRIMARY KEY(scope,id))""",
                "CREATE TABLE IF NOT EXISTS records (namespace TEXT, key TEXT, body TEXT NOT NULL, PRIMARY KEY(namespace,key))",
                "CREATE TABLE IF NOT EXISTS cursors (name TEXT PRIMARY KEY, value TEXT NOT NULL)",
            ):
                db.execute(statement)

    @contextmanager
    def connection(self):
        with psycopg.connect(self.url, autocommit=True, connect_timeout=5,
                             options='-c search_path=coordination -c statement_timeout=5000') as connection:
            yield _Connection(connection)

    @contextmanager
    def atomic(self):
        with self.connection() as db:
            with db.connection.transaction():
                db.execute("SELECT pg_advisory_xact_lock(1846074300)")
                yield db

    def cursor(self):
        with self.connection() as db:
            row = db.execute("SELECT value FROM cursors WHERE name='inbox'").fetchone()
        return row[0] if row else None

    def save_cursor(self, value):
        with self.atomic() as db:
            db.execute("INSERT INTO cursors VALUES ('inbox',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (value,))

    def sessions(self):
        # Same operator projection as the development runtime, without resident text.
        from supervisor.models import SupervisorState
        with self.connection() as db:
            rows = db.execute("SELECT body FROM checkpoints WHERE kind='supervisor' ORDER BY rowid").fetchall()
            blocked = db.execute("SELECT COUNT(*) FROM inbox WHERE status='blocked'").fetchone()[0]
        items = []
        for (body,) in rows:
            state = SupervisorState.model_validate_json(body)
            items.append({"ticket_id": state.context.ticket_id, "ticket_generation": state.context.ticket_generation,
                          "ticket_code": state.reception.ticket_code if state.reception else None,
                          "run_id": state.supervisor_run_id, "phase": state.phase, "pause_reason": state.pause_reason,
                          "checkpoint_version": state.version, "actions_done": [a.operation for a in state.journal],
                          "action_in_flight": state.action.status if state.action else None})
        return [{"blocked_inbox_items": blocked}, *items] if blocked else items
