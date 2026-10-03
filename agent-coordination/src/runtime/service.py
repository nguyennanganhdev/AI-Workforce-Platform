"""Authenticated ASGI ingress. ACK only after durable accept; no fixture runtime."""
import asyncio
import hmac
import importlib
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from starlette.applications import Starlette
from starlette.responses import JSONResponse,Response
from starlette.routing import Route

from adapters.backend.errors import AdapterError
from groupchat.reception import ReceptionMessage

REQUIRED = frozenset(('storage','authority','event_verifier','releases','openbot','model','delegation','schemas'))


@dataclass
class Components:
    ingress: object
    worker: object
    readiness: object
    close: object


@dataclass(frozen=True)
class Continuation:
    """Yielded normal work, distinct from bounded recovery of an unknown outcome."""
    delay: float = 5


class Worker:
    """One inbox owner; state/action journal remains the sole outbound dispatcher.

    Processing must reverify persisted proofs and use backend remote fences. Lease
    expiry is not permission to resend an unknown action. Exceptions release local
    scheduling only; durable supervisor sending/unknown state requires reconciliation.
    """
    def __init__(self, store, handler, *, owner, lease_seconds=30, max_attempts=3):
        if type(max_attempts) is not int or max_attempts < 1: raise ValueError('invalid recovery bound')
        self.max_attempts = max_attempts
        self.store,self.handler,self.owner = store,handler,owner
        self.seconds,self.stopping = lease_seconds,asyncio.Event()

    async def once(self):
        claim = await self.store.claim(self.owner,self.seconds)
        if not claim: return False
        async def heartbeat():
            while True:
                await asyncio.sleep(self.seconds/3)
                await self.store.renew(claim,self.seconds)

        async def process():
            with self.store.lease_scope(claim):
                return await self.handler(claim)

        execution = asyncio.create_task(process())
        renewal = asyncio.create_task(heartbeat())
        try:
            done,_ = await asyncio.wait((execution,renewal),return_when=asyncio.FIRST_COMPLETED)
            if renewal in done:
                await renewal  # lease loss aborts local work; remote result remains unknown
                raise AdapterError('stale_fence')
            retry_after = await execution
            with self.store.lease_scope(claim):
                if isinstance(retry_after, Continuation):
                    await self.store.defer(claim,retry_after.delay)
                elif retry_after is not None:
                    if claim.recovery_attempts + 1 >= self.max_attempts: await self.store.park(claim)
                    else: await self.store.defer(claim,retry_after,recovery=True)
                else:
                    await self.store.ack(claim)
        except Exception as exc:
            try:
                reason=exc.code if isinstance(exc,AdapterError) else type(exc).__name__
                if claim.recovery_attempts + 1 >= self.max_attempts: await self.store.park(claim,reason=reason)
                else: await self.store.defer(claim,5,recovery=True)
            except AdapterError: pass  # takeover owns it now
            raise
        finally:
            for task in (execution,renewal):
                if not task.done(): task.cancel()
            await asyncio.gather(execution,renewal,return_exceptions=True)
        return True

    async def run(self):
        while not self.stopping.is_set():
            try: processed = await self.once()
            except Exception: processed = False  # no secrets/body in operational logs
            if not processed:
                try: await asyncio.wait_for(self.stopping.wait(),.5)
                except TimeoutError: pass

    async def stop(self): self.stopping.set()


def compose(config):
    if not config.factory: return None
    module,symbol = config.factory.split(':',1)
    factory = getattr(importlib.import_module(module),symbol)
    result = factory(config)
    if not isinstance(result,Components): raise ValueError('composition factory must return Components')
    return result


def create_app(config, components=None):
    token = os.environ.get(config.ingress_token_env)
    if token and (len(token)<32 or '\n' in token or '\r' in token):
        raise ValueError('invalid ingress credential reference')

    lifecycle = {"draining":False,"worker":None}

    async def readiness():
        worker = lifecycle["worker"]
        if lifecycle["draining"] or (worker is not None and worker.done()): return False
        if not token or components is None:
            return False
        result = await components.readiness()
        return isinstance(result,dict) and set(result)>=REQUIRED and all(result[k] is True for k in REQUIRED)

    async def health(request): return JSONResponse({'status':'ok'})
    async def ready(request):
        try: available = await asyncio.wait_for(readiness(),5)
        except Exception: available = False
        return JSONResponse({'ready':available},status_code=200 if available else 503)

    async def ingress(request):
        offered = request.headers.get('authorization','')
        if not token or not hmac.compare_digest(offered,'Bearer '+token):
            return JSONResponse({'error':'unauthorized'},status_code=401)
        try:
            if not await asyncio.wait_for(readiness(),5): return JSONResponse({'error':'dependency_unavailable'},status_code=503)
            if request.headers.get('content-type','').split(';')[0] != 'application/json':
                return JSONResponse({'error':'invalid_content_type'},status_code=415)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>config.max_body_bytes: return JSONResponse({'error':'body_limit'},status_code=413)
            wire = json.loads(body)
            kind = {'/v2/reception':'reception','/v2/events':'event',
                    '/v2/contributions':'contribution','/v2/reports':'report',
                    '/v2/report-downloads':'download'}[request.url.path]
            if kind == 'reception': ReceptionMessage.model_validate(wire,strict=True)
            if kind == 'download':
                workflows=getattr(components,'workflows',None)
                if workflows is None: raise AdapterError('workflow_dependency_unavailable')
                content=await workflows.download(wire,request.headers)
                return Response(content,media_type='application/octet-stream',headers={
                    'Content-Disposition':'attachment; filename="report.bin"','Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff'})
            # Authority verifies actor/source/audience/expiry; bearer is service
            # authentication only. Production ingress owns durable accept + proof.
            receipt = await components.ingress.accept(kind,wire,request.headers)
            if not isinstance(receipt,dict) or receipt.get('durable') is not True:
                raise AdapterError('durable_accept_unconfirmed',outcome_unknown=True)
            return JSONResponse({'accepted':True,'id':receipt['id']},status_code=202)
        except AdapterError as exc:
            return JSONResponse({'error':exc.code},status_code=409 if exc.code=='conflict' else 503)
        except (ValueError,TypeError,KeyError):
            return JSONResponse({'error':'invalid_input'},status_code=422)
        except Exception:
            return JSONResponse({'error':'dependency_unavailable'},status_code=503)

    @asynccontextmanager
    async def lifespan(app):
        worker = asyncio.create_task(components.worker.run()) if components else None
        lifecycle["worker"] = worker
        try: yield
        finally:
            lifecycle["draining"] = True
            if components:
                await components.worker.stop()
                if worker:
                    try: await asyncio.wait_for(worker,10)
                    except TimeoutError:
                        worker.cancel()
                        await asyncio.gather(worker,return_exceptions=True)
                await components.close()

    return Starlette(routes=[Route('/health',health),Route('/ready',ready),
        *[Route(path,ingress,methods=['POST']) for path in (
            '/v2/reception','/v2/events','/v2/contributions','/v2/reports','/v2/report-downloads')]],lifespan=lifespan)
