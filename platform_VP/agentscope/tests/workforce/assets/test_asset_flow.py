"""Bidirectional private-asset flow tests."""

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from agentscope.app.rag.blob_store import S3BlobStore
from agentscope.app.workforce.assets import (
    WorkforceAssetService,
    create_customer_asset_router,
    create_provider_asset_router,
)
from agentscope.app.workforce.contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    PartnerAudience,
    Scope,
    VerifiedProviderContext,
)
from agentscope.app.workforce.execution._mcp_adapter import McpAdapter
from agentscope.app.workforce.execution._utils import ExecutionError

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    @asynccontextmanager
    async def transaction(self):
        yield object()

    async def insert(self, record, uow):
        del uow
        self.rows[record["id"]] = deepcopy(record)

    async def get(self, asset_id, uow, *, lock=False):
        del uow, lock
        row = self.rows.get(asset_id)
        return None if row is None else deepcopy(row)

    async def update(self, asset_id, values, uow):
        del uow
        self.rows[asset_id].update(deepcopy(values))
        return True


class FakeStream:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


class FakeBlobStore:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}

    async def presign_put(self, key, *, content_type, metadata=None, expires_in=900):
        del expires_in
        uri = f"s3://private/{key}"
        self.objects[uri] = {
            "payload": None,
            "content_type": content_type,
            "metadata": dict(metadata or {}),
        }
        return uri, f"https://upload.invalid/{key}", {"Content-Type": content_type}

    async def stat(self, uri):
        item = self.objects.get(uri)
        if item is None or item["payload"] is None:
            return None
        return {
            "byte_size": len(item["payload"]),
            "content_type": item["content_type"],
            "metadata": item["metadata"],
            "etag": "etag",
        }

    async def promote(self, source_uri, destination_key, *, content_type, metadata):
        target_uri = f"s3://private/{destination_key}"
        self.objects[target_uri] = {
            "payload": self.objects[source_uri]["payload"],
            "content_type": content_type,
            "metadata": dict(metadata),
        }
        return target_uri

    @asynccontextmanager
    async def open(self, uri):
        yield FakeStream(self.objects[uri]["payload"])

    async def delete(self, uri):
        self.objects.pop(uri, None)

    async def presign_get(self, uri, *, expires_in, download_name):
        return f"https://download.invalid/{uri.rsplit('/', 1)[-1]}?ttl={expires_in}&name={download_name}"


class FakeS3Client:
    def __init__(self, session) -> None:
        self.session = session

    async def generate_presigned_url(self, operation, **kwargs):
        return f"https://public.invalid/{operation}/{kwargs['Params']['Key']}"

    async def copy_object(self, **kwargs):
        self.session.copies.append(kwargs)


class FakeClientContext:
    def __init__(self, client) -> None:
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *args):
        del args


class FakeS3Session:
    def __init__(self) -> None:
        self.endpoints = []
        self.copies = []

    def client(self, service, **kwargs):
        assert service == "s3"
        self.endpoints.append(kwargs["endpoint_url"])
        return FakeClientContext(FakeS3Client(self))


class FakeRouting:
    async def resolve(self, actor, target):
        del actor, target
        return SimpleNamespace(
            scope=SCOPE,
            route_id="route-1",
            route_revision=1,
        )

    async def revalidate(self, *args):
        del args


class FakeIdentity:
    async def check_scope_active(self, scope, uow=None):
        del uow
        if scope != SCOPE:
            raise PermissionError


class FakeOperations:
    def __init__(self) -> None:
        self.repo = FakeRepository()
        self.operation = {
            "id": "operation-1",
            "scope": SCOPE.model_dump(mode="json"),
            "workflow_id": "workflow-1",
            "audience_ref": {
                "partner_client_id": "partner-1",
                "external_user_id": "user-1",
                "external_ticket_id": "ticket-1",
                "external_conversation_id": "chat-1",
            },
        }

    async def resolve(self, principal, envelope, uow):
        del principal, envelope, uow
        return deepcopy(self.operation)


def customer_actor() -> ActorContext:
    return ActorContext(
        kind=ActorKind.PARTNER,
        actor_id="customer-credential",
        partner_client_id="partner-1",
        credential_id="credential-1",
        credential_purpose=CredentialPurpose.CUSTOMER_API,
        external_user_id="user-1",
        authentication_source="test",
    )


def provider_principal() -> VerifiedProviderContext:
    actor = ActorContext(
        kind=ActorKind.PARTNER,
        actor_id="provider-1",
        partner_client_id="partner-1",
        credential_id="provider-credential",
        credential_purpose=CredentialPurpose.PROVIDER_EVENTS,
        authentication_source="test",
    )
    return VerifiedProviderContext(
        tenant_id="tenant-1",
        provider_integration_id="provider-1",
        actor_id="provider-1",
        credential_id="provider-credential",
        partner_client_id="partner-1",
        signing_key_id="key-1",
        authenticated_at=NOW,
        actor=actor,
    )


class AssetFlowTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repo = FakeRepository()
        self.blob = FakeBlobStore()
        self.operations = FakeOperations()
        self.service = WorkforceAssetService(
            self.repo,
            self.blob,
            FakeRouting(),
            FakeIdentity(),
            self.operations,
            clock=lambda: NOW,
            ids=lambda: "asset-1",
        )
        self.request = {
            "schema_version": "1",
            "external_management_ref": "BQL-A",
            "external_user_id": "user-1",
            "external_ticket_id": "ticket-1",
            "external_conversation_id": "chat-1",
            "filename": "leak.png",
            "content_type": "image/png",
            "byte_size": 12,
        }

    async def test_customer_upload_bind_and_mcp_download_grant(self) -> None:
        session = await self.service.create_customer_upload(
            customer_actor(), self.request
        )
        self.assertNotIn("s3://", session.upload_url)
        uri = self.repo.rows[session.asset_id]["object_uri"]
        self.blob.objects[uri]["payload"] = b"\x89PNG\r\n\x1a\nDATA"

        projection = await self.service.complete_customer(
            customer_actor(), session.asset_id
        )
        self.assertEqual("active", projection.status)
        finalized_uri = self.repo.rows[session.asset_id]["object_uri"]
        self.assertIn("/workforce-assets/objects/", finalized_uri)
        self.assertNotIn(uri, self.blob.objects)
        audience = PartnerAudience(
            partner_client_id="partner-1",
            external_user_id="user-1",
            external_ticket_id="ticket-1",
            external_conversation_id="chat-1",
        )
        async with self.repo.transaction() as uow:
            with self.assertRaisesRegex(ExecutionError, "ASSET_BINDING_MISMATCH"):
                await self.service.bind_customer_assets(
                    SCOPE,
                    audience.model_copy(update={"external_ticket_id": "ticket-other"}),
                    "workflow-other",
                    (session.asset_id,),
                    uow,
                )
            await self.service.bind_customer_assets(
                SCOPE, audience, "workflow-1", (session.asset_id,), uow
            )

        arguments = {"asset_ids": [session.asset_id], "summary": "pipe"}
        descriptor = {
            "capabilities": ["asset_download_v1"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "asset_ids": {"type": "array"},
                    "summary": {"type": "string"},
                    "asset_downloads": {"type": "array"},
                },
            },
        }
        materialized = await self.service.materialize_for_provider(
            SCOPE,
            {"workflow_id": "workflow-1"},
            descriptor,
            arguments,
        )
        self.assertNotIn("asset_downloads", arguments)
        self.assertEqual(
            session.asset_id, materialized["asset_downloads"][0]["asset_id"]
        )
        self.assertIn("ttl=300", materialized["asset_downloads"][0]["download_url"])

        grant = await self.service.customer_download(customer_actor(), session.asset_id)
        self.assertEqual(session.asset_id, grant.asset_id)

    async def test_fake_image_is_rejected(self) -> None:
        session = await self.service.create_customer_upload(
            customer_actor(), self.request
        )
        uri = self.repo.rows[session.asset_id]["object_uri"]
        self.blob.objects[uri]["payload"] = b"not-an-image"
        with self.assertRaisesRegex(ExecutionError, "ASSET_UPLOAD_MISMATCH"):
            await self.service.complete_customer(customer_actor(), session.asset_id)
        self.assertEqual("rejected", self.repo.rows[session.asset_id]["status"])

    def test_mcp_model_cannot_supply_download_urls(self) -> None:
        adapter = McpAdapter(None, None, None)
        descriptor = {
            "tool_version_id": "tool-v1",
            "input_schema": {
                "type": "object",
                "properties": {
                    "asset_downloads": {"type": "array"},
                    "summary": {"type": "string"},
                },
                "required": ["asset_downloads", "summary"],
                "additionalProperties": False,
            },
        }
        schema = adapter.model_input_schema(descriptor)
        self.assertNotIn("asset_downloads", schema["properties"])
        self.assertNotIn("asset_downloads", schema["required"])
        with self.assertRaisesRegex(ExecutionError, "ASSET_DOWNLOADS_SERVER_OWNED"):
            adapter.validate_model_input(
                descriptor,
                {"summary": "pipe", "asset_downloads": ["spoof"]},
            )

    async def test_provider_upload_is_bound_to_operation_for_reverse_flow(self) -> None:
        provider_request = {
            "schema_version": "1",
            "client_reference": "correlation-1",
            "filename": "completion.png",
            "content_type": "image/png",
            "byte_size": 12,
        }
        session = await self.service.create_provider_upload(
            provider_principal(), provider_request
        )
        uri = self.repo.rows[session.asset_id]["object_uri"]
        self.blob.objects[uri]["payload"] = b"\x89PNG\r\n\x1a\nDONE"
        projection = await self.service.complete_provider(
            provider_principal(), session.asset_id
        )
        self.assertEqual("provider", projection.origin)
        with self.assertRaisesRegex(ExecutionError, "ASSET_BINDING_MISMATCH"):
            await self.service.materialize_for_provider(
                SCOPE,
                {"workflow_id": "workflow-1"},
                {
                    "capabilities": ["asset_download_v1"],
                    "input_schema": {
                        "properties": {"asset_downloads": {"type": "array"}}
                    },
                },
                {"asset_ids": [session.asset_id]},
            )

        envelope = {
            "client_reference": "correlation-1",
            "data": {"status": "completed"},
            "attachments": [{"asset_id": session.asset_id}],
        }
        async with self.repo.transaction() as uow:
            await self.service.validate_provider_event_assets(
                provider_principal(), envelope, uow
            )
        self.operations.operation["id"] = "operation-other"
        async with self.repo.transaction() as uow:
            with self.assertRaisesRegex(
                ExecutionError, "PROVIDER_ASSET_BINDING_MISMATCH"
            ):
                await self.service.validate_provider_event_assets(
                    provider_principal(), envelope, uow
                )

    def test_asset_routes_compose_under_one_workforce_prefix(self) -> None:
        from fastapi import APIRouter, FastAPI

        async def customer_dependency():
            return customer_actor()

        parent = APIRouter(prefix="/workforce/v1")
        parent.include_router(
            create_customer_asset_router(self.service, customer_dependency)
        )
        parent.include_router(
            create_provider_asset_router(self.service, SimpleNamespace())
        )
        app = FastAPI()
        app.include_router(parent)
        paths = set(app.openapi()["paths"])
        self.assertIn("/workforce/v1/partner/assets/upload-sessions", paths)
        self.assertIn("/workforce/v1/provider/assets/upload-sessions", paths)
        self.assertFalse(any("/workforce/v1/workforce/v1/" in path for path in paths))

    async def test_presigned_urls_use_public_not_container_endpoint(self) -> None:
        import importlib.util

        if importlib.util.find_spec("aioboto3") is None:
            self.skipTest("aioboto3 is not installed (s3 extra)")
        store = S3BlobStore(
            "private",
            endpoint_url="http://minio:9000",
            public_endpoint_url="https://assets.example.test",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )
        session = FakeS3Session()
        store._session = session
        uri, url, headers = await store.presign_put(
            "workforce-assets/asset.png",
            content_type="image/png",
            metadata={"asset-id": "asset-1"},
        )
        self.assertEqual("s3://private/workforce-assets/asset.png", uri)
        self.assertTrue(url.startswith("https://public.invalid/put_object/"))
        self.assertEqual("image/png", headers["Content-Type"])
        await store.presign_get(uri)
        promoted = await store.promote(
            uri,
            "workforce-assets/objects/asset.png",
            content_type="image/png",
            metadata={"asset-id": "asset-1"},
        )
        self.assertEqual("s3://private/workforce-assets/objects/asset.png", promoted)
        self.assertEqual("REPLACE", session.copies[0]["MetadataDirective"])
        self.assertEqual(
            [
                "https://assets.example.test",
                "https://assets.example.test",
                "http://minio:9000",
            ],
            session.endpoints,
        )
