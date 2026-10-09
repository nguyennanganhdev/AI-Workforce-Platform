"""HTTP MCP tool broker. No STDIO or shell processes; effects require exact-call approval."""

import asyncio
import json
from contextlib import asynccontextmanager

from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .db import Artifact, Record, emit, now, transaction, uid
from .domain import queue_agent, stable_hash
from .queue import fence_for_execution as fence
from .security import decrypt, validate_endpoint


@asynccontextmanager
async def connection(config):
    import httpx

    await validate_endpoint(config["url"])
    headers = (
        {"Authorization": "Bearer " + decrypt(config["encrypted_secret"])}
        if config.get("encrypted_secret")
        else {}
    )
    async with (
        httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=False) as http,
        streamable_http_client(config["url"], http_client=http) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        yield session


async def config_for(db, workspace, rid):
    record = await db.get(Record, rid)
    if (
        not record
        or record.workspace != workspace
        or record.kind != "mcp"
        or not record.body["enabled"]
    ):
        return None
    config = {**record.body, "version": record.version}
    if config.get("credential_id"):
        credential = await db.get(Record, config["credential_id"])
        if not credential or credential.workspace != workspace or credential.kind != "credentials":
            return None
        config["encrypted_secret"] = credential.body["encrypted_secret"]
    return config


async def mcp_tools(job, spec):
    from .runtime import chunk

    tools = []
    for rid in spec["mcp_ids"]:
        async with transaction() as db:
            config = await config_for(db, job.workspace, rid)
        if not config:
            continue
        try:
            async with asyncio.timeout(20):
                async with connection(config) as client:
                    available = (await client.list_tools()).tools
        except Exception:
            # Config failure must be visible to the agent; do not silently omit the grant.
            from .runtime import SafeRuntimeError

            raise SafeRuntimeError("mcp_unavailable") from None
        for remote in available:
            if remote.name not in config["allowed_tools"]:
                continue
            read_only = (
                config["read_only"]
                and remote.annotations
                and remote.annotations.readOnlyHint is True
            )

            def build_call(tool_name, config_id, config_version, automatic):
                async def call(**arguments):
                    from .runtime import SafeRuntimeError

                    if len(json.dumps(arguments, ensure_ascii=False).encode()) > 32000:
                        raise SafeRuntimeError("tool_arguments_too_large")
                    async with transaction() as db:
                        session, current = await fence(db, job.id, job.generation)
                        key = stable_hash([job.id, config_id, tool_name, arguments])[:36]
                        previous = await db.get(Artifact, key)
                        if previous:
                            return chunk({"execution_id": key, **previous.body})
                        body = {
                            "mcp_id": config_id,
                            "config_version": config_version,
                            "tool": tool_name,
                            "arguments": arguments,
                            "status": "started" if automatic else "pending",
                            "task_id": job.id,
                            "phase": current.body["phase"],
                            "round": current.body["round"],
                            "read_only": bool(automatic),
                        }
                        db.add(
                            Artifact(
                                id=key,
                                workspace=session.workspace,
                                session_id=session.id,
                                kind="tool_execution",
                                agent_id=current.body["agent_id"],
                                turn=session.turn,
                                body=body,
                            )
                        )
                        await emit(
                            db,
                            session,
                            "tool.started" if automatic else "approval.required",
                            {"execution_id": key, "tool": tool_name, "arguments": arguments},
                        )
                    if not automatic:
                        return chunk({"execution_id": key, "status": "pending_approval"})
                    return chunk(await perform(job, key))

                return call

            name = "mcp_" + rid[:8] + "_" + remote.name
            tools.append(
                FunctionTool(
                    build_call(remote.name, rid, config["version"], bool(read_only)),
                    name=name,
                    description=remote.description or remote.name,
                    input_schema=remote.inputSchema,
                    is_concurrency_safe=False,
                    permission=PermissionDecision(
                        behavior=PermissionBehavior.ALLOW,
                        message="Scoped broker; write calls require durable approval",
                    ),
                )
            )
    return tools


async def perform(job, execution_id):
    from .runtime import SafeRuntimeError

    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        execution = await db.get(Artifact, execution_id)
        config = await config_for(db, job.workspace, execution.body["mcp_id"])
        if not config or execution.body["tool"] not in config["allowed_tools"]:
            raise SafeRuntimeError("tool_grant_revoked")
        if config["version"] != execution.body.get("config_version"):
            raise SafeRuntimeError("tool_config_changed_requires_new_approval")
        arguments = execution.body["arguments"]
        tool_name = execution.body["tool"]
    try:
        async with asyncio.timeout(30):
            async with connection(config) as client:
                response = await client.call_tool(tool_name, arguments)
                text = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)[:16000]
                success = not response.isError
    except Exception:
        text, success = (
            "Tool timeout/transport error; external effect is uncertain. Do not retry automatically.",
            False,
        )
    async with transaction() as db:
        session, _ = await fence(db, job.id, job.generation)
        execution = await db.get(Artifact, execution_id)
        status = "succeeded" if success else "uncertain"
        evidence_id = uid()
        db.add(
            Artifact(
                id=evidence_id,
                workspace=session.workspace,
                session_id=session.id,
                kind="evidence",
                agent_id=execution.agent_id,
                turn=session.turn,
                body={
                    "text": text,
                    "source": f"mcp:{execution.body['mcp_id']}:{tool_name}",
                    "verified": success,
                    "verification": "tool_response_provenance",
                    "execution_id": execution_id,
                },
            )
        )
        execution.body = {
            **execution.body,
            "status": status,
            "text": text,
            "evidence_id": evidence_id,
        }
        await emit(
            db,
            session,
            "tool.result",
            {"execution_id": execution_id, "status": status, "evidence_id": evidence_id},
        )
        return {
            "execution_id": execution_id,
            "status": status,
            "evidence_id": evidence_id,
            "result": text,
        }


async def execute_approved(job):
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        execution = await db.get(Artifact, job.body["execution_id"])
        if execution.body["status"] == "approved":
            execution.body = {**execution.body, "status": "started", "started": now()}
            should_call = True
        elif execution.body["status"] == "started":
            # Worker crash after committing intent: cannot establish whether effect happened.
            execution.body = {**execution.body, "status": "uncertain"}
            should_call = False
        else:
            # Durable success survives a crash between result commit and job ack.
            should_call = False
    if should_call:
        await perform(job, execution.id)
    async with transaction() as db:
        session, current = await fence(db, job.id, job.generation)
        execution = await db.get(Artifact, job.body["execution_id"])
        current.status = "done"
        if execution.body["status"] != "succeeded":
            session.status = "needs_review"
            await emit(db, session, "tool.uncertain", {"execution_id": execution.id})
            return
        await queue_agent(
            db,
            session,
            execution.agent_id,
            execution.body["phase"],
            execution.body["round"],
            trigger=execution.id,
        )
