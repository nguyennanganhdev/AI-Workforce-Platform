"""Run canonical HTTP business E2E on a fresh local database, without Agent/model/partner calls.

Requires RESIDENT_TEST_ADMIN_URL and RESIDENT_TEST_RUNTIME_URL (restricted role already created).
Creates and drops only its generated maintain_flow_test_* database.
"""
import asyncio
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import httpx
from vinhomes_api import database


async def main():
    owner=os.environ['RESIDENT_TEST_ADMIN_URL']
    runtime=os.environ['RESIDENT_TEST_RUNTIME_URL']
    for url in (owner,runtime):
        if urlsplit(url.replace('postgresql+asyncpg:','postgresql:')).hostname not in {'127.0.0.1','localhost','::1'}:
            raise RuntimeError('HTTP business E2E requires local test PostgreSQL')
    name='maintain_flow_test_'+uuid4().hex
    def url_for(value):return urlunsplit(urlsplit(value)._replace(path='/'+name))
    service=Path(__file__).resolve().parents[1]
    process=None
    created=False
    with tempfile.TemporaryDirectory(prefix='vinhomes-business-') as directory:
        try:
            await database.create(owner,name);created=True
            await database.migrate(url_for(owner))
            await database.seed(url_for(owner))
            await database.role(url_for(owner),urlsplit(runtime).username,None)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={**os.environ,'VINHOMES_API_DATABASE_URL':url_for(runtime).replace('postgresql:','postgresql+asyncpg:'),
                 'VINHOMES_API_HOST':'127.0.0.1','VINHOMES_API_PORT':str(port),
                 'VINHOMES_API_TENANT_ID':'11111111-1111-5111-a111-111111111111',
                 'VINHOMES_API_DEMO_MODE':'1','VINHOMES_API_PASSWORD_AUTH':'0','VINHOMES_API_DEV_USER_ID':'',
                 'VINHOMES_API_VOLUME_FILE_STORAGE':'1','VINHOMES_RESIDENT_FILE_ROOT':directory,
                 'VINHOMES_API_RECEPTION_URL':'','VINHOMES_API_PLATFORM_URL':'','VINHOMES_API_PLATFORM_MCP_TOKEN':'',
                 'VINHOMES_API_S3_ENDPOINT':'','VINHOMES_API_EMBEDDING_API_KEY':'','VINHOMES_SMTP_HOST':''}
            with open(Path(directory)/'api.log','wb') as log:
                process=subprocess.Popen([sys.executable,'-m','vinhomes_api'],cwd=service,env=env,stdout=log,stderr=subprocess.STDOUT)
                base=f'http://127.0.0.1:{port}'
                for _ in range(60):
                    if process.poll() is not None:raise RuntimeError('Isolated business API stopped before readiness')
                    try:
                        if httpx.get(base+'/ready',timeout=1).status_code==200:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.25)
                else:raise RuntimeError('Isolated business API did not become ready')
                tests=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_resident_integration.py'],
                    cwd=service,env={**env,'VINHOMES_INTEGRATION_URL':base})
                return tests.returncode
        finally:
            if process:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            if created:
                assert re.fullmatch(r'maintain_flow_test_[a-f0-9]{32}',name)
                connection=await asyncpg.connect(owner)
                try:await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
                finally:await connection.close()


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
