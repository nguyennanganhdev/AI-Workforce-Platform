"""TEST ONLY C6 composition: real SQL C1/C2/C4/C5 and raw C3 HTTP.

The C5 scripted Leader, tool catalog, quote/HITL and MCP backend remain
explicit test dependencies. This is not the global C7 composition.
"""

import asyncio
import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, MetaData, String, Table, insert

from agentscope.app.workforce.contracts import (
    ActorContext,
    InboundReceipt,
    PartnerAudience,
    PartnerOperation,
)
from agentscope.app.workforce.execution import (
    PartnerApprovalService,
    create_router as execution_router,
)
from agentscope.app.workforce.execution.external_operations import (
    OperationReconciler,
    RegistryExecutionProtocols,
)
from agentscope.app.workforce.execution.provider_events import (
    ProviderEventIngress,
    ProviderEventProcessor,
    WorkflowEventAdapter,
)
from agentscope.app.workforce.foundation import (
    DurableJobWorker,
    HmacProviderAuth,
    SqlIdentityPort,
    SqlPartnerRoutingPort,
    SqlProviderCredentialRepository,
)
from agentscope.app.workforce.foundation._tables import (
    manager_memberships,
    partner_manager_routes,
    provider_credentials,
    provider_integrations,
)
from agentscope.app.workforce.orchestration import (
    WorkflowContinuationJobHandler,
    create_router as workflow_router,
)
from tests.workforce.lifecycle.async_evaluation import runtime_fixture as c5
from tests.workforce.lifecycle.async_evaluation.test_phase_b import fixture
from tests.workforce.orchestration.phase_c.test_c4_sql_slice import SCOPE

SECRET = b"TEST-ONLY-C6-HMAC-SECRET-DO-NOT-USE" * 2


class _Authorization:
    """Test composition of C4 authorization with C1 SQL grant validation."""

    def __init__(self, env):
        self.env = env

    async def authorize(self, scope, actor, audience, operation, uow=None):
        actor = ActorContext.model_validate(actor)
        audience = PartnerAudience.model_validate(audience)
        if (
            actor.external_user_id != audience.external_user_id
            or actor.partner_client_id != audience.partner_client_id
        ):
            raise PermissionError("customer audience mismatch")
        await self.env.ingress.identity.check_scope_active(scope, uow=uow)
        await self.env.ingress.routing.revalidate(
            scope,
            "route-1",
            1,
            actor,
            audience,
            {
                "read_events": "receive_events",
                "start": "submit_request",
                "close": "close_workflow",
            }.get(operation, operation),
            uow=uow,
        )

    async def authorize_trigger(self, aggregate, trigger, uow=None):
        audience = aggregate.workflow.audience
        actor = self.env.actor.model_copy(
            update={"external_user_id": audience.external_user_id}
        )
        await self.authorize(
            aggregate.workflow.scope, actor, audience, "reply", uow
        )

    async def can_publish_external_event(self, aggregate, event, uow):
        try:
            await self.authorize_trigger(aggregate, event, uow)
        except PermissionError:
            return False
        return True


class _Queries:
    def __init__(self, provider):
        self.calls, self.provider = [], provider

    async def query(self, scope, operation, timer_id):
        self.calls.append((scope, operation["id"], timer_id))
        result = self.provider.bookings[operation["correlation_id"]]
        return {
            "status": result["status"],
            "external_job_id": result["external_job_id"],
            "provider_version": 0,
        }


class _ApprovalCommands:
    """C7 wiring example: existing command ledger + approval trigger, one UOW.

    No private ledger or fabricated workflow endpoint. A production root must
    supply equivalent binding authorization and continuation scheduling.
    """

    def __init__(self, driver):
        self.driver = driver

    def __getattr__(self, name):
        return getattr(self.driver.env.requests, name)

    async def authorize_approval(self, actor, approval_id, body, uow=None):
        driver = self.driver
        approval = await driver.env.execution_repository.get(
            "approvals", approval_id, uow, SCOPE
        )
        if approval is None:
            raise PermissionError("approval not visible")
        aggregate = await driver.env.workflows_repo.load(
            SCOPE, approval["workflow_id"], uow
        )
        audience = aggregate.workflow.audience
        if (
            any(
                body[key] != getattr(audience, key)
                for key in (
                    "external_user_id",
                    "external_ticket_id",
                    "external_conversation_id",
                )
            )
            or body["workflow_id"] != aggregate.workflow.workflow_id
        ):
            raise PermissionError("approval binding mismatch")
        await driver.env.authorization.authorize(
            SCOPE, actor, audience, "submit_consent", uow
        )
        return {"scope": SCOPE.model_dump(), "audience": audience.model_dump()}

    async def record_result(self, request_id, result, uow=None):
        await self.driver.env.requests.record_result(request_id, result, uow)
        if result.data["status"] == "approved":
            aggregate = await self.driver.env.workflows_repo.load(
                SCOPE, result.data["workflow_id"], uow
            )
            user = aggregate.workflow.audience.external_user_id
            actor = self.driver.env.actor.model_copy(
                update={"external_user_id": user}
            )
            continuation = await self.driver.env.requests.claim_or_read(
                actor,
                "approval-continuation-" + request_id,
                "approval_continuation",
                result.data["workflow_id"],
                hashlib.sha256(request_id.encode()).hexdigest(),
                uow,
            )
            await self.driver.env.workflow_service.enqueue_trigger(
                SCOPE,
                {
                    "trigger_id": "approval-" + request_id,
                    "workflow_id": result.data["workflow_id"],
                    "cause": {
                        "kind": "approval",
                        "request_id": continuation.request_id,
                        "approval_id": result.data["approval_id"],
                    },
                },
                uow,
            )


class RawProviderCaseDriver(c5.SqlCaseDriver):
    """C5 evaluation driver with C6 raw HTTP/inbox/jobs and real query hook."""

    def __init__(self, database_url=None, connect_args=None):
        self.database_url = database_url
        self.connect_args = connect_args or {}

    async def setup(self):
        data = fixture()
        protocol = data["protocols"][0]
        data["protocols"] = [
            protocol.model_copy(
                update={
                    "ordering": "provider_version",
                    "event_mappings": {
                        status: protocol.event_mappings[
                            "completed"
                        ].model_copy(update={"status": status})
                        for status in (
                            "assigned",
                            "on_the_way",
                            "arrived",
                            "completed",
                        )
                    },
                }
            )
        ]
        # Change only test input data; all production adapters run unpatched.
        with patch.object(c5, "fixture", lambda: data):
            if self.database_url:
                create_engine = c5.c4.create_async_engine
                with patch.object(
                    c5.c4,
                    "create_async_engine",
                    lambda _: create_engine(
                        self.database_url, connect_args=self.connect_args
                    ),
                ):
                    await super().setup()
            else:
                await super().setup()
        await self._seed_identity()
        self.env.ingress.identity = SqlIdentityPort(self.env.uows)
        self.env.ingress.routing = SqlPartnerRoutingPort(
            self.env.uows, clock=self.env.clock
        )
        self.env.authorization = _Authorization(self.env)
        self.env.workflow_service.authorization = self.env.authorization
        self.env.event_service.authorization = self.env.authorization

        async def api_key_auth(key):
            if key != "TEST-ONLY-C6-PROVIDER":
                raise PermissionError("test API key rejected")
            return {
                "key_id": "c6-api-key",
                "tenant_id": SCOPE.tenant_id,
                "client_id": "provider-client",
            }

        self.auth = HmacProviderAuth(
            SqlProviderCredentialRepository(self.env.uows),
            api_key_auth,
            lambda ref: SECRET,
            clock=self.env.clock,
        )
        self.protocols = RegistryExecutionProtocols(
            self.registry_provider,
            self.env.execution_repository,
            self.auth,
            self.operations,
        )
        self.gateway.protocols = self.protocols
        self.provider_ingress = ProviderEventIngress(
            self.env.execution_repository,
            self.auth,
            self.protocols,
            self.env.jobs,
            self.operations,
            self.env.clock,
        )
        self.workflow_adapter = WorkflowEventAdapter(
            self.env.execution_repository,
            self.env.workflow_service,
            query_sink=self.env.workflow_service.apply_query_result,
        )
        self.processor = ProviderEventProcessor(
            self.provider_ingress, self.workflow_adapter
        )
        self.queries = _Queries(self.provider)
        self.reconciler = OperationReconciler(
            self.env.execution_repository,
            self.queries,
            self.protocols,
            self.workflow_adapter,
            self.env.jobs,
        )
        self.restart_worker()

        async def customer(request: Request):
            return self.env.actor.model_copy(
                update={
                    "external_user_id": request.headers.get(
                        "x-test-user", "resident-1"
                    )
                }
            )

        async def manager():
            return {"scope": SCOPE.model_dump()}

        self.app = FastAPI()
        self.app.include_router(
            workflow_router(
                self.env.ingress,
                self.env.event_service,
                customer,
                bounded_wait_seconds=0,
            )
        )
        self.partner_approvals = PartnerApprovalService(
            self.approvals, _ApprovalCommands(self)
        )
        self.app.include_router(
            execution_router(
                self.gateway,
                self.approvals,
                self.partner_approvals,
                self.provider_ingress,
                manager,
                customer,
                self.auth,
            )
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=self.app), base_url="http://test"
        )
        self.raw_events = {}

    async def _seed_identity(self):
        metadata = MetaData()

        def table(name, fields):
            return Table(
                name,
                metadata,
                *[
                    Column(field, String(255), primary_key=field == "id")
                    for field in fields.split()
                ],
            )

        domains = table("business_domains", "id tenant_id status")
        areas = table("areas", "id domain_id status")
        users = table(
            "auth_users", "id tenant_id domain_id area_id role status"
        )
        async with self.env.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        now = self.env.clock()
        async with self.env.uows() as tx:
            await tx.execute(
                insert(domains).values(
                    id=SCOPE.domain_id,
                    tenant_id=SCOPE.tenant_id,
                    status="active",
                )
            )
            await tx.execute(
                insert(areas).values(
                    id=SCOPE.area_id,
                    domain_id=SCOPE.domain_id,
                    status="active",
                )
            )
            await tx.execute(
                insert(users).values(
                    id=SCOPE.manager_account_id,
                    tenant_id=SCOPE.tenant_id,
                    domain_id=SCOPE.domain_id,
                    area_id=SCOPE.area_id,
                    role="AREA_MANAGER",
                    status="active",
                )
            )
            await tx.execute(
                insert(manager_memberships).values(
                    id="c6-membership",
                    **SCOPE.model_dump(),
                    status="verified",
                    revision=1,
                    verified_by="test-provisioning",
                    verified_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await tx.execute(
                insert(partner_manager_routes).values(
                    id="route-1",
                    **SCOPE.model_dump(),
                    partner_client_id="partner-1",
                    external_management_ref="tower-a",
                    status="active",
                    revision=1,
                    membership_revision=1,
                    allowed_operations=list(PartnerOperation),
                    granted_by=SCOPE.manager_account_id,
                    confirmed_by_client_id="partner-1",
                    created_at=now,
                    updated_at=now,
                )
            )
            await tx.execute(
                insert(provider_integrations).values(
                    id="provider-A",
                    tenant_id=SCOPE.tenant_id,
                    partner_client_id="provider-client",
                    name="TEST-C6",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            await tx.execute(
                insert(provider_credentials).values(
                    id="c6-credential",
                    provider_integration_id="provider-A",
                    api_credential_id="c6-api-key",
                    signing_key_id="c6-signing",
                    secret_ref="TEST-C6-secret-reference",
                    purpose="provider_events",
                    allowed_operations=[
                        "publish_job_event",
                        "read_event_receipt",
                    ],
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            await tx.commit()

    def restart_worker(self):
        handler = WorkflowContinuationJobHandler(
            self.continuation, worker_id="c6-workflow"
        )

        async def checked(handler, job):
            try:
                return await handler(job)
            except Exception as error:
                self.last_turn_error = error
                raise

        async def continuation(job):
            return await checked(handler, job)

        async def provider(job):
            return await checked(self.processor.handle_job, job)

        async def reconcile(job):
            return {
                "outcome": await self.reconciler.reconcile(
                    job.scope,
                    job.payload["operation_id"],
                    job.payload["timer_id"],
                )
            }

        self.worker = DurableJobWorker(
            self.env.jobs,
            {
                handler.job_type: continuation,
                "provider_event": provider,
                "operation_reconcile": reconcile,
            },
            # SQLite serializes writers; lease races are a PostgreSQL gate.
            worker_id="c6-worker",
            heartbeat_interval=10.0,
        )

    async def open_case(self, scope, snapshot, test_case, bind):
        self.pattern, self.snapshot = test_case["pattern"], snapshot
        self.bind_case = bind
        case_id = test_case["case_id"]
        user = test_case.get("external_user_id", case_id)
        self.actor = self.env.actor.model_copy(
            update={"external_user_id": user}
        )
        envelope = self.env.envelope(
            case_id,
            test_case.get("external_ticket_id", "ticket-A"),
            "chat-" + case_id,
        ).model_copy(update={"external_user_id": user, "residence_id": None})
        response = await self.client.post(
            "/workforce/v1/partner/requests",
            headers={"x-test-user": user},
            json=envelope.model_dump(mode="json"),
        )
        response.raise_for_status()
        receipt = InboundReceipt.model_validate(response.json())
        self.opened[case_id] = (self.actor, receipt)
        aggregate = await self.env.workflows_repo.load(
            scope, receipt.workflow_id
        )
        self.call = {
            "call_id": "call-" + case_id,
            "run_id": receipt.workflow_id,
            "agent_id": snapshot.agent_id,
            "version_id": snapshot.candidate_version_id,
            "tool_version_id": "repair-v1",
            "arguments": {"room": "TEST-room"},
            "idempotency_key": "call-" + case_id,
        }
        self.runtime_authority.contexts[receipt.workflow_id] = {
            "run_id": receipt.workflow_id,
            "scope": scope.model_dump(),
            "mode": "evaluation",
            "workflow_id": receipt.workflow_id,
            "conversation_id": receipt.conversation_id,
            "ticket_id": aggregate.workflow.ticket_id,
            "group_id": aggregate.workflow.group_id,
            "partner_audience": aggregate.workflow.audience.model_dump(),
            "allowed_decider": {
                "kind": "manager",
                "actor_id": scope.manager_account_id,
            },
            "status": "running",
            "route_revision": 1,
            "version_pins": [
                {
                    "agent_id": snapshot.agent_id,
                    "version_id": snapshot.candidate_version_id,
                }
            ],
        }
        if self.pattern == "external_tracking":
            self.descriptor["async_protocol_hash"] = (
                self.protocol.snapshot_ref.schema_hash
            )
        else:
            self.descriptor.pop("async_protocol_hash", None)
        return receipt.workflow_id

    def signed(self, raw):
        stamp = str(int(self.env.clock().timestamp()))
        signature = hmac.new(
            SECRET, stamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        return {
            "authorization": "ApiKey TEST-ONLY-C6-PROVIDER",
            "x-partner-timestamp": stamp,
            "x-partner-key-id": "c6-signing",
            "x-partner-signature": "v1=" + signature,
            "content-type": "application/json",
        }

    async def send(self, envelope):
        raw = json.dumps(envelope).encode()
        return await self.client.post(
            "/workforce/v1/provider/job-events",
            content=raw,
            headers=self.signed(raw),
        )

    async def receipt(self, receipt_id):
        response = await self.client.get(
            "/workforce/v1/provider/event-receipts/" + receipt_id,
            headers=self.signed(b""),
        )
        response.raise_for_status()
        return response.json()

    async def provider_fact(self, scope, before, key):
        operation_id = before.checkpoint.operation_refs[0]
        if self.cause == "timer-query-pending":
            async with self.env.uows() as tx:
                await self.reconciler.schedule(
                    scope, operation_id, key, self.env.clock(), tx
                )
                await tx.commit()
        else:
            status, version = {
                "assigned-v1": ("assigned", 1),
                "on-the-way-v2": ("on_the_way", 2),
                "duplicate-v2": ("on_the_way", 2),
                "arrived-v3": ("arrived", 3),
                "completed-v4": ("completed", 4),
                "completed": ("completed", 1),
                "late-v2": ("on_the_way", 2),
            }[self.cause]
            operation = await self.env.execution_repository.read(
                "operations", scope, operation_id
            )
            if self.cause == "duplicate-v2":
                event = self.raw_events[(operation_id, status)]
            else:
                event = {
                    "schema_version": "1",
                    "external_event_id": key,
                    "client_reference": operation["correlation_id"],
                    "event_type": status,
                    "provider_version": version,
                    "occurred_at": self.env.clock().isoformat(),
                    "data": {
                        "confirmed": status == "completed",
                        "private_note": "TEST PRIVATE PROVIDER NOTE",
                    },
                }
                if operation["external_job_id"]:
                    event["external_job_id"] = operation["external_job_id"]
                self.raw_events[(operation_id, status)] = event
            response = await self.send(event)
            response.raise_for_status()
            assert response.status_code == 202
        # Commit provider fact and enqueue continuation before C5 captures
        # the next model turn. Duplicates may have no queued provider job.
        if self.cause != "duplicate-v2":
            outcome = await self.worker.run_once()
            if outcome.status != "succeeded":
                raise self.last_turn_error

    async def cleanup(self):
        if hasattr(self, "client"):
            await self.client.aclose()
        await super().cleanup()


async def sse_frames(app, path, user, count, cursor=None):
    """Read actual HTTP SSE with a bounded ASGI client disconnect.

    HTTPX's in-process transport buffers infinite bodies. This client sends
    http.disconnect after N frames; it never changes the server's SSE stream.
    """
    messages = []
    disconnected = asyncio.Event()
    first = True

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body":
            body = b"".join(m.get("body", b"") for m in messages)
            if body.count(b"\ndata:") >= count:
                disconnected.set()
                await asyncio.sleep(0)

    headers = [(b"x-test-user", user.encode())]
    if cursor:
        headers.append((b"last-event-id", cursor.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": ("external_user_id=" + user).encode(),
        "headers": headers,
        "server": ("test", 80),
        "client": ("test", 1),
    }
    await asyncio.wait_for(app(scope, receive, send), 5)
    return messages
