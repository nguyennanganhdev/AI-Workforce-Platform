"""python -m agent_eval: the evaluator service and worker (settings: agent_eval.worker.Settings.from_env)."""
import logging

import uvicorn

from .service import create_app
from .worker import Settings

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level='info')
