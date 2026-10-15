"""Run the local Vinhomes API server."""

import uvicorn

from .v3_config import V3Settings


def main() -> None:
    settings = V3Settings.from_env()
    uvicorn.run("vinhomes_api.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
