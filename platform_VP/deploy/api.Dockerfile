FROM ghcr.io/astral-sh/uv:0.11.0 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
RUN groupadd --system platform && useradd --system --gid platform --create-home platform
WORKDIR /app
COPY agentscope /app/agentscope
COPY services/platform-api/pyproject.toml services/platform-api/uv.lock /app/services/platform-api/
COPY services/platform-api/vp/__init__.py /app/services/platform-api/vp/__init__.py
WORKDIR /app/services/platform-api
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev && chown -R platform:platform /app
COPY --chown=platform:platform services/platform-api/vp /app/services/platform-api/vp
USER platform
EXPOSE 8088
