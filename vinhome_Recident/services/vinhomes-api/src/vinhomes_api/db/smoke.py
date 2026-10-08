"""Run a minimal live database connectivity check."""

import asyncio

from sqlalchemy import text

from ..config import Settings
from .engine import create_database


async def check_database_connection(database_url: str) -> int:
    database = create_database(database_url)
    try:
        async with database.engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return result.scalar_one()
    finally:
        await database.dispose()


async def _main() -> None:
    result = await check_database_connection(Settings.from_env().database_url)
    if result != 1:
        raise RuntimeError("Database smoke query returned an unexpected result")
    print("Database connection OK (SELECT 1)")


if __name__ == "__main__":
    asyncio.run(_main())
