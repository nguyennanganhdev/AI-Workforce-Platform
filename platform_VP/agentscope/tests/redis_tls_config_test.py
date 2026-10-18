"""Connection configuration tests for Redis-backed service components."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Connection, SSLConnection

from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage


@pytest.mark.parametrize("component", [RedisStorage, RedisMessageBus])
@pytest.mark.parametrize(
    ("ssl", "connection_class"),
    [(False, Connection), (True, SSLConnection)],
)
def test_redis_connection_security_options(
    component: type[RedisStorage] | type[RedisMessageBus],
    ssl: bool,
    connection_class: type[Connection],
) -> None:
    """TLS and ACL settings must reach the redis connection pool."""

    async def exercise() -> tuple[AsyncMock, object]:
        pool = AsyncMock()
        with (
            patch("redis.asyncio.ConnectionPool", return_value=pool) as factory,
            patch("redis.asyncio.Redis"),
        ):
            client = component(username="service", ssl=ssl)
            await client.__aenter__()
            await client.aclose()
        return pool, factory

    _, factory = asyncio.run(exercise())
    kwargs = factory.call_args.kwargs
    assert kwargs["username"] == "service"
    assert kwargs["connection_class"] is connection_class
