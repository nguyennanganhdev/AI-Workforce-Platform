FROM node:20-bookworm-slim AS node-runtime

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Node/npm/npx are required by the default Playwright MCP server.
COPY --from=node-runtime /usr/local/ /usr/local/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# Install only the extras used by the Agent Service and Compose services.
RUN python -m pip install --no-cache-dir \
    -e ".[service,storage-redis,storage-s3,storage-postgres,auth,channel,vdb-qdrant]"

WORKDIR /app/examples/agent_service

EXPOSE 8000

CMD ["/bin/sh", "-c", "python -m alembic -c /app/src/agentscope/app/storage/_sql/_alembic/alembic.ini upgrade head && python main.py"]
