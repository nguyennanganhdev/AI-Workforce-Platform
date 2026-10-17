"""TEST ONLY: compose real C1/C2 producers with an explicit fake C4 sink."""

from contextlib import asynccontextmanager
import hashlib
import hmac
import json

from sqlalchemy import insert, select

from agentscope.app.workforce.contracts import Scope
from agentscope.app.workforce.execution.external_operations import (
    RegistryExecutionProtocols,
)
from agentscope.app.workforce.execution.provider_events import (
    WorkflowEventAdapter,
)
from agentscope.app.workforce.foundation import (
    DurableJobService,
    HmacProviderAuth,
    SqlDurableJobRepository,
    SqlProviderCredentialRepository,
)
from agentscope.app.workforce.foundation._tables import (
    metadata as foundation_metadata,
    provider_credentials,
    provider_integrations,
)
from agentscope.app.workforce.registry.event_protocols import (
    SqlAsyncProtocolProvider,
)
from agentscope.app.workforce.registry.event_protocols._tables import (
    metadata as registry_metadata,
)
from execution_fakes import SCOPE_A, approved_call, harness
from phase_ab_fakes import TypedWorkflow, sample_protocol


SECRET = b"TEST-ONLY-C3-HMAC-SECRET-DO-NOT-USE" * 2


def signed(env, envelope=None):
    raw = b"" if envelope is None else json.dumps(envelope).encode("utf-8")
    stamp = str(int(env.clock().timestamp()))
    signature = hmac.new(
        SECRET, stamp.encode("ascii") + b"." + raw, hashlib.sha256
    ).hexdigest()
    return raw, {
        "authorization": "ApiKey TEST-ONLY-PROVIDER",
        "x-partner-timestamp": stamp,
        "x-partner-key-id": "TEST-signing-key",
        "x-partner-signature": "v1=" + signature,
    }


async def principal(env, envelope):
    raw, headers = signed(env, envelope)
    return await env.auth.authenticate(raw, headers)


async def table_rows(env, table):
    async with env.repo.transaction() as uow:
        return (await uow.execute(select(table))).mappings().all()


@asynccontextmanager
async def c3_harness(*, event_mode="snapshot"):
    async with harness(tracking=True, canonical_uow=True) as env:
        async with env.engine.begin() as connection:
            await connection.run_sync(foundation_metadata.create_all)
            await connection.run_sync(registry_metadata.create_all)
        async with env.repo.transaction() as uow:
            await uow.execute(
                insert(provider_integrations).values(
                    id="provider-1",
                    tenant_id=SCOPE_A["tenant_id"],
                    partner_client_id="provider-client",
                    name="TEST-C3",
                    status="active",
                    created_at=env.clock(),
                    updated_at=env.clock(),
                )
            )
            await uow.execute(
                insert(provider_credentials).values(
                    id="TEST-credential-row",
                    provider_integration_id="provider-1",
                    api_credential_id="TEST-api-credential",
                    signing_key_id="TEST-signing-key",
                    secret_ref="TEST-secret-reference",
                    purpose="provider_events",
                    allowed_operations=[
                        "publish_job_event",
                        "read_event_receipt",
                    ],
                    status="active",
                    created_at=env.clock(),
                    updated_at=env.clock(),
                )
            )

        async def api_key_auth(key):
            if key != "TEST-ONLY-PROVIDER":
                raise PermissionError("TEST private credential failure")
            return {
                "key_id": "TEST-api-credential",
                "tenant_id": SCOPE_A["tenant_id"],
                "client_id": "provider-client",
            }

        env.auth = HmacProviderAuth(
            SqlProviderCredentialRepository(env.uows),
            api_key_auth,
            lambda ref: SECRET,
            clock=env.clock,
        )
        env.jobs = DurableJobService(
            SqlDurableJobRepository(env.uows), clock=env.clock
        )
        env.registry_provider = SqlAsyncProtocolProvider(env.uows)
        env.protocols = RegistryExecutionProtocols(
            env.registry_provider, env.repo, env.auth, env.operations
        )
        env.config = sample_protocol(event_mode)
        env.registry_service = env.protocols.bind(SCOPE_A).port
        await env.registry_service.publish(env.config)
        env.descriptor["async_protocol_hash"] = (
            env.config.snapshot_ref.schema_hash
        )
        env.gateway.protocols = env.ingress.protocols = env.protocols
        env.ingress.auth, env.ingress.jobs = env.auth, env.jobs

        async def assigned(arguments, output):
            output["status"] = "assigned"

        env.provider.after_write = assigned
        env.typed_workflow = TypedWorkflow(env)
        env.workflow_adapter = WorkflowEventAdapter(
            env.repo,
            env.typed_workflow,
            query_sink=env.typed_workflow.apply_query_result,
        )
        env.processor.workflow = env.workflow_adapter
        call = await approved_call(env)
        await env.gateway.execute(SCOPE_A, call)
        env.operation = (
            await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
        )[0]
        assert env.operation["creation_status"] == "succeeded"
        assert (
            env.operation["scope"]
            == Scope.model_validate(SCOPE_A).model_dump()
        )
        yield env
