"""Back up both databases + bucket + settings; verify restoration to fresh databases and bucket.

Run with the application writers stopped. Restore verification never replaces the source.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from minio import Minio

ROOT = Path('/backups')


def pg(url, tool, *args, output=None):
    parts = urlsplit(url.replace('postgresql+asyncpg://', 'postgresql://'))
    env = {**os.environ, 'PGHOST': parts.hostname, 'PGPORT': str(parts.port or 5432),
           'PGUSER': unquote(parts.username or ''), 'PGPASSWORD': unquote(parts.password or ''),
           'PGDATABASE': parts.path.lstrip('/')}
    result = subprocess.run([tool, *args], env=env, stdout=output or subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        # pg_restore/psql may echo statements. Keep credentials and stored settings out of logs.
        raise RuntimeError(f'{tool} failed with exit {result.returncode}; backup/restore did not complete')
    return result.stdout.decode() if output is None else ''


def db_url(url, name):
    parts = urlsplit(url)
    return parts._replace(path='/' + name).geturl()


def counts(url):
    names = [line.split('|') for line in pg(url, 'psql', '-XAt', '-c', "select schemaname,tablename from pg_tables where schemaname not like 'pg_%' and schemaname <> 'information_schema' order by schemaname,tablename").splitlines()]
    if any(not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', part) for name in names for part in name):
        raise RuntimeError('Unexpected table name')
    if not names:
        return {}
    query = ' union all '.join(f"select '{schema}.{name}',count(*) from \"{schema}\".\"{name}\"" for schema, name in names)
    return dict(line.split('|') for line in pg(url, 'psql', '-XAt', '-c', query).splitlines())


def store():
    parts = urlsplit(os.environ['S3_ENDPOINT'])
    return Minio(parts.netloc, access_key=os.environ['S3_ADMIN_ACCESS_KEY'],
                 secret_key=os.environ['S3_ADMIN_SECRET_KEY'], secure=parts.scheme == 'https')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup():
    ROOT.mkdir(exist_ok=True)
    target = ROOT / datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    target.mkdir()
    manifest = {'databases': {}, 'objects': [], 'bucket': os.getenv('S3_BUCKET', 'vinhomes-files')}
    for name, variable in [('business', 'MIGRATION_DATABASE_URL'), ('coordination', 'COORDINATION_DATABASE_URL')]:
        url = os.environ[variable]
        destination = target / (name + '.dump')
        pg(url, 'pg_dump', '-Fc', '-f', str(destination))
        manifest['databases'][name] = {'sha256': sha(destination), 'counts': counts(url)}
    client = store()
    objects = target / 'objects'
    objects.mkdir()
    for index, obj in enumerate(client.list_objects(manifest['bucket'], recursive=True)):
        destination = objects / str(index)
        client.fget_object(manifest['bucket'], obj.object_name, str(destination))
        manifest['objects'].append({'key': obj.object_name, 'file': str(index), 'size': destination.stat().st_size, 'sha256': sha(destination)})
    shutil.copyfile('/config/deployment.env', target / 'deployment.env')
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (ROOT / 'latest').write_text(target.name)
    print(json.dumps({'type': 'backup-complete', 'directory': target.name, 'objects': len(manifest['objects']),
                      'tables': {name: len(value['counts']) for name, value in manifest['databases'].items()}}))


def verify():
    name = (ROOT / 'latest').read_text().strip()
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z', name):
        raise RuntimeError('Invalid backup name')
    target = ROOT / name
    manifest = json.loads((target / 'manifest.json').read_text())
    admin = os.environ['RESTORE_ADMIN_DATABASE_URL']
    suffix = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
    restored = []
    for kind, expected in manifest['databases'].items():
        if kind not in ('business', 'coordination'):
            raise RuntimeError('Unexpected backup database')
        dump = target / (kind + '.dump')
        if sha(dump) != expected['sha256']:
            raise RuntimeError('Database backup checksum mismatch')
        database = 'vinhomes_restore_' + kind + '_' + suffix
        pg(admin, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-c', f'CREATE DATABASE "{database}"')
        url = db_url(admin, database)
        pg(url, 'pg_restore', '--no-owner', '--no-acl', '--exit-on-error', '-d', database, str(dump))
        if counts(url) != expected['counts']:
            raise RuntimeError(f'Restored {kind} row counts differ')
        restored.append(database)
    client = store()
    bucket = 'vinhomes-restore-' + suffix
    client.make_bucket(bucket)
    for obj in manifest['objects']:
        path = target / 'objects' / obj['file']
        if path.parent != target / 'objects' or sha(path) != obj['sha256']:
            raise RuntimeError('Object backup checksum mismatch')
        client.fput_object(bucket, obj['key'], str(path))
        response = client.get_object(bucket, obj['key'])
        try:
            actual = hashlib.sha256(response.read()).hexdigest()
        finally:
            response.close()
            response.release_conn()
        if actual != obj['sha256']:
            raise RuntimeError('Restored object checksum mismatch')
    print(json.dumps({'type': 'restore-verified', 'databases': restored, 'bucket': bucket, 'objects': len(manifest['objects'])}))


if __name__ == '__main__':
    try:
        {'backup': backup, 'restore-verify': verify}[sys.argv[1] if len(sys.argv) > 1 else 'backup']()
    except Exception as error:
        print(json.dumps({'type': 'backup-error', 'error': str(error)}), file=sys.stderr)
        raise SystemExit(1)
