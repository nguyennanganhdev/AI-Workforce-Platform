# -*- coding: utf-8 -*-
"""
Single internal tool execution gateway; never exposed as a public MCP API.
"""

from typing import Any

import asyncio

from ..contracts import Scope
from ._calculator import calculate
from ._effects import SIDE_EFFECTS, classify
from ._mcp_adapter import validate
from ._utils import ExecutionError, digest, freeze, value


class ExecutionGateway:
    """
    Compose ports, policy, transactions, optional async protocols and MCP.
    """

    def __init__(
        self,
        policy: Any,
        transactions: Any,
        mcp: Any,
        operations: Any,
        protocols: Any,
        builtins: Any = None,
        call_factory: Any = None,
    ) -> None:
        self.policy, self.transactions, self.mcp = policy, transactions, mcp
        self.operations, self.protocols = operations, protocols
        self.repo = transactions.repo
        self.builtins = {"builtin.money.v1": calculate, **(builtins or {})}
        self.call_factory = call_factory

    async def execute(self, scope: Any, request: Any) -> Any:
        """Durable intent precedes network; replay returns persisted state."""
        request = freeze(value(request))
        context, descriptor = await self.policy.check(scope, request)
        descriptor_hash = digest(descriptor)
        if descriptor["source_kind"] == "mcp":
            self.mcp.validate_model_input(descriptor, request["arguments"])
        else:
            validate(
                descriptor["input_schema"],
                request["arguments"],
                "TOOL_INPUT_INVALID",
            )
        if request.get(
            "arguments_hash", digest(request["arguments"])
        ) != digest(request["arguments"]):
            raise ExecutionError("ARGUMENTS_HASH_MISMATCH", 422)
        # Return existing outcomes without fetching a possibly expired quote.
        async with self.repo.transaction() as uow:
            previous = await self.repo.get(
                "calls", request["call_id"], uow, scope
            )
        if previous and previous["status"] not in {
            "proposed",
            "awaiting_approval",
        }:
            fingerprint = self.transactions.fingerprint(request)
            if previous["fingerprint"] != fingerprint:
                raise ExecutionError("IDEMPOTENCY_CONFLICT")
            return previous
        effect = classify(descriptor)
        quote = None
        if effect in SIDE_EFFECTS:
            quote = await self.transactions.approvals.verified_quote(
                scope, context, request, descriptor
            )
        protocol = None
        if descriptor.get("async_protocol_hash"):
            protocol = freeze(
                await self.protocols.get_snapshot(
                    Scope.model_validate(scope), descriptor["tool_version_id"]
                )
            )
            if digest(protocol) != descriptor["async_protocol_hash"]:
                raise ExecutionError("ASYNC_PROTOCOL_PIN_MISMATCH", 403)
        async with self.repo.transaction() as uow:
            context, descriptor = await self.policy.check(
                scope, request, uow=uow
            )
            if digest(descriptor) != descriptor_hash:
                raise ExecutionError("CATALOG_CHANGED")
            call, dispatch = await self.transactions.reserve(
                scope, context, request, descriptor, quote, uow
            )
            operation = None
            if dispatch and protocol:
                operation = await self.operations.prepare(
                    scope, context, request, protocol, uow
                )
            arguments = request["arguments"]
            if operation:
                arguments = self.operations.create_arguments(
                    operation, arguments
                )
                validate(
                    descriptor["input_schema"], arguments, "TOOL_INPUT_INVALID"
                )
        if not dispatch:
            return call
        sent = False
        output, error, status, external_id = None, None, "failed", None
        try:
            if descriptor["source_kind"] == "builtin":
                handler = self.builtins.get(descriptor["tool_version_id"])
                if handler is None:
                    raise ExecutionError("BUILTIN_NOT_REGISTERED", 403)
                await self.policy.check(scope, request)
                sent = True
                output = handler(arguments)
                if hasattr(output, "__await__"):
                    output = await output
            else:
                async with self.mcp.prepare(
                    scope,
                    context,
                    descriptor,
                    arguments,
                    call_reference=operation["correlation_id"]
                    if operation
                    else call["id"],
                ) as invoke:
                    # Credential resolution/connection setup can take time.
                    # Check
                    # membership, cancellation and route again immediately
                    # before send.
                    await self.policy.check(scope, request)
                    sent = True
                    output = await invoke()
            output = freeze(output)
            validate(
                descriptor.get("output_schema"), output, "TOOL_OUTPUT_INVALID"
            )
            status = "succeeded"
            external_id = (
                output.get("external_transaction_id")
                if isinstance(output, dict)
                else None
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                self._finish(
                    scope,
                    call,
                    operation,
                    "unknown" if sent else "failed",
                    None,
                    "EXECUTION_INTERRUPTED",
                    None,
                )
            )
            raise
        except Exception as exc:
            # Once a side effect may have left the process, a malformed
            # response,
            # timeout or network error cannot prove the provider did nothing.
            status = "unknown" if sent and effect in SIDE_EFFECTS else "failed"
            error = (
                exc.code
                if isinstance(exc, ExecutionError)
                else "PROVIDER_CALL_FAILED"
            )
            output = None
        return await self._finish(
            scope, call, operation, status, output, error, external_id
        )

    async def _finish(
        self,
        scope: Any,
        call: Any,
        operation: Any,
        status: Any,
        output: Any,
        error: Any,
        external_id: Any,
    ) -> Any:
        async with self.repo.transaction() as uow:
            if operation:
                if status == "succeeded":
                    try:
                        result = (
                            await self.protocols.normalize_creation_result(
                                operation["protocol"], output
                            )
                        )
                    except (ExecutionError, KeyError, ValueError):
                        status, output, error = (
                            "unknown",
                            None,
                            "CREATION_RESULT_INVALID",
                        )
                        result = {
                            "creation_status": "unknown",
                            "pending": True,
                        }
                else:
                    result = {
                        "creation_status": "unknown"
                        if status == "unknown"
                        else "failed",
                        "pending": status == "unknown",
                    }
                from sqlalchemy.exc import IntegrityError

                try:
                    async with uow.begin_nested():
                        await self.operations.bind_result(
                            scope, operation["id"], result, uow
                        )
                except (ExecutionError, IntegrityError):
                    status, output, error = (
                        "unknown",
                        None,
                        "CORRELATION_CONFLICT",
                    )
                    current = await self.repo.get(
                        "operations", operation["id"], uow, scope, lock=True
                    )
                    current["reconciliation_error"] = error
                    if current["creation_status"] in {"prepared", "intent"}:
                        current["creation_status"] = "unknown"
                    await self.repo.save(
                        "operations", current, current["revision"], uow
                    )
            return await self.transactions.finish(
                scope, call["id"], status, output, error, external_id, uow
            )

    async def get_call(self, scope: Any, call_id: Any) -> Any:
        """
        Manager projection; partner reads are delegated to its audience port.
        """
        return await self.repo.read("calls", scope, call_id)

    async def prepare_toolkit(
        self, scope: Any, run_context: Any, agent_spec: Any
    ) -> Any:
        """
        Tool assembly is explicit; wrappers still recheck every invocation.
        """
        from ._toolkit import assemble_toolkit

        if self.call_factory is None:
            raise ExecutionError("CALL_FACTORY_UNAVAILABLE", 503)

        async def request_factory(tool_version_id: Any, arguments: Any) -> Any:
            return await self.call_factory(
                scope, run_context, agent_spec, tool_version_id, arguments
            )

        return await assemble_toolkit(
            self, scope, value(run_context), value(agent_spec), request_factory
        )

    async def decide_approval(
        self,
        scope: Any,
        approval_id: Any,
        decision: Any,
        actor: Any,
        audience: Any = None,
    ) -> Any:
        """
        ExecutionPort manager decision uses a shared DTO's JSON representation.
        """
        decision = value(decision)
        return await self.transactions.approvals.decide_approval(
            scope,
            approval_id,
            decision["decision"],
            actor,
            audience,
            arguments_hash=decision["arguments_hash"],
            quote_hash=decision["quote_hash"],
        )
