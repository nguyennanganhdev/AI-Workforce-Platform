"""Redis is a wake-up hint; PostgreSQL remains the durable queue and replay log."""

import asyncio

from .config import settings


async def wake():
    if not settings.redis_url:
        return
    from redis.asyncio import Redis

    client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        await client.lpush("vp:wakeup", "ready")
        await client.ltrim("vp:wakeup", 0, 99)
    except Exception:
        pass  # Polling recovers; losing this hint must not lose a job.
    finally:
        await client.aclose()


async def wait_for_work(stop):
    if settings.redis_url:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=2)
        try:
            await client.brpop("vp:wakeup", timeout=1)
            return
        except Exception:
            pass
        finally:
            await client.aclose()
    try:
        await asyncio.wait_for(stop.wait(), timeout=0.5)
    except TimeoutError:
        pass
