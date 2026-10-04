"""Provision the local dedicated PostgreSQL store and preserve existing SQLite state.

Run only with the Coordination process stopped. Business data is not modified.
The owner credential comes from the ignored local migration environment, never CLI args.
"""
import asyncio
import json
import secrets
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agent-coordination/src'))
from persistence.postgres import PostgreSQLStore

DATABASE = 'vinhomes_connected_coordination'
ROLE = 'vinhomes_connected_coordination'
TABLES = ('checkpoints', 'acknowledgements', 'inbox', 'ledger', 'records', 'cursors')


def env(path):
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8-sig').splitlines()
                if line and not line.startswith('#') and '=' in line)


def main():
    owner_url = env(ROOT / 'services/vinhomes-api/.local-connected/migration.env')['DATABASE_URL']
    address = urlsplit(owner_url)
    if address.hostname not in ('127.0.0.1', 'localhost') or address.path != '/vinhomes_connected':
        raise RuntimeError('Expected the local connected database owner configuration')
    config = ROOT / 'agent-coordination/.env'
    settings = env(config)
    known = settings.get('COORDINATION_DATABASE_URL')
    password = urlsplit(known).password if known else secrets.token_hex(24)
    cluster = urlunsplit(address._replace(path='/postgres'))
    from psycopg import sql
    with psycopg.connect(cluster, autocommit=True) as db:
        exists = db.execute('select 1 from pg_roles where rolname=%s', (ROLE,)).fetchone()
        if exists and not known:
            raise RuntimeError('Checkpoint role exists without matching local credentials')
        if not exists:
            db.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(ROLE), sql.Literal(password)))
        owner = db.execute('select pg_get_userbyid(datdba) from pg_database where datname=%s', (DATABASE,)).fetchone()
        if owner and owner[0] != ROLE:
            raise RuntimeError('Existing checkpoint database has an unexpected owner')
        if not owner:
            db.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(DATABASE), sql.Identifier(ROLE)))
            db.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(DATABASE)))
    target_url = urlunsplit((address.scheme, f'{ROLE}:{quote(password)}@{address.hostname}:{address.port}', '/' + DATABASE, '', ''))
    target = PostgreSQLStore(target_url)
    source = ROOT / 'agent-coordination/.coordination-state/connected.sqlite3'
    counts = {}
    if source.exists():
        artifact = ROOT / '.codex-artifacts'
        artifact.mkdir(exist_ok=True)
        backup = artifact / ('coordination-before-postgres-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
        with sqlite3.connect(source) as original, sqlite3.connect(backup) as saved:
            original.backup(saved)
        with sqlite3.connect(backup) as original, target.atomic() as dest:
            for table in TABLES:
                if not original.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone():
                    continue
                columns = [r[1] for r in original.execute(f'pragma table_info("{table}")')]
                rows = original.execute(f'select * from "{table}"').fetchall()
                if table == 'inbox':
                    # Preserve payloads/fences, but a stopped worker no longer owns leases.
                    rows = [tuple(None if columns[i] == 'owner' else 0 if columns[i] == 'expires' else value for i, value in enumerate(row)) for row in rows]
                occupied = dest.execute(f'select count(*) from "{table}"').fetchone()[0]
                if occupied:
                    raise RuntimeError('Target already contains state; import is one-time and never overwrites it')
                names = ','.join('"' + c + '"' for c in columns)
                placeholders = ','.join('?' for _ in columns)
                for row in rows:
                    dest.execute(f'insert into "{table}"({names}) values({placeholders})', row)
                counts[table] = len(rows)
    settings['COORDINATION_DATABASE_URL'] = target_url
    # Preserve comments and other settings rather than rewriting an unrelated environment.
    lines = config.read_text(encoding='utf-8-sig').splitlines()
    lines = [line for line in lines if not line.startswith('COORDINATION_DATABASE_URL=')]
    config.write_text('\n'.join(lines) + '\nCOORDINATION_DATABASE_URL=' + target_url + '\n', encoding='utf-8')
    print(json.dumps({'database': DATABASE, 'role': ROLE, 'preservedRows': counts}))


if __name__ == '__main__':
    main()
