# The platform image: awp (platform_VP/core) on the vendored AgentScope (platform_VP/agentscope), both installed from
# this repository's source. Build context: platform_VP.
#
#   docker build -t awp-platform:0.1.0 -f platform_VP/Dockerfile platform_VP
#
# Third-party packages come from deploy/requirements.lock (exact versions and hashes, wheels only). Nothing secret is
# copied in: keys, database URLs and the model catalog arrive at run time (deploy/compose.yml, deploy/.env).

# ---- build: a virtualenv with everything installed --------------------------------------------------------------
FROM python:3.12-slim AS build

# Patient with a slow network. Downloads are kept in a BuildKit cache mount (never in a layer), so a build that was cut
# off goes on where it stopped.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

# The runtime virtualenv has no pip of its own: the build stage's pip installs into it.
RUN python -m venv --without-pip /opt/venv

COPY deploy/requirements.lock /build/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --python /opt/venv/bin/python install --require-hashes --only-binary :all: -r /build/requirements.lock

# The two packages of this repository, built here with pinned build tools and installed without resolving anything:
# their dependencies are exactly the lock above. `pip check` fails the build when the lock no longer covers them.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install setuptools==80.9.0 wheel==0.45.1
COPY agentscope /build/agentscope
COPY core /build/core
RUN pip wheel --no-deps --no-build-isolation -w /build/wheels /build/agentscope /build/core \
 && pip --python /opt/venv/bin/python install --no-deps /build/wheels/*.whl \
 && pip --python /opt/venv/bin/python check \
 && /opt/venv/bin/python -c "import awp, agentscope, asyncpg, cryptography, redis, uvicorn; print('agentscope', agentscope.__version__)"

# ---- runtime --------------------------------------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    HOME=/var/lib/awp \
    AWP_HOST=0.0.0.0 \
    AWP_PORT=8800 \
    AWP_WORKSPACE_DIR=/var/lib/awp/workspaces \
    AWP_AUTO_CREATE=0

# A fixed uid/gid so a host directory or a volume can be given to it. /var/lib/awp is the only place the process writes.
RUN groupadd --system --gid 10001 awp \
 && useradd --system --uid 10001 --gid awp --home-dir /var/lib/awp --no-create-home --shell /usr/sbin/nologin awp \
 && mkdir -p /var/lib/awp/workspaces /etc/awp \
 && chown -R awp:awp /var/lib/awp

COPY --from=build /opt/venv /opt/venv

WORKDIR /var/lib/awp
USER 10001:10001
VOLUME ["/var/lib/awp"]
EXPOSE 8800

# No curl in the image: the check is Python's own urllib. /platform/v1/health needs no key.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=4 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('AWP_PORT', '8800') + '/platform/v1/health', timeout=4).read()"]

# Exec form: the Python process is the one that receives SIGTERM, and uvicorn then stops accepting requests, lets the
# running ones end and runs the application's shutdown (the engine stops, the pools close).
STOPSIGNAL SIGTERM
ENTRYPOINT ["python", "-m", "awp"]
