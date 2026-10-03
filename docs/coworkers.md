# Coworkers

A coworker is a Bot with a durable profile and standing role. The role is sent with every run so the user does not have to restate the job in each channel.

## Data model

| Piece                | Table                           | Purpose                                                               |
| -------------------- | ------------------------------- | --------------------------------------------------------------------- |
| Runtime agent        | `agents`                        | AG-UI endpoint and optional key reference.                            |
| Profile              | `agent_profiles`                | Name, title, role, avatar seed, owner, visibility, and soft deletion. |
| Personal roster      | `agent_preferences`             | Per-user hidden state.                                                |
| Channel              | `channels`                      | Conversation membership and coworker binding.                         |
| Intelligence mapping | `intelligence_channel_mappings` | Channel-to-thread mapping.                                            |

Package-provided agents are public and ownerless. User-created coworkers are owned by the creator.

## Generated coworkers (Meta-Agent P0)

The default Create coworker flow asks for **name, role and description** (80, 120 and
1,000 characters respectively). The server generates a structured AgentSpec, resolves
required resources against the installed catalogue, compiles the core instructions and
runs deterministic checks plus an independent semantic review. You do not choose a model,
prompt, MCP server, tool or schema. Failed construction does not fall back to legacy creation.

Generated coworkers are private and use the existing in-process built-in runtime, including
when a managed remote endpoint is configured. Their canonical configuration is stored in
`agents.configuration.factory.spec`, with the compiler-owned `configuration.systemPrompt`
projection. This is the P0 path, separate from deferred Workforce publishing/versioning.

**Ready** means construction passed and required access is currently available. **Waiting
for access** means the artifact was saved but cannot run: an authorized person must explicitly
approve the displayed resources through the existing grants flow and/or the creator must
connect the required account, then recheck. An administrator's own connection cannot substitute
for the creator's connection. Partial approvals remain pending; successful grants are retained.
Readiness is checked again at runtime, and revocation or changed resources blocks subsequent
runs. A changed tool/skill definition requires recreation, not automatic rewriting.

Generated identity and configuration are read-only in P0, and copying is disabled. Inspection,
resource setup, hiding, deletion and existing conversation history remain available. Recreate a
coworker to change its job. Input/output requirements guide the model in ordinary text; semantic
review is not a guarantee of correct answers or strict structured output.

P0 release acceptance is **blocked** pending the final browser and configured-model quality
gates; see [verification prerequisites](development.md#meta-agent-p0-verification).

## Standing role

Remote coworkers receive a system message derived from their title and role description:

```text
You are Expense Manager, Finance Operations.

Review receipts, categorize expenses, and prepare reimbursement reports.

This standing role applies in every channel. Treat channel messages as task-specific instructions within it.
```

A further provenance block is appended by the deployment rather than the package: it tells the
coworker to say where each answer came from, to mark plainly anything it answers from its own
knowledge rather than from a source, and never to present the latter as the former. Being deployment-wide,
it cannot be forgotten from the next coworker somebody adds.

The message is ordinary AG-UI system content, so it works with any AG-UI-compatible backend. Editing the role affects the next run.

## Visibility

| Visibility | Who can see and run it      |
| ---------- | --------------------------- |
| `private`  | Owner and administrators.   |
| `public`   | Everyone in the deployment. |

Filtering happens in server/database queries. Package-provided agents cannot be edited or deleted through the product.

## Channels

Starting a channel creates a new conversation and Intelligence thread. Two channels with the same coworker stay separate.

Each channel routes through a channel-local proxy agent id, pinned to that channel's thread id, then forwards to the coworker runtime id.

## Deleting and hiding

Deleting is soft. The coworker stops running, but existing channels remain readable for their members and restore as tombstones.

Hiding is personal roster state. It removes the coworker from one user's list without disabling the coworker for anyone else.

## Default endpoint

Legacy coworkers can use:

```dotenv
MANAGED_AGENT_AG_UI_URL=http://localhost:4201/ag-ui
```

That is `agent-langgraph`, which runs a real framework and its own tool loop. The proof-of-concept on
`4200` hand-writes the protocol and leaves the loop to whatever is watching, so it is a reference
rather than something to build a deployment on.

The URL is optional. Set it with `MANAGED_AGENT_TOKEN`, or leave it unset: legacy coworkers
then use their explicit endpoint or the existing built-in prompt path, and a package agent whose endpoint expands to nothing is omitted
rather than registered against a missing host. A leftover token with no URL is ignored.
Package-provided agents otherwise use their own `agents.yaml` configuration.

## Register an external AG-UI agent

In `agents.yaml`:

```yaml
agents:
  - id: risk
    name: Risk
    title: Risk & Compliance
    role_description: Investigate policies and controls.
    type: remote-ag-ui
    endpoint: http://risk.internal/ag-ui
```

In the product, choose **Connect an existing agent** from `/agents`, or edit a legacy coworker, and set:

- name;
- title;
- role description;
- visibility;
- optional endpoint;
- optional authorization header.

Endpoint registration uses target checks. Cloud metadata addresses are refused under every configuration. Optional keys are write-only: sending a key stores/replaces it, omitting it keeps the existing key, and APIs do not return it.

`POST /api/agents/test-connection` checks whether an endpoint answers before saving it.

## Capabilities

A coworker's role does not grant capabilities. Capabilities are governed separately:

- browser and file actions go through the computer gateway policy;
- components are published deployment-wide and can be withheld per Bot;
- MCP tools are granted per Bot by administrators;
- personal skills can be attached only to Bots the author owns;
- deployment skills are managed by administrators.

See [architecture.md](architecture.md).
