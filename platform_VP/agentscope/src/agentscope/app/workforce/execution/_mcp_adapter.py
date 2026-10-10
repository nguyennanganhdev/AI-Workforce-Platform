# -*- coding: utf-8 -*-
"""Scoped MCP client lifetime and schema-checked output projection."""

from typing import Any

from contextlib import asynccontextmanager

from ._utils import ExecutionError, freeze


def validate(schema: Any, data: Any, code: Any) -> Any:
    """Do not include offending values (which may contain PII) in errors."""
    from jsonschema import Draft202012Validator

    if schema and list(Draft202012Validator(schema).iter_errors(data)):
        raise ExecutionError(code, 422)


class McpAdapter:
    """No cross-user client cache or mutation of shared runtime headers."""

    def __init__(
        self,
        secrets: Any,
        client_factory: Any,
        projector: Any,
        idempotency_fields: Any = None,
    ) -> None:
        self.secrets, self.client_factory, self.projector = (
            secrets,
            client_factory,
            projector,
        )
        # Reviewed integration configuration, never model/provider annotations.
        self.idempotency_fields = dict(idempotency_fields or {})

    def model_input_schema(self, descriptor: Any) -> Any:
        """Hide server-injected idempotency fields from model arguments."""
        schema = freeze(descriptor["input_schema"])
        field = self.idempotency_fields.get(descriptor["tool_version_id"])
        if field:
            schema.get("properties", {}).pop(field, None)
            if "required" in schema:
                schema["required"] = [
                    k for k in schema["required"] if k != field
                ]
        return schema

    def validate_model_input(self, descriptor: Any, arguments: Any) -> None:
        """
        Reject caller-selected idempotency even with permissive MCP schemas.
        """
        field = self.idempotency_fields.get(descriptor["tool_version_id"])
        if field and field in arguments:
            raise ExecutionError("IDEMPOTENCY_FIELD_SERVER_OWNED", 422)
        validate(
            self.model_input_schema(descriptor),
            arguments,
            "TOOL_INPUT_INVALID",
        )

    @asynccontextmanager
    async def prepare(
        self,
        scope: Any,
        context: Any,
        descriptor: Any,
        arguments: Any,
        call_reference: Any,
    ) -> Any:
        """
        Resolve credentials just in time; factory owns an isolated MCPClient.
        """
        arguments = freeze(arguments)
        field = self.idempotency_fields.get(descriptor["tool_version_id"])
        if field:
            if field in arguments and arguments[field] != call_reference:
                raise ExecutionError("CORRELATION_CONFLICT")
            arguments[field] = call_reference
        validate(descriptor["input_schema"], arguments, "TOOL_INPUT_INVALID")
        credential = await self.secrets.resolve_for_execution(
            scope,
            descriptor["credential_ref"],
            context["mode"],
        )
        if context["mode"] == "evaluation" and credential[
            "environment"
        ] not in {"mock", "sandbox"}:
            raise ExecutionError("EVAL_PRODUCTION_CREDENTIAL_FORBIDDEN", 403)
        async with self.client_factory(
            scope, descriptor, credential
        ) as client:
            tool = await client.get_tool(descriptor["provider_tool_name"])
            if tool.input_schema != descriptor["input_schema"]:
                raise ExecutionError("MCP_SCHEMA_DRIFT", 403)

            async def invoke() -> Any:
                chunk = await tool(**arguments)
                if str(getattr(chunk, "state", "")).lower() in {
                    "error",
                    "toolresultstate.error",
                }:
                    raise ExecutionError("PROVIDER_REJECTED", 422)
                # MCPTool already converts MCP responses into ToolChunk. The
                # provider-specific projector extracts JSON and strips secrets
                # before either persistence or model/UI access.
                output = await self.projector.project(scope, descriptor, chunk)
                validate(
                    descriptor.get("output_schema"),
                    output,
                    "TOOL_OUTPUT_INVALID",
                )
                return freeze(output)

            yield invoke
