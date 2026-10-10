"""TEST ONLY: deterministic ports and finite Hotel/Car/Technical providers."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import Column, JSON, MetaData, String, Table, insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentscope.app.workforce.contracts import ActorContext, Scope
from agentscope.app.workforce.execution import (
    ApprovalService,
    ExecutionGateway,
    ExecutionPolicy,
    TransactionService,
    calculator_descriptor,
    create_repository,
    get_metadata,
)
from agentscope.app.workforce.execution._mcp_adapter import McpAdapter
from agentscope.app.workforce.execution._utils import (
    ExecutionError,
    digest,
    freeze,
    owner,
    timestamp,
)
from agentscope.app.workforce.execution.external_operations import (
    ExternalOperationService,
)
from agentscope.app.workforce.execution.provider_events import (
    ProviderEventIngress,
    ProviderEventProcessor,
)

SCOPE_A = {
    "tenant_id": "tenant",
    "domain_id": "travel",
    "area_id": "area-1",
    "manager_account_id": "A",
}
SCOPE_B = {**SCOPE_A, "manager_account_id": "B"}
SCOPE_C = {**SCOPE_A, "area_id": "area-2", "manager_account_id": "C"}
SCOPE_D = {**SCOPE_A, "domain_id": "other", "manager_account_id": "D"}
AUDIENCE = {
    "partner_client_id": "customer",
    "external_user_id": "resident-123",
    "external_conversation_id": "CHAT-A",
    "external_ticket_id": "TICKET-A",
}
MANAGER = {"kind": "manager", "actor_id": "A"}
PROVIDER = {
    "kind": "partner",
    "purpose": "provider_events",
    "tenant_id": "tenant",
    "provider_integration_id": "provider-1",
    "actor_id": "provider",
}
PARTNER = {
    "kind": "partner",
    "credential_purpose": "customer_api",
    "credential_id": "TEST-ONLY-CUSTOMER",
    "authentication_source": "fixture",
    "actor_id": "customer",
    "partner_client_id": "customer",
    "external_user_id": "resident-123",
}
PARTNER = ActorContext.model_validate(PARTNER).model_dump(mode="json")

test_metadata = MetaData()
test_events = Table(
    "test_wf_events",
    test_metadata,
    Column("id", String, primary_key=True),
    Column("payload", JSON, nullable=False),
)


class Clock:
    """Frozen fixture clock, matching the project's travel dataset date."""

    def __init__(self):
        self.now = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class Runtime:
    """Fake verified runtime, revision/grant/membership and pinned specs."""

    def __init__(self, descriptor):
        self.active, self.revision = True, 1
        self.contexts = {}
        self.spec = {
            "agent_id": "hotel",
            "version_id": "v1",
            "tool_bindings": [
                {
                    "tool_id": descriptor["tool_id"],
                    "tool_version_id": descriptor["tool_version_id"],
                    "schema_hash": descriptor["schema_hash"],
                    "required_capability": descriptor["capabilities"][0],
                }
            ],
            "execution_policy": {
                "allowed_effects": ["read", "booking", "write", "cancel"]
            },
        }
        self.add_run("run-A")

    def add_run(
        self, run_id, scope=SCOPE_A, audience=AUDIENCE, decider=MANAGER
    ):
        suffix = run_id.split("-")[-1]
        self.contexts[run_id] = {
            "run_id": run_id,
            "scope": freeze(scope),
            "mode": "production",
            "workflow_id": "workflow-" + suffix,
            "conversation_id": "conversation-" + suffix,
            "group_id": "group-" + suffix,
            "partner_audience": freeze(audience),
            "allowed_decider": freeze(decider),
            "status": "running",
            "route_revision": 1,
            "version_pins": [{"agent_id": "hotel", "version_id": "v1"}],
        }

    async def load(self, scope, run_id, uow=None):
        context = self.contexts[run_id]
        if context["scope"] != owner(scope):
            raise ExecutionError("RESOURCE_NOT_FOUND", 404)
        return freeze(context)

    async def revalidate(self, scope, context, operation, uow=None):
        if not self.active:
            raise ExecutionError("AUTHORIZATION_REVOKED", 403)
        if context["route_revision"] != self.revision:
            raise ExecutionError("ROUTE_REVISION_CHANGED", 403)
        if self.contexts[context["run_id"]]["status"] == "cancelled":
            raise ExecutionError("RUN_CANCELLED", 403)

    async def get_agent_spec(self, scope, agent_id, version_id, uow=None):
        return freeze(self.spec)

    async def authorize_tool(self, scope, context, descriptor, uow=None):
        pass

    async def authorize_conversation(self, scope, conversation_id):
        if not any(
            c["scope"] == scope and c["conversation_id"] == conversation_id
            for c in self.contexts.values()
        ):
            raise ExecutionError("RESOURCE_NOT_FOUND", 404)


class Registry:
    """Fake scoped Registry descriptor port."""

    def __init__(self, descriptor):
        self.descriptor = descriptor

    async def get_tool_snapshot(self, scope, tool_version_id):
        assert isinstance(scope, Scope)
        if tool_version_id != self.descriptor["tool_version_id"]:
            return None
        return freeze(self.descriptor)


class Quotes:
    """TEST ONLY quote adapter; no live price verification is implied."""

    def __init__(self, clock):
        self.quote = {
            "quote_ref": "quote-1",
            "quote_version": "1",
            "provider": "FAKE Hotel",
            "option": "FAKE sea view",
            "dates": ["2026-10-10", "2026-10-11"],
            "amount": {"amount_minor": 5000000, "currency": "VND"},
            "fees": {"amount_minor": 0, "currency": "VND"},
            "cancellation_terms": "FAKE non-refundable",
            "expires_at": timestamp(clock() + timedelta(minutes=20)),
        }

    async def validate(self, scope, context, request, descriptor):
        return freeze(self.quote)


class Jobs:
    """Transactional fake job outbox, persisted in a test-only table."""

    def __init__(self):
        self.fail = False

    async def enqueue_provider(self, principal, job_type, payload, key, uow):
        if self.fail:
            raise RuntimeError("TEST commit failure")
        await uow.execute(
            insert(test_events).values(id="job-" + key, payload=payload)
        )

    async def enqueue(
        self, scope, job_type, payload, key, uow, not_before=None
    ):
        assert isinstance(scope, Scope)
        assert isinstance(not_before, datetime) and not_before.tzinfo
        await self.enqueue_provider({}, job_type, payload, key, uow)


class Hitl:
    """Transactional fake bridge for existing AgentScope HITL events."""

    async def required(self, scope, record, context, uow):
        await uow.execute(
            insert(test_events).values(
                id="required-" + record["id"], payload={"status": "pending"}
            )
        )

    async def resolved(self, scope, record, context, uow):
        await uow.execute(
            insert(test_events).values(
                id="resolved-" + record["id"],
                payload={"status": record["status"]},
            )
        )


class ProviderAuth:
    """TEST ONLY signature fake; production must inject Foundation auth."""

    def __init__(self):
        self.active = True

    async def authenticate(self, raw, headers):
        if (
            headers.get("authorization") != "Bearer TEST-ONLY-PROVIDER"
            or not self.active
        ):
            raise ExecutionError("PROVIDER_UNAUTHENTICATED", 401)
        return freeze(PROVIDER)

    async def authorize_integration(self, principal, operation, uow=None):
        if not self.active or principal.get("purpose") != "provider_events":
            raise ExecutionError("PROVIDER_UNAUTHORIZED", 403)


def protocol_fixture(order_mode="snapshot"):
    """Two domains may supply different states through this same port shape."""
    return {
        "protocol_id": "FAKE-maintenance",
        "version": "1",
        "schema_hash": "FAKE-schema-1",
        "provider_integration_id": "provider-1",
        "capability": "external_tracking",
        "provider_events": True,
        "status_query": True,
        "order_mode": order_mode,
        "initial_version": 1,
        "create_fields": {
            "client_reference": "client_reference",
            "idempotency_key": "idempotency_key",
        },
    }


class Protocols:
    """TEST ONLY deterministic normalizer owned by Registry in production."""

    def __init__(self, protocol):
        self.protocol = protocol

    async def get_snapshot(self, scope, tool_version_id):
        assert isinstance(scope, Scope)
        return freeze(self.protocol)

    async def validate_envelope(self, principal, envelope):
        if envelope["event_type"] not in {
            "FAKE.progress",
            "FAKE.complete",
            "FAKE.booking_confirmed",
        }:
            raise ExecutionError("EVENT_TYPE_UNSUPPORTED", 422)

    async def normalize_verified_event(self, principal, protocol, envelope):
        data = envelope["data"]
        if not isinstance(data.get("status"), str) or data["status"] not in {
            "assigned",
            "on_the_way",
            "completed",
            "confirmed",
        }:
            raise ExecutionError("EVENT_DATA_INVALID", 422)
        return {
            "status": data["status"],
            "facts": {"label": data.get("label", "FAKE")},
            "provider_version": envelope.get("provider_version"),
            "order_mode": protocol["order_mode"],
            "terminal": data["status"] in {"completed", "confirmed"},
        }

    async def validate_transition(self, protocol, operation, event):
        if operation["job_status"] in {"completed", "confirmed"}:
            return (
                "stale"
                if event["status"] not in {"completed", "confirmed"}
                else "conflict"
            )
        if (
            event["status"] == operation["job_status"]
            and event.get("provider_version") is None
        ):
            return "stale"
        return "apply"

    async def normalize_creation_result(self, protocol, output):
        return {
            "creation_status": "succeeded",
            "external_job_id": output["external_job_id"],
            "job_status": "assigned",
            "pending": True,
        }

    async def normalize_query_result(self, protocol, result):
        return {
            "status": result["status"],
            "facts": {"label": "FAKE"},
            "provider_version": result.get("provider_version"),
            "terminal": result["status"] == "completed",
        }


class Workflow:
    """TEST ONLY atomic workflow sink. Does not implement Orchestration."""

    def __init__(self):
        self.closed, self.revoked, self.fail = set(), set(), False

    async def apply_external_event(self, scope, op, event, uow):
        if self.fail:
            raise RuntimeError("TEST workflow failure")
        if (
            op["workflow_id"] in self.closed
            or op["workflow_id"] in self.revoked
        ):
            return
        await uow.execute(
            insert(test_events).values(
                id="apply-" + event["inbox_event_id"],
                payload={
                    "scope": scope,
                    "workflow_id": op["workflow_id"],
                    "status": event["status"],
                },
            )
        )

    async def mark_operation_attention(self, scope, op, cause_id, reason, uow):
        if (
            op["workflow_id"] not in self.closed
            and op["workflow_id"] not in self.revoked
        ):
            await uow.execute(
                insert(test_events).values(
                    id="attention-" + cause_id,
                    payload={"status": "needs_attention", "reason": reason},
                )
            )

    async def apply_execution_result(self, scope, call, cause_id, uow):
        if (
            call["workflow_id"] not in self.closed
            and call["workflow_id"] not in self.revoked
        ):
            await uow.execute(
                insert(test_events).values(
                    id="reconciled-" + cause_id,
                    payload={"status": call["status"]},
                )
            )


class FakeMcpProvider:
    """
    Finite inventory, dedupe and injectable timeout-after-write/network faults.
    """

    def __init__(self, schema):
        self.schema, self.calls, self.rooms, self.bookings = schema, 0, 2, {}
        self.fault, self.before_call, self.after_write = None, None, None

    async def get_tool(self, name):
        provider = self

        class Tool:
            input_schema = provider.schema

            async def __call__(self, **arguments):
                if provider.before_call:
                    await provider.before_call()
                if provider.fault == "network_before_write":
                    raise ConnectionError("FAKE PRIVATE RESPONSE NEVER LOG")
                key = arguments.get("idempotency_key", str(provider.calls))
                if key in provider.bookings:
                    result = provider.bookings[key]
                else:
                    provider.calls += 1
                    if provider.rooms == 0:
                        return {"error": "no_availability"}
                    provider.rooms -= 1
                    result = {
                        "external_transaction_id": "FAKE-booking-"
                        + str(provider.calls),
                        "external_job_id": "FAKE-job-" + str(provider.calls),
                        "status": "confirmed",
                    }
                    provider.bookings[key] = result
                if provider.after_write:
                    await provider.after_write(arguments, result)
                if provider.fault == "timeout_after_write":
                    raise TimeoutError("FAKE committed before timeout")
                return result

        return Tool()


class Secrets:
    """TEST ONLY credential identity, with no production secrets."""

    def __init__(self):
        self.environment = "mock"
        self.owner = SCOPE_A

    async def resolve_for_execution(self, scope, ref, mode):
        assert isinstance(scope, Scope)
        if owner(scope) != self.owner:
            raise ExecutionError("CREDENTIAL_SCOPE_MISMATCH", 403)
        return {"environment": self.environment, "identity": "TEST-ONLY"}


class Projector:
    """
    Test MCP fake already emits JSON; real adapter parses ToolChunk separately.
    """

    async def project(self, scope, descriptor, chunk):
        if "error" in chunk:
            raise ExecutionError("PROVIDER_REJECTED", 422)
        return freeze(chunk)


@asynccontextmanager
async def harness(
    url="sqlite+aiosqlite:///:memory:",
    tracking=False,
    calculator=False,
    **engine_args,
):
    """
    Exercise the real SQL repository and real Execution services with fake
    ports.
    """
    clock = Clock()
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["room"],
        "properties": {
            "room": {"type": "string"},
            "client_reference": {"type": "string"},
            "idempotency_key": {"type": "string"},
        },
    }
    protocol = protocol_fixture()
    descriptor = {
        "scope": SCOPE_A,
        "tool_id": "hotel.book",
        "tool_version_id": "hotel.book.v1",
        "llm_alias": "hotel_book_v1",
        "provider_tool_name": "hotel_book",
        "description": "FAKE Hotel booking",
        "source_kind": "mcp",
        "input_schema": schema,
        "output_schema": {"type": "object"},
        "schema_hash": digest(schema),
        "capabilities": ["book_hotel"],
        "effect": "booking",
        "effect_reviewed": True,
        "available": True,
        "credential_ref": "TEST-ONLY-credential",
    }
    if tracking:
        descriptor["async_protocol_hash"] = digest(protocol)
    if calculator:
        descriptor = calculator_descriptor(SCOPE_A)
    engine = create_async_engine(url, **engine_args)
    async with engine.begin() as connection:
        await connection.run_sync(get_metadata().create_all)
        await connection.run_sync(test_metadata.create_all)
    repo = create_repository(
        async_sessionmaker(engine, expire_on_commit=False)
    )
    runtime, registry, quotes = (
        Runtime(descriptor),
        Registry(descriptor),
        Quotes(clock),
    )
    approvals = ApprovalService(repo, runtime, quotes, Hitl(), clock)
    transactions = TransactionService(repo, approvals, clock)
    operations, protocols = (
        ExternalOperationService(repo, clock),
        Protocols(protocol),
    )
    provider, secrets = FakeMcpProvider(schema), Secrets()

    @asynccontextmanager
    async def client_factory(scope, desc, credential):
        yield provider

    mcp = McpAdapter(
        secrets,
        client_factory,
        Projector(),
        idempotency_fields={"hotel.book.v1": "idempotency_key"},
    )
    gateway = ExecutionGateway(
        ExecutionPolicy(runtime, registry),
        transactions,
        mcp,
        operations,
        protocols,
    )
    auth, jobs, workflow = ProviderAuth(), Jobs(), Workflow()
    ingress = ProviderEventIngress(
        repo, auth, protocols, jobs, operations, clock
    )
    processor = ProviderEventProcessor(ingress, workflow)
    env = SimpleNamespace(**locals())
    try:
        yield env
    finally:
        await engine.dispose()


def call_fixture(call_id="call-A", run_id="run-A", calculator=False):
    """
    Server-created internal call identity; no public execute endpoint exists.
    """
    return {
        "call_id": call_id,
        "run_id": run_id,
        "agent_id": "hotel",
        "version_id": "v1",
        "tool_version_id": "builtin.money.v1"
        if calculator
        else "hotel.book.v1",
        "arguments": {"room": "FAKE-seaview"},
        "idempotency_key": "key-" + call_id,
    }


async def approved_call(env, call=None, actor=MANAGER):
    """Request and explicitly approve one test transaction."""
    call = call or call_fixture()
    proposed = await env.gateway.execute(SCOPE_A, call)
    approval = await env.repo.read(
        "approvals", SCOPE_A, proposed["approval_id"]
    )
    await env.approvals.decide_approval(
        SCOPE_A,
        approval["id"],
        "approve",
        actor,
        arguments_hash=approval["arguments_hash"],
        quote_hash=approval["quote_hash"],
    )
    return {**call, "approval_id": approval["id"]}


def event_fixture(
    event_id="event-1",
    job_id=None,
    correlation=None,
    version=1,
    status="assigned",
):
    """
    Opaque IDs remain exact; transport retry signatures are excluded from body.
    """
    event = {
        "schema_version": "1",
        "external_event_id": event_id,
        "event_type": "FAKE.progress",
        "occurred_at": "2026-10-09T02:30:00Z",
        "data": {"status": status},
        "provider_version": version,
    }
    if job_id:
        event["external_job_id"] = job_id
    if correlation:
        event["client_reference"] = correlation
    return event
