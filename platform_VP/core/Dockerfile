FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d
WORKDIR /app
COPY core/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY agentscope/pyproject.toml agentscope/README.md agentscope/LICENSE ./agentscope/
COPY agentscope/src ./agentscope/src
COPY core/pyproject.toml ./core/
COPY core/src ./core/src
RUN pip install --no-cache-dir --no-deps './agentscope[service,storage-sql]' ./core
WORKDIR /app/core
EXPOSE 8800
CMD ["python", "-m", "awp"]
