"""Durable coordination state; never a ticket or approval authority."""
import json
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass

from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from groupchat.models import ScopeState
from supervisor.models import SupervisorState


def scope_key(context):
    return json.dumps(context.scope(), separators=(',', ':'))


@dataclass(frozen=True)
class Claim:
    key: str
    owner: str
    fence: int
    expires: float
    payload: dict
    recovery_attempts: int = 0


class DurableSQLStore:
    """Checkpoint, inbox fencing and quota semantics shared by the SQL stores.

    Each implementation supplies connection() and atomic(); no network I/O is
    awaited inside a transaction.
    """

    def __init__(self, *, clock=time.time):
        self.clock = clock
        self.active_claim = ContextVar("coordination_claim", default=None)

    @contextmanager
    def lease_scope(self, claim):
        token = self.active_claim.set(claim)
        try:
            yield
        finally:
            self.active_claim.reset(token)

    def _guard(self, db):
        claim = self.active_claim.get()
        if claim is not None:
            self._check_claim(db,claim)

    async def load(self, context):
        with self.connection() as db:
            self._guard(db)
            row = db.execute('SELECT body FROM checkpoints WHERE kind=? AND scope=?',
                             ('supervisor', scope_key(context))).fetchone()
        state = SupervisorState.model_validate_json(row[0]) if row else None
        if state and state.context != context:
            raise AdapterError('scope_mismatch')
        return state

    async def commit(self, state, expected_version, *, delivery_id=None):
        with self.atomic() as db:
            self._guard(db)
            key = scope_key(state.context)
            row = db.execute('SELECT version,body FROM checkpoints WHERE kind=? AND scope=?',
                             ('supervisor', key)).fetchone()
            if (row[0] if row else None) != expected_version:
                return False
            if row and SupervisorState.model_validate_json(row[1]).context != state.context:
                raise AdapterError('scope_mismatch')
            if state.version != (expected_version + 1 if row else 0):
                raise AdapterError('invalid_checkpoint_version')
            db.execute('INSERT INTO checkpoints(kind,scope,version,body) VALUES (?,?,?,?) ON CONFLICT(kind,scope) DO UPDATE SET version=excluded.version,body=excluded.body',
                       ('supervisor', key, state.version, state.model_dump_json()))
            if delivery_id:
                db.execute('INSERT INTO acknowledgements VALUES (?,?) ON CONFLICT(tenant,id) DO NOTHING',
                           (state.context.tenant_id, delivery_id))
        return True

    @asynccontextmanager
    async def transaction(self, context):
        # Consumer MUST NOT await network I/O inside this context. Room preparation
        # is outside this transaction. BEGIN IMMEDIATE serializes independent processes.
        with self.atomic() as db:
            self._guard(db)
            key = scope_key(context)
            row = db.execute('SELECT body FROM checkpoints WHERE kind=? AND scope=?', ('room',key)).fetchone()
            state = ScopeState.model_validate_json(row[0]) if row else ScopeState()
            if state.snapshot and not state.snapshot.scope.same_room_scope(context):
                raise AdapterError('scope_mismatch')
            yield state
            self._guard(db)
            db.execute('INSERT INTO checkpoints(kind,scope,version,body) VALUES (?,?,?,?) ON CONFLICT(kind,scope) DO UPDATE SET version=excluded.version,body=excluded.body',
                       ('room',key,state.fence,state.model_dump_json()))

    async def accept(self, key, payload):
        digest = fingerprint(payload)
        with self.atomic() as db:
            self._guard(db)
            old = db.execute('SELECT digest FROM inbox WHERE key=?', (key,)).fetchone()
            if old:
                if old[0] != digest:
                    raise AdapterError('conflict')
                return False
            db.execute('INSERT INTO inbox(key,digest,body) VALUES (?,?,?)',
                       (key,digest,json.dumps(payload, ensure_ascii=False, allow_nan=False)))
        return True

    async def enqueue_once(self, delivery):
        return await self.accept(json.dumps((delivery.tenant_id, delivery.event_id)), asdict(delivery))

    async def claim(self, owner, seconds=30):
        if not owner or not 0 < seconds <= 300:
            raise ValueError('invalid lease')
        now = self.clock()
        with self.atomic() as db:
            row = db.execute("SELECT key,body,fence,owner FROM inbox WHERE status='pending' AND expires<=? ORDER BY rowid LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            key, body, fence, previous_owner = row
            recovery = db.execute("SELECT body FROM records WHERE namespace='inbox_recovery_count' AND key=?", (key,)).fetchone()
            recovery_attempts = json.loads(recovery[0]) if recovery else 0
            if previous_owner is not None:
                # An expired owner abandoned an attempt, unlike a normal yield.
                recovery_attempts += 1
                db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET body=excluded.body',
                           ('inbox_recovery_count',key,json.dumps(recovery_attempts)))
            fence += 1
            db.execute('UPDATE inbox SET owner=?,fence=?,expires=? WHERE key=?', (owner,fence,now+seconds,key))
        return Claim(key,owner,fence,now+seconds,json.loads(body),recovery_attempts)

    def _check_claim(self, db, claim):
        row = db.execute('SELECT owner,fence,expires,status FROM inbox WHERE key=?', (claim.key,)).fetchone()
        if not row or row[:2] != (claim.owner,claim.fence) or row[2] <= self.clock() or row[3] != 'pending':
            raise AdapterError('stale_fence')

    async def ack(self, claim):
        with self.atomic() as db:
            self._check_claim(db,claim)
            if claim.payload.get('kind') == 'event':
                delivery=claim.payload['delivery']
                db.execute('INSERT INTO acknowledgements VALUES (?,?) ON CONFLICT(tenant,id) DO NOTHING',
                           (delivery['tenant_id'],delivery['event_id']))
            db.execute("UPDATE inbox SET status='done' WHERE key=?", (claim.key,))

    async def renew(self, claim, seconds=30):
        if not 0 < seconds <= 300: raise ValueError('invalid lease')
        with self.atomic() as db:
            self._check_claim(db,claim)
            db.execute('UPDATE inbox SET expires=? WHERE key=?',(self.clock()+seconds,claim.key))

    async def release(self, claim):
        with self.atomic() as db:
            self._check_claim(db,claim)
            db.execute('UPDATE inbox SET expires=0,owner=NULL WHERE key=?', (claim.key,))

    async def defer(self, claim, seconds, *, recovery=False):
        if not 0 < seconds <= 300: raise ValueError('invalid retry delay')
        with self.atomic() as db:
            self._check_claim(db,claim)
            if recovery:
                db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET body=excluded.body',
                           ('inbox_recovery_count',claim.key,json.dumps(claim.recovery_attempts+1)))
            db.execute('UPDATE inbox SET expires=?,owner=NULL WHERE key=?',(self.clock()+seconds,claim.key))

    async def park(self, claim, reason="recovery_unconfirmed"):
        # Preserve unknown/manual recovery input, never label it successfully ACKed.
        with self.atomic() as db:
            self._check_claim(db,claim)
            attempts = claim.recovery_attempts+1
            db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET body=excluded.body',
                       ('inbox_recovery_count',claim.key,json.dumps(attempts)))
            details={'reason':reason,'fence':claim.fence,'recovery_attempts':attempts,'kind':claim.payload.get('kind'),
                     'input_id':claim.payload.get('wire',{}).get('message_id',claim.payload.get('wire',{}).get('event_id'))}
            db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET body=excluded.body',
                       ('recovery_blocked',claim.key,json.dumps(details,sort_keys=True)))
            db.execute("UPDATE inbox SET status='blocked',owner=NULL WHERE key=?",(claim.key,))

    async def put_once(self, namespace, key, value):
        body = json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)
        with self.atomic() as db:
            self._guard(db)
            old = db.execute('SELECT body FROM records WHERE namespace=? AND key=?', (namespace,key)).fetchone()
            if old and old[0] != body:
                raise AdapterError('conflict')
            db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(namespace,key) DO NOTHING', (namespace,key,body))
            return old is None

    async def get(self, namespace, key):
        with self.connection() as db:
            row = db.execute('SELECT body FROM records WHERE namespace=? AND key=?', (namespace,key)).fetchone()
        return json.loads(row[0]) if row else None
