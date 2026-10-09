import asyncio
import signal

from . import db
from .automation import scheduler_loop
from .config import settings
from .knowledge import execute_index
from .maintenance import maintenance_loop
from .queue import worker_loop
from .runtime import execute_agent
from .security import cipher


async def main():
    cipher()
    await db.initialize()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    tasks = [
        asyncio.create_task(worker_loop(i, stop, execute_agent)) for i in range(settings.workers)
    ]
    tasks += [
        asyncio.create_task(worker_loop(0, stop, execute_index, "index")),
        asyncio.create_task(scheduler_loop(stop)),
        asyncio.create_task(maintenance_loop(stop, settings.workers)),
    ]
    try:
        # Fail process if any long-lived loop fails; container restart makes failure observable.
        stopped = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait([*tasks, stopped], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is not stopped:
                task.result()
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
