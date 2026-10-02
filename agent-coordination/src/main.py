"""Start the Coordination service; absent bindings boot unready and reject ingress."""
import os
from pathlib import Path
import uvicorn
from config import ServiceConfig
from runtime.service import compose, create_app


def load():
    path = os.environ.get('COORDINATION_CONFIG')
    return ServiceConfig.model_validate_json(Path(path).read_text()) if path else ServiceConfig()


def app_factory():
    config = load()
    return create_app(config,compose(config))


if __name__ == '__main__':
    config = load()
    uvicorn.run(create_app(config,compose(config)),host=config.host,port=config.port,log_level='warning')
