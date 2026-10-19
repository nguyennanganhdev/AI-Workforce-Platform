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

## Telegram channel

The example service registers `TelegramChannel` alongside the other channel
types. In the Web UI, open **Channels**, choose **Telegram**, then enter:

- **Bot ID**: the numeric part before `:` in the token issued by `@BotFather`.
- **Bot Token**: the full BotFather token. Keep it secret.
- The agent routing rule and model to use for incoming messages.

Save the channel, open a private chat with your bot in Telegram, and send a
text message. The user must start the chat before the bot can reply. Tool
approval requests appear as **Approve** / **Deny** buttons; unusually long
tool-call IDs require approval from the session in Web UI instead.

This first version supports private text conversations. Groups, attachments,
and streaming replies are not supported; attachments remain visible in the
Web UI. No additional Telegram SDK or public webhook URL is required.

Run only one polling worker for each bot. When using a dedicated channel
worker, include `TelegramChannel` in its `channels` list and set
`enable_channel_worker=False` on API replicas. A bot already using a webhook
or another poller shows a failed status; the adapter never removes another
integration's webhook automatically. After resolving a conflict, disable and
enable the channel to reconnect. Credentials are immutable: recreate the
channel if the token changes.

Telegram acknowledges updates on the next poll. A crash between handling a
batch and acknowledging it can replay the last batch after restart; this
adapter does not promise exactly-once delivery. Use durable Redis storage
for production. Like the existing channels, credentials are hidden from
channel API responses but are not encrypted at rest by this application.

## What Next

- You can customize the service in `main.py` by adding your own MCPs, middlewares, or workspace manager implementations.

- Experience the agent service, including
    - human-in-the-loop interactions & permission system
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01vGGiBw20agWwpzmjy_!!6000000006866-2-tps-2934-1732.png" alt="Permission System" width="100%">

    - schedule tasks
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01Xi3Qw71E2haKKu4z0_!!6000000000294-2-tps-2932-1738.png" alt="Schedule Tasks" width="100%">

    - and more! (stay tuned for future updates)
