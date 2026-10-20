# Agent Service

Agent service is a FastAPI-based, multi-tenant and multi-session service built with AgentScope 2.0.

This example demonstrates

- how to set up the agent service with Redis storage, and
- how to launch the service and its companion Web UI

Details about the agent service please refer to the [tutorial](https://docs.agentscope.io/latest/en/deploy/agent-service).

## Prerequisites

- Python ≥ 3.11
- Node.js ≥ 20 with `npx`
- [optional] Gaode/AMap API key in `AMAP_API_KEY` (for the `amap` MCP)

## Quickstart

Install AgentScope from PyPI or source:

```bash
uv pip install agentscope[full]
# or
# uv pip install -e [full]
```

Install Redis and start it as backend storage:

```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Linux (systemd)
sudo apt install redis-server
sudo systemctl start redis-server

# Docker (cross-platform)
docker run --rm -p 6379:6379 redis:7
```

Start the agent service:

```bash
cd examples/agent_service

python main.py
```

Launch the Web UI in a separate terminal to experience a chat-style interface:

```bash
cd examples/web_ui/

pnpm install
# or npm install

# Run in dev mode
pnpm dev
```

After that, you can set the API endpoint `http://localhost:8000` in the Web UI and start experiencing the agent service.

<img src="https://gw.alicdn.com/imgextra/i2/O1CN01Phmg1G1brIVC8WXyU_!!6000000003518-2-tps-2938-1736.png" alt="Web UI Screenshot" width="100%">

## Docker deployment permissions

The application image runs as UID/GID `10001:10001`. Compose drops all Linux
capabilities and sets `no-new-privileges`; do not override the application user
with root or mount the Docker socket into the app container. When deploying the
image outside Compose (including AWS), use the same user and security settings.

Rebuild and recreate the app to apply runtime and image changes. Fresh workspace
volumes inherit the image's writable workspace directory. Existing volumes from
root-based images must have their ownership migrated once, with the app stopped.
From the repository's `platform_VP/agentscope` directory, using the deployment's
existing environment configuration:

```bash
docker compose build app
docker compose stop app
docker compose run --rm --no-deps --user 0:0 --cap-add CHOWN --cap-add DAC_OVERRIDE app \
  chown -Rh 10001:10001 /app/examples/agent_service/workspaces
docker compose up -d --no-deps --force-recreate app
```

For bind mounts or a different AWS runtime, set the mounted workspace directory's
ownership to `10001:10001` before starting the new container. Keep MCP providers
trusted: the code-execution deny policy recognizes published tool names and input
schemas, and cannot verify a provider that hides execution behind another API.

## What Next

- You can customize the service in `main.py` by adding your own MCPs, middlewares, or workspace manager implementations.

- Experience the agent service, including
    - human-in-the-loop interactions & permission system
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01vGGiBw20agWwpzmjy_!!6000000006866-2-tps-2934-1732.png" alt="Permission System" width="100%">

    - schedule tasks
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01Xi3Qw71E2haKKu4z0_!!6000000000294-2-tps-2932-1738.png" alt="Schedule Tasks" width="100%">

    - and more! (stay tuned for future updates)
