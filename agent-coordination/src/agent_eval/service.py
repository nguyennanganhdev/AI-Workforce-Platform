"""The evaluator service: case generation for the business API, and the worker loop.

Run from agent-coordination/:  python -m agent_eval     (settings: worker.Settings.from_env)
"""
from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .generator import PROMPT_VERSION, generate
from .judge import PROMPT_VERSION as JUDGE_PROMPT
from .llm import ModelConfig
from .worker import Settings, Worker

log = logging.getLogger('agent_eval')


def create_app(settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None, run_worker: bool = True) -> Starlette:
    settings = settings or Settings.from_env()
    box: dict = {}

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(transport=transport) as client:
            box['client'] = client
            worker = Worker(settings, client)
            stopping = asyncio.Event()

            async def loop():
                registered_at = None
                while not stopping.is_set():
                    try:
                        if settings.sandbox_url and (registered_at is None or worker.clock() - registered_at > settings.catalog_seconds):
                            await worker.register()
                            registered_at = worker.clock()
                        if settings.sandbox_url and await worker.once():
                            continue
                    except Exception:  # noqa: BLE001 - one failed round must not end the service
                        log.exception('an evaluation round failed; the next one starts as usual')
                    try:
                        await asyncio.wait_for(stopping.wait(), settings.poll_seconds)
                    except TimeoutError:
                        pass

            task = asyncio.create_task(loop()) if run_worker else None
            try:
                yield
            finally:
                stopping.set()
                if task:
                    await asyncio.wait_for(task, 120)

    def authorized(request: Request) -> bool:
        offered = request.headers.get('authorization', '')
        return offered.startswith('Bearer ') and hmac.compare_digest(offered[7:].encode(), settings.service_token.encode())

    async def health(request):
        model = settings.fallback_model
        return JSONResponse({'status': 'ok', 'sandbox': bool(settings.sandbox_url), 'model': model.model_name if model else None,
                             'provider': model.provider if model else None})

    async def generate_cases(request):
        if not authorized(request):
            return JSONResponse({'error': 'Service authentication required'}, status_code=401)
        try:
            body = await request.json()
            context = body['context']
            model = ModelConfig.from_api(body['model_config']) if body.get('model_config') else settings.fallback_model
        except (ValueError, KeyError, TypeError):
            return JSONResponse({'error': 'Invalid generation request'}, status_code=422)
        if model is None:
            return JSONResponse({'error': 'No evaluator model is configured'}, status_code=503)
        try:
            cases, problems, usage = await generate(box['client'], model, context)
        except ValueError:
            return JSONResponse({'error': 'The context carried agent instructions'}, status_code=422)
        if not cases:
            return JSONResponse({'error': 'The model gave no usable cases', 'problems': problems}, status_code=503)
        return JSONResponse({'cases': cases, 'problems': problems, 'generator_profile': {
            'prompt_version': PROMPT_VERSION, 'judge_prompt_version': JUDGE_PROMPT, 'model_profile': model.profile,
            'usage': {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens}}})

    return Starlette(routes=[Route('/health', health), Route('/internal/generate', generate_cases, methods=['POST'])], lifespan=lifespan)
